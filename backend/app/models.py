import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints, StrictInt

Fund = Literal["KESCON", "FYNBAL", "BAOGLB", "PROINC"]
Broker = Literal["Kudu Securities", "Impala Capital", "Springbok Stockbrokers"]
Status = Literal["DRAFT", "SENT", "EXECUTED", "DONE"]
IsoDate = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]


def validate_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use a valid YYYY-MM-DD date")
    date.fromisoformat(value)
    return value


def positive_decimal(value: str) -> str:
    if not isinstance(value, str) or len(value) > 1000 or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value
    ):
        raise ValueError("Use a finite positive decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Use a finite positive decimal string") from exc
    if number <= 0 or abs(number.adjusted()) > 1000:
        raise ValueError("Use a positive decimal in the supported magnitude range")
    return value


DecimalText = Annotated[str, BeforeValidator(positive_decimal)]
TradeDate = Annotated[IsoDate, BeforeValidator(validate_date)]


class TradeCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: TradeDate
    fund: Fund
    instrument_id: StrictInt
    side: Literal["BUY", "SELL"]
    qty: DecimalText
    price: DecimalText
    broker: Broker


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    executed_price: str | None = None


class Instrument(BaseModel):
    id: int
    code: str
    name: str
    asset_class: str
    currency: str
    quote_unit: str
    last_close: str | None
    last_close_date: str | None


class Trade(TradeCapture):
    id: int
    instrument_code: str
    currency: str
    status: Status
    executed_price: str | None
    consideration: str
    last_close: str | None
    last_close_date: str | None
    price_deviation_pct: str | None
    warning: str | None


class Position(BaseModel):
    fund: Fund
    instrument_id: int
    instrument_code: str
    currency: str
    net_qty: str
