# Codex Cross-Project Devloop Toolkit v1 SPEC

## Goal

Build a reversible L0/L1 Codex autopilot control plane that can read a project contract, inspect GitHub Project tasks, classify execution readiness, and produce bounded dry-run plans across projects.

## Non-Goals

- Do not implement unattended code modification in v1.
- Do not replace GitHub Issues, Project v2, repo authority docs, or evidence ledgers.
- Do not modify `EgoOperator/**`, legacy projects, `docs/PROGRAM_STATE_UNIFIED.yaml`, or `artifacts/evidence_ledger/**`.
- Do not close human-observation or high-impact route/state/evidence issues automatically.

## Allowed Paths

- `.codex/project_contract.yaml`
- `.agents/skills/codex-project-autopilot/**`
- `AGENTS.md`
- `scripts/**`
- `scripts/tests/**`
- `docs/codex/tasks/codex-cross-project-devloop-toolkit-v1/**`

## Acceptance Gate

- GitHub Project issue #17 tracks this work as `In Progress`.
- A project contract exists and keeps EGO-specific paths/rules out of generic script logic.
- `scripts/codex_project_autopilot.py` supports `doctor`, `report`, `plan-next`, `classify-issue`, and dry-run `run-loop`.
- Unit tests cover contract loading, classification, dry-run non-mutation, structured stop reasons, and non-EGO path independence.
- Real dry-run commands complete without mutating GitHub Project state.

## Claim Ceiling

`Codex cross-project autopilot L0/L1 local workflow candidate pass`.

This cannot prove unattended autonomous development, stable efficiency gains, EgoOperator human-trial success, runtime efficacy, live autonomy, durable memory efficacy, or consciousness.
