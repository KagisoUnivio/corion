# Frontend agent tasks

Read the [agent guide](../../AGENTS.md), [API contract](../../api-contract.md), and [testing checklist](../../testing.md). Use the `feat/frontend` worktree.

## P0

- [ ] Build a single-page React/Vite trading desk against the shared contract. Load funds, brokers, and real instruments through the API, and show the instrument currency and quote unit.
- [ ] Build a draft trade form and today's ledger with a fund filter. Start side and broker unselected and clear both after successful capture.
- [ ] Display dates as DD/MM/YYYY and send ISO dates. Use the South African trade date for today's view. Render server consideration with two displayed decimals and the currency.
- [ ] Handle loading, empty results, missing closes, and errors. Render both string and array forms of the FastAPI error detail.
- [ ] Run the integrated flow against the live API and imported data. Disable development fixtures for the demo.

## P1 and P2

- [ ] Render advisory price warnings and the available status action. Require executed price at execution and display the updated consideration from the server.
- [ ] Add an export or positions UI only if those API features are available and time remains.

## Done

A user can capture a real-instrument trade and find it in the filtered ledger from the UI. Record the live workflow exercised, actual startup command, and gaps in the [handoff](../../messages.md).
