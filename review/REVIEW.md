# Corion Trade Ledger QA review

**P0 fails one API validation case.** Live capture, money, fund filtering, browser reload and restart persistence passed. P1 and the available P2 API features passed the cases below.

## Reviewed revisions

The data, backend and frontend worktrees were all based on `92a3032`. The product code and seed were in local worktree files at review time. I reviewed the files directly because the branches had no committed diffs yet.

| Relevant file | SHA-256 prefix |
| --- | --- |
| Backend `app/main.py` | `1f13d77dc786` |
| Backend `app/models.py` | `40a95a60e120` |
| Frontend `src/main.jsx` | `ad4064c8bfc7` |
| Shipped market database | `d5a4d252cb68` |

## P0 finding for the backend owner

| Finding | Reproduction | Expected | Observed | Suggested fix |
| --- | --- | --- | --- | --- |
| A malformed numeric quantity produces an internal server error | On the live API, use the supplied `overflow` check. It posts a valid capture payload with unquoted `"qty":1e309`. | HTTP 422 with client-readable `detail` and no stored trade | HTTP 500 with plain text `Internal Server Error`. Before/after ledger reads confirm no trade was stored. Ordinary numeric `100` and decimal strings `"NaN"` and `"Infinity"` return 422. | Keep strict decimal-string validation. Return a JSON-safe validation error payload by dropping or normalizing its raw input and context. Rerun `overflow` and the P0 smoke. |

The API log shows FastAPI’s validation exception already contains an error at `body.qty`. Its default response handler then tries to serialize the raw input as JSON. The parsed float is infinite and Starlette’s JSON serialization rejects it.

## Acceptance results

| Priority | Case | Result | Evidence |
| --- | --- | --- | --- |
| P0 | Import, schema, quality handoff and replay | Pass | Rebuilt independently from the source export. Shipped SQLite, fresh SQLite and fresh SQL replay match row for row. Each has 20 instruments and 616 prices spanning 2026-10-01 to 2026-11-13, integrity `ok`, zero foreign-key violations and five null closes. |
| P0 | Close metadata | Pass | Live instrument list has 20 real instruments. NMR falls back to 5141 on 2026-11-06 after five null closes. KWP’s latest valid row is 4570 on 2026-11-12. The source’s truncated KWP row on 2026-11-13 was omitted, and HVB’s corrected 33646 row was retained. |
| P0 | Four considerations | Pass | Independent Decimal calculations below match the four live HTTP 201 responses, including currency and DRAFT status. |
| P0 | Explicit terms, invalid input and unknown convention | Pass except finding above | Missing side or broker, invalid side, unknown references, bad dates, zero/negative/nonfinite decimal strings and fractional contracts returned 422. Unsupported quote fixture returned 422 with explicit detail. Rejected submissions left the ledger unchanged. |
| P0 | Today, date/fund filters and persistence | Pass | Omitted date included the day’s KESCON trades. Filtering another date or fund returned `[]`. Uvicorn PID 185939 was stopped and PID 186515 retrieved the same trade ID and status from the same database. |
| P0 | Browser capture and error states | Pass | Chromium captured a real MZT KESCON BUY with Kudu Securities. The request used ISO date, the form used DD/MM/YYYY, the ledger showed DRAFT and ZAR 2,500.00, and side/broker were empty initially and after submit. PROINC excluded the trade, reload restored it and a direct API query found the same trade ID. A delayed live response exercised loading. Controlled response interception exercised both error detail shapes and the missing-close state. |
| P0 | Local origin | Pass | An OPTIONS preflight to the API returned 200 with `Access-Control-Allow-Origin: http://localhost:5173`. The isolated browser runs used a temporary Vite proxy. |
| P1 | Threshold, cutoff and unavailable comparisons | Pass | Direct API tested 95%, 105%, 94% and 106% of MZT’s 17101 close on 2026-11-05. Only the 6% deviations warned. NMR on 2026-11-09 used 5141 from 2026-11-06. Pre-history and zero-close cases returned unavailable comparisons and still captured. The bond basis case suppressed deviation and warned. |
| P1 | Status and effective price | Pass | API and browser advanced DRAFT → SENT → EXECUTED → DONE. DRAFT → EXECUTED and the reverse transition returned 409. Omitted/zero executed price returned 422 from SENT. An unknown ID returned 404. Captured 2500 and executed 2550 were retained through DONE and consideration moved to ZAR 2550.00. Competing DRAFT → SENT requests produced one 200 and one 409. |
| P2 | CSV and positions API | Pass | CSV returned only the chosen date/fund, ISO dates and currency. Executed BUY 12 and SELL 5 produced net 7, another fund produced net 4 and DRAFT/SENT were excluded. |

The backend owner’s suite passed all 8 cases with `python3 -m unittest discover -s tests -v` from the backend product directory using the seed as `DB_PATH`. The frontend’s `npm run build -- --outDir <temp-dir>` completed successfully.

## Independent expected values

| Instrument and quote unit | Calculation | Expected |
| --- | --- | --- |
| MZT, ZAc | 100 × 2500 ÷ 100 | ZAR 2500.00 |
| NWT, USD | 10 × 150.25 | USD 1502.50 |
| R2032X, PCT_NOMINAL | 100000 × 98.5 ÷ 100 | ZAR 98500.00 |
| ALSIZ26, INDEX_POINTS | 2 × 75000 × 10 | ZAR 1500000.00 notional |

## Reproduction

Commands below run from the reviewer worktree. The QA runs used backend ports 18080 and 18081 and Vite ports 15173 and 15174 because the standard ports were already in use. The example commands for the browser assume the standard local ports and a Playwright install. The browser fixture starts from a database with PROINC empty for today. Run state-changing checks sequentially on a fresh QA copy.

```bash
corion_qa_dir=$(mktemp -d)
python3 ../data/convert_market_data.py ../data/market_data.sql --output-dir "$corion_qa_dir"
python3 review/tests/smoke.py seed ../data/market_data.sqlite \
  "$corion_qa_dir/market_data.sqlite" "$corion_qa_dir/market_data_sqlite.sql"
```

Start the backend from `../backend/backend` with its declared dependencies and the absolute path to the rebuilt DB. Start Vite from `../frontend/frontend` with `npm run dev`.

```bash
DB_PATH=/absolute/path/to/market_data.sqlite python3 -m uvicorn app.main:app --port 8000
```

Run the acceptance scripts from the reviewer worktree. Restart the backend on the same DB between `api` and `restart`. The `extended` command adds two synthetic instruments and a zero close to the test database, so run it after the seed and real-data cases.

```bash
python3 review/tests/smoke.py api --state "$corion_qa_dir/state.json" --p1
python3 review/tests/smoke.py restart --state "$corion_qa_dir/state.json"
CHECK_P1=1 node review/tests/browser.cjs
python3 review/tests/smoke.py extended --db "$corion_qa_dir/market_data.sqlite"
python3 review/tests/smoke.py overflow
```

Use `--base`, `FRONTEND_URL` and `API_URL` to select isolated local ports. Set `PLAYWRIGHT_MODULE` to an existing Playwright module path if it is installed outside the review worktree.

## Remaining risks and handoff

- Bond input is provisionally all-in. The desk still needs to confirm that basis and comparability with source closes. ALSI is shown as contract notional. The desk still needs to confirm rounding and fractional equity/nominal levels.
- The import evidence covers the supplied export and deterministic corrections. The source owner can provide the missing KWP close in a complete export.
- Browser checks exercised a fixed same-day path. A Johannesburg midnight rollover was not run. The handoff uses `review/` inside `feat/reviewer` provisionally, pending confirmation of the integrated directory.
