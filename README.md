# Corion Trade Ledger

A local trade-capture application built with React, FastAPI, and SQLite. It uses market data imported from the supplied SQL Server export. The API validates each trade, calculates consideration in the instrument's currency, and stores the trade so it survives a restart.

Use the browser to look up instruments and their latest closes, capture trades, filter today's ledger by fund, and advance trades through `DRAFT → SENT → EXECUTED → DONE`. The API also supports historical ledger queries, CSV export, and net executed positions.

## Run locally

Run the commands from the repository root. Use Python 3.11 or later with `venv`, and Node.js 22 or later with npm.

**Terminal 1 — API**

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

corion_db="${XDG_DATA_HOME:-$HOME/.local/share}/corion/market_data.sqlite"
mkdir -p "$(dirname "$corion_db")"
if [ ! -f "$corion_db" ]; then
  cp market_data.sqlite "$corion_db"
fi

DB_PATH="$corion_db" backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

The first run copies the checked-in seed to a writable location. Later runs reuse that copy and its trades. To start with a fresh ledger, give `DB_PATH` the absolute path to a separate copy of the seed.

Check readiness at [localhost:8000/api/health](http://localhost:8000/api/health). Interactive API documentation is available at [localhost:8000/docs](http://localhost:8000/docs).

**Terminal 2 — Web app**

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [localhost:5173](http://localhost:5173). The API allows that browser origin. If you change the API port, set `VITE_API_BASE_URL` when starting Vite, including the `/api` suffix.

## Walk through a trade

1. Keep today's date and select fund **KESCON**, instrument **MZT**, side **Buy**, and broker **Kudu Securities**.
2. Enter quantity **100** and price **2500**. MZT is quoted in South African cents (`ZAc`). Choose **Capture draft** and confirm that the ledger shows **DRAFT** and **ZAR 2,500.00**.
3. Switch the ledger filter to **FYNBAL**. The KESCON trade should disappear. Switch back to **KESCON** and reload the page to confirm that the trade is still present.
4. Choose **Mark sent**, enter **2550** as the executed price, then choose **Execute**. The row keeps the captured price of 2500 and shows executed consideration of **ZAR 2,550.00**. Choose **Mark done** to finish.

The app uses Johannesburg's calendar date. A price warning is expected for this example because the example price differs from the seed's reference close. The warning is advisory.

## Market data and pricing

The converter rebuilds the seed from the original SQL export. It preserves five missing closes as null, keeps the source-marked correction for a duplicate price, and excludes the truncated final price record. The supplied seed contains **20 instruments and 616 prices** from 1 October to 13 November 2026. [Import quality report](market_data_quality.md)

The backend uses decimal arithmetic, rounds consideration to two decimal places with half-even rounding, and uses the executed price once the trade reaches `EXECUTED`.

| Quote convention | Consideration | Verified example |
| --- | --- | --- |
| JSE equity in cents | Quantity × price ÷ 100 | 100 × 2500 ÷ 100 = ZAR 2,500.00 |
| USD equity | Quantity × price | 10 × 150.25 = USD 1,502.50 |
| Bond per 100 nominal | Nominal × price ÷ 100 | 100,000 × 98.5 ÷ 100 = ZAR 98,500.00 |
| ALSIZ26 in index points | Whole contracts × points × 10 | 2 × 75,000 × 10 = ZAR 1,500,000.00 notional |

Price warnings use the most recent valid close for the same instrument on or before the trade date. A deviation greater than 5% triggers a warning. Bond input is treated as all-in, and bond deviation is unavailable until the source close basis is confirmed.

## Useful API calls

```bash
curl -fsS http://localhost:8000/api/instruments
curl -fsS 'http://localhost:8000/api/trades?fund=KESCON'
curl -fsS 'http://localhost:8000/api/trades/export?fund=KESCON'
curl -fsS 'http://localhost:8000/api/positions?fund=KESCON'
```

The ledger and CSV export accept `date=YYYY-MM-DD` and default to today in Johannesburg. Positions aggregate executed and completed buys and sells by fund and instrument.

## Verify the project

Run the backend suite and frontend build from the repository root after installing the dependencies above.

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
DB_PATH="$PWD/market_data.sqlite" PYTHONPATH=backend \
  backend/.venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

The backend suite uses disposable copies of the seed. To rebuild and compare the import with the checked-in database, run the independent seed check.

```bash
corion_import_dir=$(mktemp -d)
python3 convert_market_data.py market_data.sql --output-dir "$corion_import_dir"
python3 review/tests/smoke.py seed market_data.sqlite \
  "$corion_import_dir/market_data.sqlite" "$corion_import_dir/market_data_sqlite.sql"
```

The [QA review](review/REVIEW.md) records independent API and browser evidence, including restart persistence, fund filtering, warning thresholds, and invalid state transitions.

## Assessment scope and known gaps

- The browser shows today's ledger. Use the API with an explicit date to retrieve a backdated trade.
- `SENT` is a manual status. Broker connectivity, authentication, and a full audit trail are outside the assessment scope.
- An unquoted JSON quantity of `1e309` returns HTTP 500. The expected response is HTTP 422, and no trade is stored. [QA reproduction](review/REVIEW.md#p0-finding-for-the-backend-owner)

[Backend](backend/) · [Frontend](frontend/) · [API contract](docs/api-contract.md) · [Independent checks](review/tests/)
