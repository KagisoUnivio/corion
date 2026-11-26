import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from . import market


def database_path() -> Path:
    if configured := os.getenv("DB_PATH"):
        return Path(configured).expanduser().resolve()
    roots = Path(__file__).resolve().parents
    for root in (roots[2], roots[3]):
        candidate = root / "data" / "market_data.sqlite"
        if candidate.is_file():
            return candidate
    return roots[2] / "data" / "market_data.sqlite"


@contextmanager
def database():
    try:
        # mode=rw refuses to create an empty database if the seed is missing.
        db = sqlite3.connect(database_path().as_uri() + "?mode=rw", uri=True)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("PRAGMA foreign_keys = ON")
                market.verify_schema(db)
                db.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY,
                        trade_date TEXT NOT NULL,
                        fund TEXT NOT NULL,
                        instrument_id INTEGER NOT NULL REFERENCES Instruments(InstrumentId),
                        side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                        qty TEXT NOT NULL,
                        price TEXT NOT NULL,
                        broker TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'DRAFT'
                            CHECK(status IN ('DRAFT', 'SENT', 'EXECUTED', 'DONE')),
                        executed_price TEXT,
                        CHECK((status IN ('EXECUTED', 'DONE')) = (executed_price IS NOT NULL))
                    )
                """)
                yield db
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise HTTPException(503, "Trade ledger database is unavailable") from exc
