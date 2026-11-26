# Trade Ledger API contract

Review draft based on [projects.md](projects.md). Backend and Frontend should use the same contract revision. The human orchestrator approves shared changes before implementation teams adopt them.

## Transport and endpoints

The API base is `http://localhost:8000/api`. Allow the local Vite origin `http://localhost:5173`. JSON is used except for CSV export. Return arrays directly for list endpoints.

| Priority | Method | Path relative to base | Response |
| --- | --- | --- | --- |
| P0 | GET | `/health` | Database readiness. Proposed `200 {"status":"ok"}` when ready and `503` when unavailable. |
| P0 | GET | `/reference-data` | `200` with `funds` and `brokers` arrays |
| P0 | GET | `/instruments` | `200` with an array of instruments and their latest close metadata |
| P0 | GET | `/trades` | `200` with an array of trades |
| P0 | POST | `/trades` | `201` with the persisted DRAFT trade |
| P1 | PATCH | `/trades/{id}/status` | `200` with the updated trade |
| P2 | GET | `/trades/export` | `200` with CSV |
| P2 | GET | `/positions` | `200` with executed net quantities |

`GET /trades` and `GET /trades/export` accept optional `date=YYYY-MM-DD` and `fund=KESCON` parameters. Date defaults to the current date in `Africa/Johannesburg`. When supplied, fund narrows results. An empty result returns `[]` for the JSON ledger.

## Reference and instrument data

```json
{
  "funds": ["KESCON", "FYNBAL", "BAOGLB", "PROINC"],
  "brokers": ["Kudu Securities", "Impala Capital", "Springbok Stockbrokers"]
}
```

An instrument has integer `id`, string `code`, `name`, `asset_class`, `currency`, and `quote_unit`, plus `last_close` as a decimal string or null and `last_close_date` as an ISO date or null. Preserve source quote units in the response. Latest instrument closes are per instrument and independent of the trade form date.

## Trade capture

```json
{
  "trade_date": "2026-11-26",
  "fund": "KESCON",
  "instrument_id": 1,
  "side": "BUY",
  "qty": "100",
  "price": "2500",
  "broker": "Kudu Securities"
}
```

Send `trade_date` explicitly, prefilled with the current South African date. Require a valid ISO date, a known integer instrument ID, a configured fund and broker, and explicit `BUY` or `SELL`. Quantity and price are finite positive decimal strings. Futures quantities must represent whole contracts. Use [architecture](architecture.md) for the source quote mapping and consideration formulas.

Every trade response contains all capture fields and the following:

| Field | Type and meaning |
| --- | --- |
| `id` | Integer trade identifier |
| `instrument_code`, `currency` | Strings from instrument metadata |
| `status` | `DRAFT`, `SENT`, `EXECUTED`, or `DONE` |
| `executed_price` | Positive decimal string or null |
| `consideration` | Unsigned decimal string in instrument currency |
| `last_close`, `last_close_date` | Decimal string and ISO date, or null when unavailable. The selected close must be on or before the trade date. |
| `price_deviation_pct` | Decimal string in percentage points (for example `"6"` for 6%), or null when comparison is unavailable |
| `warning` | Advisory message string or null |

For comparable closes, compute absolute deviation and warn only above 5%. A missing, zero, or noncomparable close makes comparison unavailable and leaves an otherwise valid trade eligible for capture. Return an explanatory warning once P1 is present. Proposed P0 behavior is to include the response fields and use null for warning and deviation until P1 is enabled.

## Status changes

Advance one step at a time through `DRAFT → SENT → EXECUTED → DONE`. SENT records a manual status. Send `{"status":"SENT"}` or `{"status":"DONE"}` for those transitions. Send `{"status":"EXECUTED","executed_price":"2550"}` for execution. The executed price must be finite and positive. Keep the captured price and retain the executed price through DONE. Recompute consideration from the executed price and refresh the warning when execution-time comparison is implemented.

| HTTP status | Condition |
| --- | --- |
| 422 | Invalid input, unknown reference values, unsupported quote convention, or missing/invalid executed price for a legal execution transition |
| 404 | Unknown trade ID |
| 409 | Illegal status transition, including skipping or reversing |

FastAPI error bodies use `detail`, which may be a string or a validation array. The UI must handle both.

## Optional outputs

CSV filters mirror the ledger. Use ISO dates, include currency, and provisionally use trade response field names as headers. Confirm the final schema with back office.

Positions accept an optional fund filter. Group by fund and instrument, include only EXECUTED and DONE trades, and sum BUY quantity minus SELL quantity. The result represents net captured executions and excludes opening balances. Confirm the response fields with the orchestrator before wiring a positions UI.
