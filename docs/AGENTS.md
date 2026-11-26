# Corion Trade Ledger agent guide

Start with [projects.md](projects.md). This guide and the files linked below are review drafts. The human orchestrator owns changes to shared requirements and approves any implementation choices that affect multiple agents.

## Assignments

| Role | Observed worktree and branch | Owned product path | Task file |
| --- | --- | --- | --- |
| Data | `data/` on `feat/data` | `data/` | [Tasks](agents/data/tasks.md) |
| Backend | `backend/` on `feat/backend` | `backend/` | [Tasks](agents/backend/tasks.md) |
| Frontend | `frontend/` on `feat/frontend` | `frontend/` | [Tasks](agents/frontend/tasks.md) |
| Reviewer | `reviewer/` on `feat/reviewer` | Review report and independent tests | [Tasks](agents/reviewer/tasks.md) |

The worktree paths identify checkout locations. The owned product paths describe the intended integrated tree. Confirm your branch and repository root with `git branch --show-current` and `git rev-parse --show-toplevel`. The existing data artifacts sit directly in the data worktree root. Resolve the branch-relative layout with the orchestrator before committing or moving files. See [architecture](architecture.md).

## Working agreement

1. Read your role's checklist, the [API contract](api-contract.md), and the [acceptance tests](testing.md) before implementation. If you start from a separate worktree, read this packet from the parent checkout or the shared baseline once it is committed.
2. Work in your owned paths. Send shared edits and interface changes to the orchestrator for approval. Use small, coherent commits on your role branch.
3. Deliver P0 first. Start P1 when market data, capture, calculation, and filtered retrieval work together. Treat CSV export and positions as P2.
4. Use [messages](messages.md) to report handoffs and blockers with a concrete next action. When an assumption changes, identify the affected roles and the relevant contract section.
5. Record commands, results, and any unrun tests. Include blockers and known gaps in the handoff. The orchestrator merges the changes and calls time.
