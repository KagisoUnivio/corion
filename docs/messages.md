# Agent messages and handoffs

Use the templates in the agent channel or send them directly to the orchestrator. The orchestrator can record shared decisions in the log below. Keep code and detailed reports in the owning paths and link to them from the message.

## Handoff order

| From | To | Send when | Include |
| --- | --- | --- | --- |
| Data | Backend, Reviewer, Orchestrator | Schema is verified | SQLite path, schema, quote units, row counts, known exceptions, reproducible import |
| Backend | Frontend, Reviewer, Orchestrator | P0 API runs against the seed | Branch or commit, startup command, base URL, routes exercised, test results |
| Frontend | Reviewer, Orchestrator | Live capture and ledger are ready | Branch or commit, startup command, live path exercised, gaps |
| Reviewer | Orchestrator and affected owner | A blocker is found or review is complete | Severity, reproduction, expected and actual behavior, test evidence, suggested fix |
| Any role | Orchestrator and affected roles | A data, contract, or integration assumption changes | Affected fields or paths, impact, proposed change, owner of next action |

## Ready or progress message

```text
From:
To:
Branch / commit:
Delivered:
Evidence (commands and observed results):
Pending or unverified:
Next action and owner:
```

## Blocker or decision request

```text
From:
To:
Priority and affected workflow:
Expected:
Observed and how to reproduce:
Workaround or proposed change:
Decision needed from:
```

## Decision log

| Topic | State | Owner |
| --- | --- | --- |
| Shared packet and proposed API details | Pending human review | Orchestrator |
| Branch-relative layout and integrated review path | Pending confirmation against existing worktrees | Orchestrator |
| Bond price basis, fractional quantity rules, and desk confirmation of provisional assumptions | Open | Orchestrator with the desk |

## Frontend handoff

Branch `feat/frontend`. Source is under the branch-relative `frontend/` product
path. The shared layout decision above is pending, so the files are uncommitted.

- Start the frontend from the product directory with `npm ci && npm run dev`.
  Open `http://localhost:5173/`. The default API is `http://localhost:8000/api`.
  Set `VITE_API_BASE_URL` to override it.
- Pass. `npm run build` on Node 18.19.1 with Vite 6.4.6.
- Pass. Rebuilt market data from `data/market_data.sql` using the converter and
  passed the isolated SQLite copy to Uvicorn as `DB_PATH`. The live API returned
  20 instruments. Chromium selected CPB (ID 4, ZAc), captured a KESCON BUY of
  100 shares at 2500 through Kudu Securities, and displayed DRAFT and
  ZAR 2,500.00. The UI displayed 26/11/2026 and sent 2026-11-26. Side and
  broker started empty and reset after capture. The matching KESCON API query
  returned trade #2 and the FYNBAL UI filter excluded it.
- Pass. Chromium showed the advisory price warning, advanced the trade to SENT,
  rejected a zero execution price, executed at 2550, displayed ZAR 2,550.00,
  and marked it DONE. A fresh Uvicorn process on port 8017 retrieved the same
  DONE trade and both prices from the same isolated database.
- Pass. Browser test-only response overrides exercised loading, an empty
  ledger, a missing close, and FastAPI string and validation-array details.
  The application uses live HTTP requests for the demo.
- CSV export and positions are outside this delivery. The observed backend
  has no routes for those outputs.
