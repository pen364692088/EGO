---
name: "ego-operator-devloop"
description: "Use for EgoOperator human-trial repair loops, GitHub issue comments with test logs, Project task closeout, and regressions around file/web_fetch/approval/memory gates. This skill routes comment/log evidence through the EgoOperator devloop packet, fast target verification, full verification, real-provider smoke gating, and GitHub Project closeout without replacing GitHub Issues or repo authority."
---

# EgoOperator Devloop

Use this skill when an EgoOperator task involves human-trial logs, GitHub issue comments, file path/tool approval failures, or deciding whether to close a narrow EgoOperator issue.

## Workflow

1. Read the relevant GitHub issue/comment or user-provided log first. If needed, build a packet:
   `python3 scripts/ego_operator_devloop.py packet --log-file <log> --candidate-issue '#<n>'`
2. Classify the result as one of: close current issue, repair current issue, or split residual UX backlog.
3. For repairs, add or update a deterministic fake-LLM regression before changing runtime behavior.
4. Run the fast loop:
   `python3 scripts/ego_operator_devloop.py verify target`
5. After the fix, run the closeout loop:
   `python3 scripts/ego_operator_devloop.py verify full`
6. Ask for or inspect real-provider smoke evidence before closing an issue that depends on human-observable behavior.
7. Close a passed GitHub Project issue with:
   `python3 scripts/github_project_task.py closeout --issue <n> --status Done --comment-file <file>`

## Boundaries

- GitHub Issue remains the task entity; Project `Status` remains the board state.
- Do not update `docs/PROGRAM_STATE_UNIFIED.yaml` or evidence ledger for local devloop-only work.
- Do not claim real-provider pass from `verify target` or `verify full`; those are local workflow checks only.
- If a residual issue is not part of the current acceptance gate, split it instead of dragging a passed mechanism issue.

## Pairing

- Pair with `ego-bugfix-root-cause` for runtime bugs or regressions.
- Pair with `ego-implement-milestone` when the user supplies a locked implementation plan.
- Prefer this skill over broad cleanup when the user says a test result is in a GitHub comment.
