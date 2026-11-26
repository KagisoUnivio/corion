#!/usr/bin/env python3
"""Run the Corion acceptance checks against an isolated market-data database."""

import argparse
import csv
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def seed_checks(seed, rebuilt, dump):
    with (
        closing(sqlite3.connect(seed.resolve().as_uri() + "?mode=ro", uri=True)) as original,
        closing(sqlite3.connect(rebuilt.resolve().as_uri() + "?mode=ro", uri=True)) as fresh,
        closing(sqlite3.connect(":memory:")) as replay,
    ):
        replay.executescript(dump.read_text(encoding="utf-8"))
        for db in (original, fresh, replay):
            equal(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)], "integrity")
            equal(db.execute("PRAGMA foreign_key_check").fetchall(), [], "foreign keys")
            equal(db.execute("SELECT COUNT(*) FROM Instruments").fetchone(), (20,), "instruments")
            query = """
                SELECT COUNT(*), MIN(PriceDate), MAX(PriceDate), COUNT(*) - COUNT(ClosePrice)
                FROM DailyPrices
            """
            equal(db.execute(query).fetchone(), (616, "2026-10-01", "2026-11-13", 5), "prices")
        for table in ("Instruments", "DailyPrices"):
            query = f"SELECT * FROM {table} ORDER BY 1, 2"
            expected = original.execute(query).fetchall()
            equal(fresh.execute(query).fetchall(), expected, f"rebuilt {table}")
            equal(replay.execute(query).fetchall(), expected, f"SQL replay {table}")

        selectors = [
            (1, "2026-11-05", ("2026-11-05", 17101)),
            (5, "2026-11-05", ("2026-11-05", 5067)),
            (5, "2026-11-09", ("2026-11-06", 5141)),
            (20, "2026-11-13", ("2026-11-12", 4570)),
            (5, "2026-09-30", None),
        ]
        query = """
            SELECT PriceDate, ClosePrice FROM DailyPrices
            WHERE InstrumentId = ? AND PriceDate <= ? AND ClosePrice > 0
            ORDER BY PriceDate DESC LIMIT 1
        """
        for instrument, day, expected in selectors:
            equal(fresh.execute(query, (instrument, day)).fetchone(), expected, f"close {instrument} on {day}")
        equal(
            fresh.execute("SELECT ClosePrice, Source FROM DailyPrices WHERE InstrumentId=3 AND PriceDate='2026-11-06'").fetchone(),
            (33646, "JSE EOD (corrected)"),
            "corrected source price",
        )
        equal(
            fresh.execute("SELECT Name FROM Instruments WHERE InstrumentId=20").fetchone(),
            ("Karoo Winemakers' Co-op",),
            "repaired instrument name",
        )
    print("PASS seed integrity, row-for-row parity, source exceptions and per-instrument cutoff")


