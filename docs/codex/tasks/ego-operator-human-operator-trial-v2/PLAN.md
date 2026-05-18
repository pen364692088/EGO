# EgoOperator Human Operator Trial v2 - PLAN

## Do Not Do

- Do not clean broad docs or legacy project folders.
- Do not modify legacy `EgoCore`, `OpenEmotion`, or `ego_desktop_lab` code.
- Do not rewrite historical `ego-handmade-human-operator-trial-v1` task docs.
- Do not promote generated trial artifacts into the formal evidence ledger.
- Do not count NoLLM/fallback output as natural-understanding proof.

## Execution Steps

1. Create the v2 task source under `docs/codex/tasks/ego-operator-human-operator-trial-v2/`.
2. Upgrade `EgoOperator/human_operator_trial.py` to v2 naming and add a scripted runner that uses the current `EgoOperator` runtime.
3. Keep old `ego-handmade-human-operator-trial-v1` as reference-only.
4. Run static and targeted regression gates.
5. Run `human_operator_trial.py --run-scripted`.
6. If a real provider key is unavailable, record `real_provider_unavailable` and keep the next action as a real-provider rerun.
7. If real-provider observations pass, report only local observation pass and use the result for the next feature/experience decision.

## Verification

Required:

```bash
python3 -m py_compile EgoOperator/agent_base.py EgoOperator/memory_system.py EgoOperator/real_use_gate.py EgoOperator/human_operator_trial.py
TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests
python3 scripts/codex/verify_route_convergence.py
python3 scripts/codex/verify_mainline_clarity.py
```

Trial:

```bash
python3 EgoOperator/human_operator_trial.py --out EgoOperator/artifacts/human_operator_trial/v2_latest --run-scripted --auto-approve-writes
```

## Rollback

Revert this task directory, the v2 trial harness changes, and route/status updates. Generated files under `EgoOperator/artifacts/human_operator_trial/` are ignored runtime artifacts and can be deleted without affecting tracked state.
