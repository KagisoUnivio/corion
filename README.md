# Corion Trade Ledger

Corion Trade Ledger is a technical assessment project for capturing and tracking trades. The React frontend lets you look up instruments and their latest closes, capture a draft, filter today's trades by fund, and advance a trade through `DRAFT` → `SENT` → `EXECUTED` → `DONE`. The FastAPI backend validates trades, calculates consideration using the instrument's quote convention, and stores trades in SQLite. CSV export and net positions are available through the API.

## Run locally

Use Python 3.11 or later with `venv` and Node.js 22 or later with npm. Run the commands from the repository root in two terminals.

### 1. Start the API

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

The first run copies the checked-in market data into a writable local database. Subsequent runs reuse that database so trades survive restarts. The API creates the trades table on the first database request. Check readiness at [localhost:8000/api/health](http://localhost:8000/api/health) or explore endpoints at [localhost:8000/docs](http://localhost:8000/docs).

### 2. Start the frontend

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [localhost:5173](http://localhost:5173). Use `localhost` in the browser because the API allows that Vite origin. The frontend uses `http://localhost:8000/api` by default. Set `VITE_API_BASE_URL` when starting Vite if you run the API on a different port.

## Try a trade

1. Keep today's date and select fund `KESCON`, instrument `MZT`, side `BUY`, and broker `Kudu Securities`.
2. Enter quantity `100` and price `2500` in South African cents (`ZAc`). Choose **Capture draft**. The ledger shows consideration of `ZAR 2,500.00`.
3. Choose **Mark sent**, enter an executed price of `2550`, then choose **Execute**. Consideration updates to `ZAR 2,550.00`. Choose **Mark done** to finish the workflow.

The ledger uses the Johannesburg date. The seed contains historical closes, so a price warning can appear when you try this example. Bond prices are entered on an all-in basis, and the API skips the deviation comparison until the source close basis is confirmed. Futures consideration represents contract notional.

## Verify the project

From the repository root with the Python environment and frontend dependencies installed:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
DB_PATH="$PWD/market_data.sqlite" PYTHONPATH=backend \
  backend/.venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

The backend tests use disposable copies of the seed. To rebuild the market data from the source SQL into a fresh directory, run:

```bash
corion_import_dir=$(mktemp -d)
python3 convert_market_data.py market_data.sql --output-dir "$corion_import_dir"
```

| Path | Contents |
| --- | --- |
| [`backend/`](backend/) | FastAPI routes, trade calculations, SQLite access, and API tests |
| [`frontend/`](frontend/) | React trade capture form and daily ledger |
| [`market_data_quality.md`](market_data_quality.md) | Seed data and import findings |
| [`review/`](review/) | Independent review and smoke tests |
