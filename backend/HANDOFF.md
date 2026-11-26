# Backend handoff for Frontend, Reviewer, and Orchestrator

Branch `feat/backend`. The files use the repository-relative `backend/` product path. The shared guide asks the orchestrator to confirm the layout before the first commit.

## Startup

Run these commands from the `feat/backend` worktree root with Python 3.11 or later. On Ubuntu, install `python3-venv` if virtual environment creation reports that `ensurepip` is unavailable.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
corion_import_dir=$(mktemp -d)
python3 ../data/convert_market_data.py ../data/market_data.sql --output-dir "$corion_import_dir"
export DB_PATH="$corion_import_dir/market_data.sqlite"
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

Use `http://localhost:8000/api` from the frontend. CORS allows `http://localhost:5173`. In the integrated checkout, run the same commands from the repository root and use `data/` in place of `../data/`.

## Verification

The acceptance suite takes a disposable copy of the configured database for each test. Run it from the same directory and environment used for startup.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

| Check | Result |
| --- | --- |
| Fresh import and SQLite checks | Pass. 20 instruments, 616 prices from 2026-10-01 to 2026-11-13, integrity `ok`, zero foreign-key violations. |
| Backend acceptance suite | Pass. All 8 tests, covering readiness, reference and instrument lookup, CORS, four quote formulas, invalid inputs, filters, price warnings, sequential and concurrent status changes, CSV, and positions. |
| Live Uvicorn HTTP smoke | Pass. Health, reference and instrument reads, JSE capture at ZAR 2500.00, filtered retrieval, and retrieval after a full API process restart. |
| Browser walkthrough | Pending frontend integration. |

Bond capture uses all-in prices. The API returns the bond close for display and reports comparison unavailable until the close basis is confirmed. Futures consideration represents ZAR notional. Money uses two decimal places with half-even rounding. CSV uses the provisional trade response field names. Positions return `fund`, `instrument_id`, `instrument_code`, `currency`, and decimal-string `net_qty`.
