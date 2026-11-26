# Testing and acceptance

Use this checklist with the [project brief](projects.md), [API contract](api-contract.md), and [architecture](architecture.md). Unit tests may use synthetic cases. The integrated smoke test and demo use imported market data. Run checks that write trades against an isolated copy of the database.

## P0 acceptance

| Area | Case | Expected |
| --- | --- | --- |
| Data | Rebuild and query the supplied seed | 20 instruments, 616 daily prices, ISO date range 2026-10-01 to 2026-11-13, integrity `ok`, and zero foreign-key violations |
| Data | Read the instrument list | Real IDs, currency and quote units, and each instrument's latest valid close and date |
| Money | 100 JSE shares at 2500 cents | ZAR 2500.00 |
| Money | 10 USD shares at 150.25 | USD 1502.50 |
| Money | 100000 nominal of a bond at 98.5 | 98500.00 in instrument currency |
| Money | 2 ALSI contracts at 75000 points, multiplier 10 | ZAR 1500000.00 notional |
| Validation | Missing side/broker, unknown fund/broker/instrument, zero/negative/nonfinite quantity or price, fractional futures contracts, invalid date, or unsupported quote convention | API returns 422 and stores no trade. Unsupported conventions have explicit error detail. |
| Capture | Submit a valid trade | API returns 201 and DRAFT. The ledger shows the trade with currency and server-calculated consideration. |
| Ledger | List trades with omitted date, then filter by date and fund | Omitted date uses South African today. Filters return only matching rows. Empty JSON results are `[]`. |
| Persistence | Restart the backend on the same test database | The captured trade is still retrievable |
| UI | Open and submit the form | Side and broker start empty and reset after successful submission. Dates display as DD/MM/YYYY and submit as ISO. |
| UI | Simulate an HTTP or validation error, an empty list, and a missing close | Detail displays for string and array forms. Loading, empty, and missing-close states are readable. |

## P1 acceptance

| Area | Case | Expected |
| --- | --- | --- |
| Warning | Close 100, trade at 105 or 95 | No threshold warning |
| Warning | Close 100, trade at 106 or 94 | Advisory warning and 6% deviation. The otherwise valid trade is accepted. |
| Warning | Missing, zero, or noncomparable close | Comparison unavailable. No fabricated price and no rejection of an otherwise valid trade. |
| Warning | Price history includes a close after the trade date | Compare with the latest valid close on or before the trade date, or report unavailable |
| Status | DRAFT → SENT → EXECUTED → DONE | Each step succeeds with a valid request. SENT records a manual status. |
| Status | DRAFT → EXECUTED, reverse a step, execute without a positive price, or update an unknown trade | 409 for an illegal transition, 422 for an invalid execution request from SENT, and 404 for an unknown ID |
| Status | Capture 100 shares at 2500 cents, execute at 2550 | Original price stays 2500. Executed price stays 2550 through DONE. Consideration becomes ZAR 2550.00. |

If P2 is implemented, verify that CSV honors date and fund filters and includes ISO dates and currency. Check positions with BUY and SELL executions in multiple funds and verify that DRAFT and SENT contribute zero.

## Live smoke test

1. Rebuild a fresh database with the command in [architecture](architecture.md). Start the backend with `DB_PATH` pointing to this copy and start Vite using the implementation's startup commands.
2. Verify API health, reference data, and instrument results. Pick a returned JSE equity and record its ID and quote unit.
3. In the UI, capture a KESCON BUY for 100 units at 2500 cents with Kudu Securities. Verify DRAFT and ZAR 2500.00 in the ledger.
4. Query `GET /api/trades?fund=KESCON&date=YYYY-MM-DD` with the submitted date and find the same trade. Switch to a different fund in the UI and verify that the trade is excluded.
5. Restart the API against the same test database and confirm persistence. If P1 is implemented, advance through the legal transitions and test the executed consideration.

## Record results

Record the branch or commit, database source, command or UI action, expected result, actual result, and status for each case. Use Pass, Fail, Blocked, or Not run. Keep independent reviewer evidence in `REVIEW.md` and route blockers through [messages](messages.md).
