# Codex Autopilot Meta-Control Plane v3 PLAN

## Steps

1. Create and verify GitHub Project issue `#69` as the operating task card.
2. Add `goal_control` to `.codex/project_contract.yaml`.
3. Add planner schema and proposal-only commands:
   - `goal-status`
   - `goal-refresh`
   - `plan-proposal`
   - `propose-ready-issues`
4. Make `run-loop` no-ready states produce candidate issue drafts rather than empty looping.
5. Ensure planner proposals cannot count as implementation evidence for closeout.
6. Add deterministic tests and run the local verification profile.
7. Commit, push, and close #69 only with evidence-first local closeout.

## Allowed Paths

- `.codex/project_contract.yaml`
- `scripts/**`
- `scripts/tests/**`
- `docs/codex/tasks/codex-autopilot-meta-control-v3/**`

## Forbidden Paths

- `EgoOperator/**`
- `legacy/ego-pre-handmade-mainline/**`
- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `artifacts/evidence_ledger/**`

## Rollback

Revert the contract, schema, script, tests, and this task directory. Close #69 as superseded/not planned if the goal-aware abstraction proves brittle or misleading.
