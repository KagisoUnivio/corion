from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from fastapi import HTTPException

from . import market


def quote_factor(instrument):
    asset = instrument["AssetClass"]
    exchange = instrument["Exchange"]
    currency = instrument["Currency"]
    unit = instrument["QuoteUnit"]
    if (asset, exchange, currency, unit) == ("EQUITY", "JSE", "ZAR", "ZAc"):
        return Decimal("0.01")
    if asset == "EQUITY" and (currency, unit) == ("USD", "USD"):
        return Decimal(1)
    if asset == "BOND" and unit == "PCT_NOMINAL":
        return Decimal("0.01")
    if (asset, exchange, currency, unit) == ("FUTURE", "SAFEX", "ZAR", "INDEX_POINTS"):
        if instrument["Code"] == "ALSIZ26" and instrument["ContractSize"] == 10:
            return Decimal(10)
    raise HTTPException(422, f"Unsupported quote convention for {instrument['Code']} ({unit})")


def decimal_text(value):
    value = format(value, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def trade_response(db, trade, instrument):
    close, close_date = market.latest_close(db, trade["instrument_id"], trade["trade_date"])
    price = Decimal(trade["executed_price"] or trade["price"])
    qty = Decimal(trade["qty"])
    with localcontext() as ctx:
        # Allow exact intermediate operations for the accepted request sizes.
        ctx.prec = 4096
        consideration = (qty * price * quote_factor(instrument)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        deviation, warning = None, None
        if close is None:
            warning = "Price comparison unavailable because there is no valid close on or before the trade date."
        elif instrument["AssetClass"] == "BOND":
            warning = "Price comparison unavailable because the bond close basis has not been confirmed."
        else:
            difference = abs(price - close)
            if difference > close * Decimal("0.05"):
                warning = "Price differs from the reference close by more than 5%."
            ctx.prec = 28
            deviation = decimal_text(difference * 100 / close)
    return {
        **dict(trade),
        "instrument_code": instrument["Code"],
        "currency": instrument["Currency"],
        "consideration": format(consideration, "f"),
        "last_close": decimal_text(close) if close is not None else None,
        "last_close_date": close_date,
        "price_deviation_pct": deviation,
        "warning": warning,
    }


def trades_for(db, day, fund):
    sql = "SELECT * FROM trades WHERE trade_date = ?"
    params = [day]
    if fund is not None:
        sql += " AND fund = ?"
        params.append(fund)
    return [
        trade_response(db, trade, market.instrument(db, trade["instrument_id"]))
        for trade in db.execute(sql + " ORDER BY id", params)
    ]
