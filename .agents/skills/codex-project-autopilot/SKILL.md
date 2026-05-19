---
name: "codex-project-autopilot"
description: "Use for cross-project Codex task-board automation, GitHub Project backlog scanning, unattended/bounded devloop planning, sweeping Todo issues, or deciding what Codex should do next from a Project board. This generic skill reads a project contract first and uses the Codex autopilot scripts for report, plan-next, classification, and dry-run loops. It does not replace project-specific skills such as ego-operator-devloop."
---

# Codex Project Autopilot

Use this skill when the user asks Codex to work from a task board, run semi-autonomously, sweep Todo/In Progress issues, or build/operate a cross-project devloop.

## Workflow

1. Read the project contract:
   `python3 scripts/codex_project_autopilot.py doctor`
2. Inspect the current board:
   `python3 scripts/codex_project_autopilot.py report`
3. Select a candidate without mutation:
   `python3 scripts/codex_project_autopilot.py plan-next`
4. For unattended/batch requests, start with:
   `python3 scripts/codex_project_autopilot.py run-loop --dry-run --max-issues 3 --max-minutes 10`
5. Only move from dry-run to implementation when the selected issue is ready, local authority is clear, and the current project contract permits that autonomy level.

## Stop Conditions

Stop instead of acting when:

- No project contract exists.
- The issue is classified as `human_required`, `aggregate`, `parked`, `supporting`, `high_impact`, `blocked`, or `unknown`.
- The worktree has unsafe dirty changes outside the contract's allowed mutation paths.
- The action would modify program state, evidence ledger, protected runtime paths, credentials, or external service settings.
- The required verification profile is missing.

## Pairing

- Pair with project-specific skills after selection. In EGO, EgoOperator human-trial logs, GitHub comments, file/web_fetch/approval/memory regressions, and closeout still use `ego-operator-devloop`.
- Pair with `ego-reflective-quality-gate` for high-risk agent/autopilot architecture or repeated failure.
- Pair with `ego-review-against-acceptance` before claiming done.

## Claim Boundary

This skill can coordinate a bounded task-board devloop. It cannot prove full unattended autonomous development, stable productivity gains, product runtime efficacy, durable memory efficacy, live autonomy, or consciousness.
