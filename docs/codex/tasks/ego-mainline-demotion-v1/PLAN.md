# Ego Mainline Demotion v1 - PLAN

## Stage Card

- stage: `ego_handmade_first_transition`
- hypothesis: `Ego_handmade` should become the repo default operator path because it preserves natural-language understanding before gates, while old projects remain useful only as reference/fallback.
- change surface: repo rules, entry docs, route/state/evidence views, and directory migration.
- rollback: revert this task commit, or move `legacy/ego-pre-handmade-mainline/{EgoCore,OpenEmotion,ego_desktop_lab}` back to repo root and revert docs/state/evidence updates.

## Steps

1. Move old projects into `legacy/ego-pre-handmade-mainline/`.
2. Update AGENTS, README, quickstart, and playbook so new work starts from `Ego_handmade`.
3. Add this task record and a bounded evidence entry.
4. Update route/state scripts and regenerate derived views.
5. Run `Ego_handmade` syntax/tests plus route/state verification.
6. Commit and push scoped changes.

## Verification

- `python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py Ego_handmade/human_operator_trial.py`
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests`
- `python3 scripts/codex/generate_program_state_views.py`
- `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check`
- `python3 scripts/codex/verify_route_convergence.py`
- `python3 scripts/codex/verify_mainline_clarity.py`
- scoped `git diff --check`