def request(base, path, expected=200, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    url = base.rstrip("/") + path
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read().decode()
        equal(response.code, expected, f"{method} {path}, response {raw}")
        return json.loads(raw)


def ledger(base, **filters):
    return request(base, "/trades?" + urlencode(filters))


def money(row, amount, currency):
    value = row["consideration"]
    equal(isinstance(value, str), True, "consideration is a decimal string")
    equal(Decimal(value), Decimal(amount), "consideration")
    equal(row["currency"], currency, "currency")


def create(base, payload, expected=201):
    return request(base, "/trades", expected, payload, "POST")


def transition(base, trade_id, status, expected=200, **fields):
    return request(base, f"/trades/{trade_id}/status", expected, {"status": status, **fields}, "PATCH")


def api_checks(base, state, p1):
    if state.exists():
        raise ValueError("Choose a fresh --state file for the initial run")
    equal(request(base, "/health")["status"], "ok", "health")
    reference = request(base, "/reference-data")
    equal(set(reference["funds"]), {"KESCON", "FYNBAL", "BAOGLB", "PROINC"}, "funds")
    equal(set(reference["brokers"]), {"Kudu Securities", "Impala Capital", "Springbok Stockbrokers"}, "brokers")

    instruments = {row["code"]: row for row in request(base, "/instruments")}
    equal(len(instruments), 20, "real instruments")
    equal(instruments["NMR"]["last_close_date"], "2026-11-06", "NMR latest valid date")
    equal(Decimal(instruments["NMR"]["last_close"]), Decimal("5141"), "NMR latest valid close")
    equal(instruments["KWP"]["last_close_date"], "2026-11-12", "KWP latest valid date")

    today = datetime.now(ZoneInfo("Africa/Johannesburg")).date().isoformat()
    payload = {
        "trade_date": today, "fund": "KESCON", "instrument_id": instruments["MZT"]["id"],
        "side": "BUY", "qty": "100", "price": "2500", "broker": "Kudu Securities",
    }
    cases = (
        ("MZT", "ZAc", "100", "2500", "2500.00", "ZAR"),
        ("NWT", "USD", "10", "150.25", "1502.50", "USD"),
        ("R2032X", "PCT_NOMINAL", "100000", "98.5", "98500.00", "ZAR"),
        ("ALSIZ26", "INDEX_POINTS", "2", "75000", "1500000.00", "ZAR"),
    )
    captured = {}
    for code, unit, qty, price, amount, currency in cases:
        instrument = instruments[code]
        equal(instrument["quote_unit"], unit, f"{code} quote unit")
        row = create(base, dict(payload, instrument_id=instrument["id"], qty=qty, price=price))
        money(row, amount, currency)
        equal(row["status"], "DRAFT", f"{code} status")
        equal(row["executed_price"], None, f"{code} executed price")
        captured[code] = row

    expected_ids = {row["id"] for row in captured.values()}
    for filters in ({}, {"date": today, "fund": "KESCON"}):
        ids = {row["id"] for row in ledger(base, **filters)}
        equal(expected_ids <= ids, True, f"captured trades visible with {filters}")
    equal(ledger(base, date=today, fund="FYNBAL"), [], "other fund")
    equal(ledger(base, date="2026-09-29", fund="KESCON"), [], "other date")

    before = ledger(base, date=today, fund="KESCON")
    for field in ("side", "broker"):
        invalid = payload.copy()
        del invalid[field]
        create(base, invalid, 422)
    for field, value in (
        ("side", "HOLD"), ("fund", "UNKNOWN"), ("broker", "UNKNOWN"),
        ("instrument_id", -1), ("trade_date", "2026-02-30"), ("trade_date", "26/11/2026"),
    ):
        create(base, dict(payload, **{field: value}), 422)
    for field in ("qty", "price"):
        for value in ("0", "-1", "NaN", "Infinity"):
            create(base, dict(payload, **{field: value}), 422)
    create(base, dict(payload, instrument_id=instruments["ALSIZ26"]["id"], qty="1.5"), 422)
    equal(
        {row["id"] for row in ledger(base, date=today, fund="KESCON")},
        {row["id"] for row in before},
        "invalid requests store no trade",
    )
    print("PASS P0 API money, real instruments, validation and date/fund filtering")

    draft = captured["MZT"]
    if p1:
        p1_checks(base, payload, instruments, draft["id"])
    state.write_text(json.dumps({"id": draft["id"], "date": today, "fund": draft["fund"],
                                 "status": "DONE" if p1 else "DRAFT"}), encoding="utf-8")
    print(f"Restart the API against the same database, then run restart with --state {state}")


def p1_checks(base, payload, instruments, trade_id):
    transition(base, trade_id, "EXECUTED", 409, executed_price="2550")
    transition(base, 2147483647, "SENT", 404)
    equal(transition(base, trade_id, "SENT")["status"], "SENT", "manual SENT")
    transition(base, trade_id, "DRAFT", 409)
    transition(base, trade_id, "EXECUTED", 422)
    transition(base, trade_id, "EXECUTED", 422, executed_price="0")
    executed = transition(base, trade_id, "EXECUTED", executed_price="2550")
    done = transition(base, trade_id, "DONE")
    for row, status in ((executed, "EXECUTED"), (done, "DONE")):
        equal(row["status"], status, "transition")
        equal(Decimal(row["price"]), Decimal("2500"), "original price")
        equal(Decimal(row["executed_price"]), Decimal("2550"), "executed price")
        money(row, "2550.00", "ZAR")

    close = Decimal("17101")
    for factor, deviation, warns in (("1.05", "5", False), ("0.95", "5", False),
                                      ("1.06", "6", True), ("0.94", "6", True)):
        row = create(base, dict(payload, trade_date="2026-11-05", price=str(close * Decimal(factor))))
        equal(Decimal(row["last_close"]), close, "historical close")
        equal(row["last_close_date"], "2026-11-05", "history cutoff")
        equal(Decimal(row["price_deviation_pct"]), Decimal(deviation), "deviation")
        equal(bool(row["warning"]), warns, "advisory warning")
    row = create(base, dict(payload, trade_date="2026-11-09", instrument_id=instruments["NMR"]["id"]))
    equal(row["last_close_date"], "2026-11-06", "same-instrument fallback")
    equal(Decimal(row["last_close"]), Decimal("5141"), "null close skipped")
    row = create(base, dict(payload, trade_date="2026-09-30"))
    for field in ("last_close", "last_close_date", "price_deviation_pct"):
        equal(row[field], None, f"unavailable {field}")
    equal(bool(row["warning"]), True, "unavailable comparison warning")
    print("PASS P1 status, execution money, warning boundaries and historical closes")


def restart_check(base, state):
    trade = json.loads(state.read_text(encoding="utf-8"))
    matching = [row for row in ledger(base, date=trade["date"], fund=trade["fund"])
                if row["id"] == trade["id"]]
    equal(len(matching), 1, "trade retrieved after operator restart")
    equal(matching[0]["status"], trade["status"], "persisted status")
    print("PASS persisted trade and status")



def extended_checks(base, database):
    day = "2026-09-28"
    payload = {
        "trade_date": day, "fund": "BAOGLB", "instrument_id": 1, "side": "BUY",
        "qty": "12", "price": "2500", "broker": "Kudu Securities",
    }
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executemany("INSERT INTO Instruments VALUES (?,?,?,?,?,?,?,?)", [
            (90001, "QAUNK", "QA unsupported quote", "EQUITY", "JSE", "ZAR", "UNKNOWN", 1),
            (90002, "QAZERO", "QA zero close", "EQUITY", "JSE", "ZAR", "ZAc", 1),
        ])
        db.execute("INSERT INTO DailyPrices VALUES (?, ?, ?, ?, ?)", (90002, day, 0, None, "QA"))

    rejected = create(base, dict(payload, instrument_id=90001), 422)
    equal("unsupported quote" in rejected["detail"].lower(), True, "unsupported quote detail")
    equal(ledger(base, date=day, fund="BAOGLB"), [], "unsupported quote stores no trade")
    zero = create(base, dict(payload, instrument_id=90002))
    for field in ("last_close", "last_close_date", "price_deviation_pct"):
        equal(zero[field], None, f"zero close {field}")
    equal(bool(zero["warning"]), True, "zero close warning")
    bond = create(base, dict(payload, trade_date="2026-11-05", instrument_id=11))
    equal(bond["price_deviation_pct"], None, "bond basis comparison unavailable")
    equal(bool(bond["warning"]), True, "bond comparison warning")
    print("PASS unsupported quote, zero close and unconfirmed bond close basis")

    buy = create(base, payload)
    sell = create(base, dict(payload, side="SELL", qty="5"))
    other_fund = create(base, dict(payload, fund="FYNBAL", qty="4"))
    sent = create(base, dict(payload, qty="40"))
    transition(base, sent["id"], "SENT")
    for trade in (buy, sell, other_fund):
        transition(base, trade["id"], "SENT")
        transition(base, trade["id"], "EXECUTED", executed_price="2500")
    transition(base, buy["id"], "DONE")

    positions = request(base, "/positions")
    net = {(row["fund"], row["instrument_id"]): Decimal(row["net_qty"]) for row in positions}
    equal(net[("BAOGLB", 1)], Decimal("7"), "BUY less SELL, excluding SENT")
    equal(net[("FYNBAL", 1)], Decimal("4"), "separate fund position")
    equal(("BAOGLB", 90002) in net, False, "DRAFT contributes no position")
    filtered = request(base, "/positions?fund=BAOGLB")
    equal({row["fund"] for row in filtered}, {"BAOGLB"}, "position fund filter")
    with urlopen(base.rstrip("/") + "/trades/export?" + urlencode({"date": day, "fund": "BAOGLB"}), timeout=5) as response:
        equal(response.headers.get_content_type(), "text/csv", "CSV media type")
        rows = list(csv.DictReader(io.StringIO(response.read().decode())))
    equal({int(row["id"]) for row in rows}, {buy["id"], sell["id"], sent["id"], zero["id"]}, "CSV filters")
    equal({row["trade_date"] for row in rows}, {day}, "CSV ISO dates")
    equal({row["currency"] for row in rows}, {"ZAR"}, "CSV currency")
    print("PASS P2 CSV filters and executed BUY/SELL positions")


def numeric_overflow_check(base):
    payload = b'{"trade_date":"2026-11-26","fund":"KESCON","instrument_id":1,"side":"BUY","qty":1e309,"price":"2500","broker":"Kudu Securities"}'
    req = Request(base.rstrip("/") + "/trades", data=payload, headers={"Content-Type": "application/json"})
    before = ledger(base, date="2026-11-26", fund="KESCON")
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        status = response.code
        response.read()
    equal(ledger(base, date="2026-11-26", fund="KESCON"), before, "numeric overflow stores no trade")
    equal(status, 422, "numeric overflow rejected with validation response")
    print("PASS invalid numeric input is handled as HTTP 422")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed")
    for field in ("seed", "rebuilt", "dump"):
        seed.add_argument(field, type=Path)
    for command in ("api", "restart"):
        endpoint = commands.add_parser(command)
        endpoint.add_argument("--base", default="http://localhost:8000/api")
        endpoint.add_argument("--state", type=Path, required=True)
        if command == "api":
            endpoint.add_argument("--p1", action="store_true")
    extended = commands.add_parser("extended", help="mutates an isolated QA database")
    extended.add_argument("--base", default="http://localhost:8000/api")
    extended.add_argument("--db", type=Path, required=True)
    overflow = commands.add_parser("overflow")
    overflow.add_argument("--base", default="http://localhost:8000/api")
    args = parser.parse_args()
    if args.command == "seed":
        seed_checks(args.seed, args.rebuilt, args.dump)
    elif args.command == "api":
        api_checks(args.base, args.state, args.p1)
    elif args.command == "restart":
        restart_check(args.base, args.state)
    elif args.command == "extended":
        extended_checks(args.base, args.db)
    else:
        numeric_overflow_check(args.base)


if __name__ == "__main__":
    main()
