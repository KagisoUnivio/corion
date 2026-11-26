# Backend agent tasks

Read the [agent guide](../../AGENTS.md), [API contract](../../api-contract.md), [architecture](../../architecture.md), and [testing checklist](../../testing.md). Use the `feat/backend` worktree.

## P0

- [ ] Build FastAPI models, routes, and tests against the shared contract. Put market-schema queries behind an adapter and connect it to the data agent's verified SQLite schema.
- [ ] Implement database readiness, funds and brokers, and instrument lookup with per-instrument latest closes. Configure CORS for the local Vite origin.
- [ ] Implement trade capture and date/fund-filtered retrieval. Validate reference values, finite positive decimals, and whole futures contracts. Create the trade table idempotently and preserve trades across restarts.
- [ ] Use Decimal for server-side consideration and persist trade price and quantity as decimal text where practical. Validate quote conventions from source metadata, preserve original captured price, and return meaningful errors for unsupported conventions.
- [ ] Verify P0 against the real imported market database and message Frontend and Reviewer with the startup and test commands.

## P1 and P2

- [ ] Implement price warnings using an on-or-before close and the strict 5% threshold. Handle unavailable or noncomparable closes.
- [ ] Implement sequential status transitions, including the executed price and recalculated consideration. Add tests for illegal transitions and execution requirements.
- [ ] If P0 and P1 are working and time remains, implement CSV and executed positions using the optional contract.

## Done

The API starts locally, reads the imported database, and creates and retrieves trades. Record test evidence, actual startup commands, and any deferred work in the [handoff](../../messages.md).
