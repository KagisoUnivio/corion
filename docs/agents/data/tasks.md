# Data agent tasks

Read the [agent guide](../../AGENTS.md), [architecture](../../architecture.md), and [testing checklist](../../testing.md). Use the `feat/data` worktree and publish the verified market schema to Backend first.

## P0

- [ ] Review the existing [converter](../../../data/convert_market_data.py) and [quality report](../../../data/market_data_quality.md) against the original SQL Server export. Preserve the original input.
- [ ] Rebuild in a fresh output directory and verify the baseline counts, date range, foreign keys, and integrity. Record duplicates, corrected prices, null closes, and exclusions with the source evidence.
- [ ] Publish `data/DATA_NOTES.md` with the actual artifacts and reproduction command, schema keys, currency and quote-unit combinations, contract sizes, and representative closes by instrument. Document KWP and the truncated source row.
- [ ] Confirm the per-instrument lookup, including the date cutoff for trade warnings. Flag missing close history and any uncertain quotation or bond comparison basis. Preserve source prices and metadata.
- [ ] Send Backend the schema, database location, and verified examples. Coordinate any artifact layout differences with the orchestrator before merge.

## Done

The generated SQLite database opens in DB Browser, market rows are queryable, and another agent can reproduce the import. Report the checks you ran and their results in the [handoff format](../../messages.md).
