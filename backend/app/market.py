import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation


def verify_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        SELECT InstrumentId, Code, Name, AssetClass, Exchange, Currency,
               QuoteUnit, ContractSize FROM Instruments LIMIT 0
    """)
    db.execute("SELECT InstrumentId, PriceDate, ClosePrice FROM DailyPrices LIMIT 0")


def instruments(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM Instruments ORDER BY Code, InstrumentId").fetchall()


def instrument(db: sqlite3.Connection, instrument_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM Instruments WHERE InstrumentId = ?", (instrument_id,)
    ).fetchone()


def latest_close(
    db: sqlite3.Connection, instrument_id: int, as_of: str = "9999-12-31"
) -> tuple[Decimal | None, str | None]:
    rows = db.execute("""
        SELECT ClosePrice, PriceDate FROM DailyPrices
        WHERE InstrumentId = ? AND PriceDate <= ? AND ClosePrice IS NOT NULL
        ORDER BY PriceDate DESC
    """, (instrument_id, as_of))
    for row in rows:
        try:
            close = Decimal(str(row["ClosePrice"]))
            day = date.fromisoformat(row["PriceDate"])
        except (InvalidOperation, TypeError, ValueError):
            continue
        if close.is_finite() and close > 0 and day.isoformat() == row["PriceDate"]:
            return close, row["PriceDate"]
    return None, None
