import csv
import os
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.db import database_path
from app.main import app

TODAY = datetime.now(ZoneInfo("Africa/Johannesburg")).date().isoformat()


class TradeApiTest(unittest.TestCase):
    def setUp(self):
        seed = database_path()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "market.sqlite"
        shutil.copyfile(seed, self.path)
        # The configured source may be a live ledger. Reset only the test copy.
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE IF EXISTS trades")
        environment = patch.dict(os.environ, {"DB_PATH": str(self.path)})
        self.addCleanup(environment.stop)
        environment.start()
        self.client = self.enterContext(TestClient(app))

    def capture(self, **overrides):
        payload = {
            "trade_date": TODAY, "fund": "KESCON", "instrument_id": 1, "side": "BUY",
            "qty": "100", "price": "2500", "broker": "Kudu Securities",
        }
        return self.client.post("/api/trades", json=payload | overrides)

    def change(self, trade_id, status, **fields):
        return self.client.patch(f"/api/trades/{trade_id}/status", json={"status": status} | fields)

    def test_readiness_reference_and_instruments(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        reference = self.client.get("/api/reference-data").json()
        self.assertEqual(reference["funds"], ["KESCON", "FYNBAL", "BAOGLB", "PROINC"])
        self.assertEqual(len(reference["brokers"]), 3)
        instruments = {item["id"]: item for item in self.client.get("/api/instruments").json()}
        self.assertEqual(len(instruments), 20)
        self.assertEqual(instruments[1]["quote_unit"], "ZAc")
        self.assertEqual(instruments[1]["last_close_date"], "2026-11-13")
        self.assertLess(instruments[5]["last_close_date"], instruments[1]["last_close_date"])
        preflight = self.client.options("/api/trades", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(preflight.headers["access-control-allow-origin"], "http://localhost:5173")
        with patch.dict(os.environ, {"DB_PATH": str(self.path.with_suffix(".missing"))}):
            self.assertEqual(self.client.get("/api/health").status_code, 503)
            self.assertFalse(self.path.with_suffix(".missing").exists())

    def test_quote_conventions(self):
        cases = [
            (1, "100", "2500", "ZAR", "2500.00"),
            (15, "10", "150.25", "USD", "1502.50"),
            (11, "100000", "98.5", "ZAR", "98500.00"),
            (19, "2", "75000", "ZAR", "1500000.00"),
        ]
        for instrument, qty, price, currency, consideration in cases:
            with self.subTest(instrument=instrument):
                response = self.capture(instrument_id=instrument, qty=qty, price=price)
                self.assertEqual(response.status_code, 201, response.text)
                trade = response.json()
                self.assertEqual((trade["currency"], trade["consideration"]), (currency, consideration))

    def test_validation_stores_no_trade(self):
        for invalid in [
            {"side": None}, {"broker": None}, {"broker": "Other"}, {"fund": "OTHER"},
            {"instrument_id": -1}, {"instrument_id": 10**40}, {"instrument_id": "1"},
            {"qty": "0"}, {"qty": "-1"}, {"price": "NaN"}, {"price": "Infinity"},
            {"price": "1e9999999999999999999"}, {"price": 2500},
            {"instrument_id": 19, "qty": "1.25"}, {"trade_date": "2026-02-30"},
        ]:
            with self.subTest(invalid=invalid):
                self.assertEqual(self.capture(**invalid).status_code, 422)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE Instruments SET QuoteUnit='OTHER' WHERE InstrumentId=1")
        response = self.capture()
        self.assertEqual(response.status_code, 422)
        self.assertIn("Unsupported quote convention", response.json()["detail"])
        self.assertEqual(self.client.get("/api/trades").json(), [])

    def test_ledger_filters_and_persistence(self):
        trade = self.capture().json()
        self.assertEqual(trade["status"], "DRAFT")
        self.capture(fund="FYNBAL")
        self.capture(trade_date="2026-10-02")
        with TestClient(app) as restarted:
            self.assertEqual(len(restarted.get("/api/trades").json()), 2)
            self.assertEqual(restarted.get("/api/trades", params={
                "date": TODAY, "fund": "KESCON",
            }).json(), [trade])
            self.assertEqual(restarted.get("/api/trades?fund=PROINC").json(), [])
            self.assertEqual(restarted.get("/api/trades?date=20261002").status_code, 422)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT typeof(qty), typeof(price) FROM trades LIMIT 1").fetchone(),
                             ("text", "text"))

    def test_price_warning_uses_historical_valid_close(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE DailyPrices SET ClosePrice=100 WHERE InstrumentId=1 AND PriceDate='2026-10-01'")
            db.execute("UPDATE DailyPrices SET ClosePrice=0 WHERE InstrumentId=1 AND PriceDate='2026-10-02'")
        for price, deviation in [("95", "5"), ("105", "5"), ("94", "6"), ("106", "6")]:
            with self.subTest(price=price):
                trade = self.capture(trade_date="2026-10-02", price=price).json()
                self.assertEqual(trade["last_close_date"], "2026-10-01")
                self.assertEqual(trade["price_deviation_pct"], deviation)
                self.assertEqual(trade["warning"] is not None, deviation == "6")
        missing = self.capture(trade_date="2026-09-30").json()
        self.assertIsNone(missing["last_close"])
        self.assertIsNone(missing["price_deviation_pct"])
        self.assertIn("unavailable", missing["warning"])
        bond = self.capture(trade_date="2026-11-13", instrument_id=11).json()
        self.assertIsNotNone(bond["last_close"])
        self.assertIsNone(bond["price_deviation_pct"])
        self.assertIn("basis", bond["warning"])

    def test_status_progression(self):
        trade_id = self.capture().json()["id"]
        self.assertEqual(self.change(999, "SENT").status_code, 404)
        self.assertEqual(self.change(trade_id, "EXECUTED").status_code, 409)
        self.assertEqual(self.change(trade_id, "SENT").status_code, 200)
        self.assertEqual(self.change(trade_id, "DRAFT").status_code, 409)
        for fields in ({}, {"executed_price": "0"}, {"executed_price": "NaN"}):
            self.assertEqual(self.change(trade_id, "EXECUTED", **fields).status_code, 422)
        execution = self.change(trade_id, "EXECUTED", executed_price="2550").json()
        done = self.change(trade_id, "DONE").json()
        for trade in (execution, done):
            self.assertEqual(trade["price"], "2500")
            self.assertEqual(trade["executed_price"], "2550")
            self.assertEqual(trade["consideration"], "2550.00")
        self.assertEqual(done["status"], "DONE")

    def test_concurrent_transition_cannot_advance_twice(self):
        trade_id = self.capture().json()["id"]
        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(lambda _: self.change(trade_id, "SENT").status_code, range(2)))
        self.assertEqual(sorted(statuses), [200, 409])

    def test_csv_and_positions(self):
        for fund, side, qty in [("KESCON", "BUY", "100"), ("KESCON", "SELL", "2.5"),
                                ("FYNBAL", "BUY", "50")]:
            trade_id = self.capture(fund=fund, side=side, qty=qty).json()["id"]
            self.change(trade_id, "SENT")
            self.change(trade_id, "EXECUTED", executed_price="2500")
        self.change(trade_id, "DONE")
        self.change(self.capture(qty="999").json()["id"], "SENT")
        self.capture(trade_date="2026-10-02")
        positions = self.client.get("/api/positions").json()
        self.assertEqual({item["fund"]: item["net_qty"] for item in positions},
                         {"KESCON": "97.5", "FYNBAL": "50"})
        self.assertEqual(len(self.client.get("/api/positions?fund=KESCON").json()), 1)
        response = self.client.get("/api/trades/export", params={"date": TODAY, "fund": "KESCON"})
        self.assertIn("text/csv", response.headers["Content-Type"])
        rows = list(csv.DictReader(response.text.splitlines()))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["trade_date"] == TODAY and row["fund"] == "KESCON"
                            and row["currency"] == "ZAR" for row in rows))
