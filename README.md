# Corion Trade Ledger

A small app for recording trades and viewing the daily ledger. The frontend is React, the API is FastAPI, and trades are saved in SQLite. The market data comes from the SQL export supplied with the assessment.

## Run it locally

You'll need Python 3.11+ and Node.js 22+. Run these commands from the repo root.

Start the API in one terminal.

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

Start the frontend in another terminal.

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [localhost:5173](http://localhost:5173). The [API docs](http://localhost:8000/docs) are on port 8000. The database copy created on the first run is reused, so your trades are still there after a restart.

## Try a trade

Leave the date set to today. Select KESCON, MZT, Buy, and Kudu Securities. Enter a quantity of 100 and a price of 2500, then click **Capture draft**. MZT is quoted in cents, so the ledger should show **ZAR 2,500.00**.

Click **Mark sent**, enter 2550 as the executed price, and click **Execute**. The amount should change to **ZAR 2,550.00**. You can then mark the trade done. Use the fund filter to see which trades belong to each fund.

The browser shows today's trades in Johannesburg time. You can query another date, export CSV, or view net positions through the API.

## Market data

The checked-in database has 20 instruments and 616 prices. The import keeps missing closes as null and records the source rows it corrected or skipped. See the [import notes](market_data_quality.md).

The API calculates consideration from the instrument's quote unit. A trade price more than 5% away from the last valid close on or before the trade date gets a warning. Bond prices are entered all-in and skipped for that comparison until the close basis is confirmed. Futures amounts are contract notional.

To rebuild the database in a separate directory, run the importer from the repo root.

```bash
python3 convert_market_data.py market_data.sql --output-dir "$(mktemp -d)"
```

## Tests

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
DB_PATH="$PWD/market_data.sqlite" PYTHONPATH=backend \
  backend/.venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

The backend tests use a copy of the seed database. See the [QA notes](review/REVIEW.md) for the browser checks and API smoke tests.
