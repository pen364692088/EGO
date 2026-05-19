# Codex Cross-Project Devloop Toolkit v1 PLAN

## Milestone 1: Task Source And Contract

- Create GitHub issue #17 and keep it in Project `Status=In Progress`.
- Add a repo-local project contract under `.codex/project_contract.yaml`.
- Record protected paths, allowed mutation paths, verify profiles, task classification rules, and observation classes.

## Milestone 2: L0/L1 Autopilot Script

- Add `scripts/codex_project_autopilot.py`.
- Implement JSON commands: `doctor`, `report`, `plan-next`, `classify-issue`, and `run-loop --dry-run`.
- Reuse `scripts/github_project_task.py` for GitHub CLI access.
- Keep v1 read-only and dry-run only; no automatic implementation, closeout, commit, or Project mutation.

## Milestone 3: Tests And Skill Routing

- Add `scripts/tests/test_codex_project_autopilot.py`.
- Add `.agents/skills/codex-project-autopilot/SKILL.md`.
- Update `AGENTS.md` routing so cross-project board/autopilot requests use the generic skill first, while EgoOperator log/comment repair still uses `ego-operator-devloop`.

## Milestone 4: Verification And Closeout

- Run targeted tests and `git diff --check`.
- Run real dry-run commands against the current Project.
- Commit/push only scoped paths.
- Comment on #17 with conservative L0/L1 local workflow result.

## Rollback

Delete the project contract, generic autopilot script/tests, skill, task docs, and revert the `AGENTS.md` routing hunk.
