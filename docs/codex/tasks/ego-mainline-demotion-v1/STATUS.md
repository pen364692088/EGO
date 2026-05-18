# Ego Mainline Demotion v1 - STATUS

## Current Milestone

- name: `ego_handmade_first_transition`
- owner: `Codex`
- state: `local_transition_pass`
- type: `repo_transition`

## Authority Snapshot

- Previous formal default lane: `subject_system_v1_governed_proactivity`
- New default operator lane: `ego_handmade_first_transition`
- Legacy projects: `legacy/ego-pre-handmade-mainline/EgoCore`, `legacy/ego-pre-handmade-mainline/OpenEmotion`, `legacy/ego-pre-handmade-mainline/ego_desktop_lab`

## Claim Boundary

This task can claim only `Ego_handmade-first repo transition / legacy demotion recorded`. It does not prove stable real user benefit, runtime efficacy, live autonomy, durable long-term memory, or consciousness.

## Decisions

- `Ego_handmade` is the default implementation surface for operator experience work.
- Legacy code remains preserved and inspectable.
- Major future actions still require Stage Card confirmation.
- Ordinary implementation details should be handled directly under the `Ego_handmade-first` contract.

## Evidence

- `python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py Ego_handmade/human_operator_trial.py scripts/codex/program_state_common.py scripts/codex/route_convergence_common.py scripts/codex/verify_route_convergence.py scripts/codex/verify_mainline_clarity.py scripts/codex/check_program_state_integrity.py` - pass.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests` - pass, `63 passed`.
- `python3 scripts/codex/generate_program_state_views.py` - regenerated program-state mirrors.
- `python3 scripts/codex/generate_route_convergence_views.py` - regenerated route/hygiene views.
- `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check` - pass.
- `python3 scripts/codex/verify_route_convergence.py` - pass, active default `ego-mainline-demotion-v1`.
- `python3 scripts/codex/verify_mainline_clarity.py` - pass, active default `ego-mainline-demotion-v1`.
- `python3 Ego_handmade/real_use_gate.py --out Ego_handmade/artifacts/real_use_gate/demotion_v1` - pass, `local_candidate_pass`.
- `python3 Ego_handmade/human_operator_trial.py --out Ego_handmade/artifacts/human_operator_trial/demotion_v1 --provider-mode none` - `needs_human_trial`; this records the next human-observable gate and does not prove live operator benefit.
- `git diff --cached --check` - pass for the staged transition diff. A full worktree diff-check over `legacy/` also observes pre-existing unstaged legacy log/artifact whitespace and is not used as the publish gate.

## Open Gate

- Real provider / human continuous-use trial remains pending. This task records the repo transition and legacy demotion only; it does not claim stable real user benefit or runtime efficacy.
