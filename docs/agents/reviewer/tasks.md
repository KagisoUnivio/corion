# Reviewer agent tasks

Read the [agent guide](../../AGENTS.md), [project brief](../../projects.md), [API contract](../../api-contract.md), and [testing checklist](../../testing.md). Use the `feat/reviewer` worktree. Confirm the integrated review path with the orchestrator. The worktree is named `reviewer/` and the brief uses `review/`.

## Review order

- [ ] Independently compute the four expected considerations and review the risk of wrong money, invalid quote conventions, fabricated data, and missing validation.
- [ ] Inspect the import and compare the data handoff with SQLite. Check null close handling and that comparison uses a per-instrument date cutoff.
- [ ] Review available branch diffs for API compatibility, persistence, explicit side/broker, date handling, and status transitions. Send P0 blockers to the orchestrator promptly.
- [ ] Run a real-data smoke test through the API and UI, including reload/restart and the fund filter. Test warning and transition cases for any P1 feature present.
- [ ] Publish `REVIEW.md` and any independent smoke checks in the review-owned path. Report severity, reproduction steps, expected and actual results, and the suggested fix. Edit review artifacts only.

## Done

Deliver a pass/fail checklist and remaining risks before the demo. Label pending or unverified cases and include the branch or commit, command, and observed result for each finding.
