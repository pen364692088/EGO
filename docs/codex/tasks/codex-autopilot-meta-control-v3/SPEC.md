# Codex Autopilot Meta-Control Plane v3 SPEC

## Goal

Upgrade Codex Project Autopilot from a task-board loop into a goal-aware control plane:

- Sense: read GitHub Project, contract, dirty baseline, and recent run reports.
- Orient: classify ready, human-required, epic, unknown, high-impact, and blocked work.
- Plan: use a bounded planner backend for proposals when no ready issue exists or framing is unclear.
- Act: keep execution under project contract and single-issue gates.
- Verify: use verify profiles, scripted entrypoints, or reviewer gates.
- Close/Learn: write evidence-first closeout packets and emit follow-up issue/skill/contract proposals.

## Non-Goals

- Do not drive Codex TUI slash commands through keystroke automation.
- Do not treat `/goal` or `/plan` as a stable script API.
- Do not automatically mutate code or GitHub issues from planner output.
- Do not modify `EgoOperator/**`, legacy projects, `docs/PROGRAM_STATE_UNIFIED.yaml`, or `artifacts/evidence_ledger/**`.
- Do not let planner output satisfy implementation evidence or closeout evidence.

## Claim Ceiling

`Codex Autopilot goal-aware meta-control local workflow candidate pass`.

This does not prove full unattended autonomous development, stable productivity gain, product runtime efficacy, live autonomy, durable memory efficacy, or consciousness.
