# Trade Ledger architecture

The local React/Vite desk calls FastAPI over HTTP. FastAPI validates and calculates trades, then reads market data and persists trades in the same SQLite database. The data converter takes the original SQL Server export and produces the SQLite seed and its quality report.

| Component | Responsibility |
| --- | --- |
| React/Vite | Trade form, instrument lookup, date/fund ledger, and display of consideration, warnings, and status |
| FastAPI | HTTP validation, reference choices, read queries, trade commands, calculations, and status transitions |
| SQLite | Imported instruments and daily prices, plus the backend-owned trade table |
| Data converter | Repeatable parsing, documented source repairs and exclusions, generated SQLite database and SQL |

## Market data and storage

The current seed is [market_data.sqlite](../data/market_data.sqlite), produced by [convert_market_data.py](../data/convert_market_data.py). A read-only check found 20 instruments and 616 price rows dated 2026-10-01 through 2026-11-13. SQLite returned `ok` for integrity and zero foreign-key violations. The [quality report](../data/market_data_quality.md) records source exceptions.

| Table | Columns and keys |
| --- | --- |
| `Instruments` | `InstrumentId` primary key, `Code`, `Name`, `AssetClass`, `Exchange`, `Currency`, `QuoteUnit`, `ContractSize` |
| `DailyPrices` | `InstrumentId` and `PriceDate` composite primary key, `ClosePrice`, `AccruedPer100`, `Source`. `InstrumentId` references `Instruments`. |

Use `data/market_data.sqlite` as the current repository-relative default and support an explicit `DB_PATH`. Enable SQLite foreign keys per connection and parameterize SQL values. Keep market tables read-only in the app. Store the captured trade fields, status, and nullable executed price. Keep trade decimals as exact text where practical. Create the trade table idempotently. Commit each trade creation or status change atomically, and check the current status within the write so concurrent requests cannot both advance the same transition.

For the instrument list, select the latest valid close independently for each instrument. For a trade, use that instrument's most recent valid dated close on or before its trade date. A usable close is finite and positive. The warning also requires comparable quote units and price basis. Use nulls for missing close data, and retain available market data for display when comparison is unavailable.

## Calculation rules

| Verified source metadata | Consideration |
| --- | --- |
| `EQUITY`, JSE, ZAR, `ZAc` | Quantity × price ÷ 100 in ZAR |
| `EQUITY`, USD, `USD` | Quantity × price in USD |
| `BOND`, `PCT_NOMINAL` | Nominal × price ÷ 100 in instrument currency |
| `FUTURE`, SAFEX, ZAR, `INDEX_POINTS`, contract size 10 for ALSIZ26 | Whole contracts × points × 10 in ZAR notional |

Reject unsupported metadata with an explicit error. Calculate unsigned consideration using Decimal, retaining precision until the two-decimal display. Side determines position direction. Keep any totals currency-specific. For the MVP, treat bond input as all-in. Compare it to a source close only when the basis is confirmed comparable, and leave accrued interest treatment for desk confirmation. Effective consideration uses captured price in DRAFT and SENT and executed price in EXECUTED and DONE.

## Integration and startup

The existing `data/`, `backend/`, `frontend/`, and `reviewer/` locations are separate Git worktree roots. The brief describes paths within the integrated product tree. Confirm intended commit-relative paths, including `review/` versus `reviewer/`, before the first merge. The orchestrator merges data, backend, frontend, then reviewer and records exact import, startup, and test commands in the project README.

Run the following commands from the parent checkout to generate an isolated copy in a fresh output directory.

```bash
corion_import_dir=$(mktemp -d)
python3 data/convert_market_data.py data/market_data.sql --output-dir "$corion_import_dir"
```

Use the generated database as `DB_PATH` for isolated integration tests. Preserve the ledger database once trades exist. The proposed local ports are 8000 for FastAPI and 5173 for Vite. Authentication, broker connectivity, commissions, a full audit trail, and deployment are deferred.
