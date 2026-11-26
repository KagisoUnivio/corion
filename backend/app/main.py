import csv
import io
from datetime import datetime
from decimal import Decimal, localcontext
from typing import get_args
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import market
from .db import database
from .ledger import decimal_text, quote_factor, trade_response, trades_for
from .models import (
    Broker, Fund, Instrument, Position, StatusChange, Trade, TradeCapture,
    TradeDate, positive_decimal,
)

app = FastAPI(title="Corion Trade Ledger")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)

NEXT_STATUS = {"DRAFT": "SENT", "SENT": "EXECUTED", "EXECUTED": "DONE"}
JOHANNESBURG = ZoneInfo("Africa/Johannesburg")


def ledger_date(day):
    return day or datetime.now(JOHANNESBURG).date().isoformat()


@app.get("/api/health")
def health():
    with database():
        return {"status": "ok"}


@app.get("/api/reference-data")
def reference_data():
    return {"funds": get_args(Fund), "brokers": get_args(Broker)}


@app.get("/api/instruments", response_model=list[Instrument])
def list_instruments():
    with database() as db:
        result = []
        for row in market.instruments(db):
            close, close_date = market.latest_close(db, row["InstrumentId"])
            result.append(Instrument(
                id=row["InstrumentId"], code=row["Code"], name=row["Name"],
                asset_class=row["AssetClass"], currency=row["Currency"],
                quote_unit=row["QuoteUnit"],
                last_close=decimal_text(close) if close is not None else None,
                last_close_date=close_date,
            ))
        return result


@app.get("/api/trades", response_model=list[Trade])
def list_trades(date: TradeDate | None = None, fund: Fund | None = None):
    with database() as db:
        return trades_for(db, ledger_date(date), fund)


@app.post("/api/trades", status_code=201, response_model=Trade)
def create_trade(request: TradeCapture):
    if not -(2**63) <= request.instrument_id < 2**63:
        raise HTTPException(422, "Unknown instrument ID")
    with database() as db:
        instrument = market.instrument(db, request.instrument_id)
        if instrument is None:
            raise HTTPException(422, "Unknown instrument ID")
        quote_factor(instrument)
        qty = Decimal(request.qty)
        if instrument["AssetClass"] == "FUTURE" and qty != qty.to_integral_value():
            raise HTTPException(422, "Futures quantities must be whole contracts")
        trade_id = db.execute("""
            INSERT INTO trades (trade_date, fund, instrument_id, side, qty, price, broker)
            VALUES (:trade_date, :fund, :instrument_id, :side, :qty, :price, :broker)
        """, request.model_dump()).lastrowid
        trade = db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        return trade_response(db, trade, instrument)


@app.patch("/api/trades/{trade_id}/status", response_model=Trade)
def change_status(trade_id: int, request: StatusChange):
    if not -(2**63) <= trade_id < 2**63:
        raise HTTPException(404, "Trade not found")
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        trade = db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if trade is None:
            raise HTTPException(404, "Trade not found")
        if NEXT_STATUS.get(trade["status"]) != request.status:
            raise HTTPException(409, f"Cannot move trade from {trade['status']} to {request.status}")
        executed_price = trade["executed_price"]
        if request.status == "EXECUTED":
            try:
                executed_price = positive_decimal(request.executed_price)
            except ValueError as exc:
                raise HTTPException(422, "EXECUTED requires a finite positive executed_price") from exc
        elif request.executed_price is not None:
            raise HTTPException(422, "executed_price can only be supplied for EXECUTED")
        db.execute(
            "UPDATE trades SET status = ?, executed_price = ? WHERE id = ?",
            (request.status, executed_price, trade_id),
        )
        updated = db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        return trade_response(db, updated, market.instrument(db, updated["instrument_id"]))


@app.get("/api/trades/export", response_class=Response)
def export_trades(date: TradeDate | None = None, fund: Fund | None = None):
    day = ledger_date(date)
    with database() as db:
        trades = trades_for(db, day, fund)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(Trade.model_fields))
    writer.writeheader()
    writer.writerows(trades)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="trades-{day}.csv"'},
    )


@app.get("/api/positions", response_model=list[Position])
def list_positions(fund: Fund | None = None):
    with database() as db:
        sql = """
            SELECT fund, instrument_id, side, qty FROM trades
            WHERE status IN ('EXECUTED', 'DONE')
        """
        params = ()
        if fund is not None:
            sql += " AND fund = ?"
            params = (fund,)
        net = {}
        with localcontext() as ctx:
            ctx.prec = 4096
            for row in db.execute(sql, params):
                key = row["fund"], row["instrument_id"]
                qty = Decimal(row["qty"])
                net[key] = net.get(key, Decimal(0)) + (qty if row["side"] == "BUY" else -qty)

        result = []
        for (position_fund, instrument_id), qty in sorted(net.items()):
            instrument = market.instrument(db, instrument_id)
            result.append(Position(
                fund=position_fund, instrument_id=instrument_id,
                instrument_code=instrument["Code"], currency=instrument["Currency"],
                net_qty=decimal_text(qty),
            ))
        return result
