# EgoOperator Human Operator Trial v2 - STATUS

## Current Milestone

- name: `human_operator_trial_v2`
- owner: `Codex`
- state: `local_protocol_ready__real_provider_unavailable`
- type: `human_observation_gate`

## Authority Snapshot

- active workstream: `ego_operator_first_transition`
- runtime path: `EgoOperator/agent_base.py`
- trial harness: `EgoOperator/human_operator_trial.py`
- historical reference: `docs/codex/tasks/ego-handmade-human-operator-trial-v1/`
- claim ceiling: `EgoOperator human-operator trial local observation pass`

## Acceptance

- v2 task source exists and is the current EgoOperator human-trial task.
- v1 handmade task remains reference-only and is not rewritten.
- v2 report schema writes JSON and Markdown with `EgoOperator` naming.
- scripted trial can run against the current runtime and record provider availability truthfully.
- NoLLM/fallback output is reported as `real_provider_unavailable`, not as natural-understanding pass.
- static, test, route, and mainline clarity gates pass.

## Current Result

Trial v2 protocol and scripted runner are implemented. The local scripted run completed with `provider_mode=none`, so the result is `real_provider_unavailable`, not a human-observation pass.

## Evidence

- `python3 -m py_compile EgoOperator/human_operator_trial.py` - pass.
- `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_human_operator_trial.py` - pass, `9 passed`.
- `python3 EgoOperator/human_operator_trial.py --out EgoOperator/artifacts/human_operator_trial/v2_latest --run-scripted --auto-approve-writes` - pass, status `real_provider_unavailable`, provider `none`, observations `18`.
- `python3 -m py_compile EgoOperator/agent_base.py EgoOperator/memory_system.py EgoOperator/real_use_gate.py EgoOperator/human_operator_trial.py` - pass.
- `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests` - pass, `65 passed`.
- `python3 scripts/codex/generate_program_state_views.py` - pass.
- `python3 scripts/codex/generate_route_convergence_views.py` - pass.
- `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check` - pass.
- `python3 scripts/codex/verify_route_convergence.py` - pass, active default `ego-operator-human-operator-trial-v2`.
- `python3 scripts/codex/verify_mainline_clarity.py` - pass, active default `ego-operator-human-operator-trial-v2`.
- `git diff --check -- README.md docs/MAINLINE_QUICKSTART.md EgoOperator docs/PROGRAM_STATE_UNIFIED.yaml docs/STATUS.md docs/codex/tasks/TASK_LANE_INDEX.md docs/REPO_HYGIENE_POLICY.md docs/REPO_SURFACE_MAP.md docs/codex/tasks/ego-operator-human-operator-trial-v2 scripts/codex/route_convergence_common.py scripts/codex/verify_route_convergence.py scripts/codex/verify_mainline_clarity.py legacy/ego-pre-handmade-mainline/EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml legacy/ego-pre-handmade-mainline/OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` - pass.

## Next Action

Run the v2 scripted trial with a real provider key. If the key is unavailable in the current shell, record the unavailable state and rerun from the operator environment that has the provider configured.
