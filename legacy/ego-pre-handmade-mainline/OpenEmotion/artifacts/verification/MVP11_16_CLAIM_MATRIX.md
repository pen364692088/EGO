# MVP11_16_CLAIM_MATRIX.md

## Inconsistency header
- `MASTER_AUTONOMOUS_MISSION.md` default lock still points to MVP11.5/T07.3.
- `ROADMAP_STATE.json` claims MVP16 observation.
- `LATEST_HANDOFF.md` claims roadmap complete.
- Therefore any stage claim must be treated as provisional until code/runtime evidence is checked.

| Stage | Claimed goal | Document status | Code location(s) | Test location(s) | Artifact / report | Caveat / risk |
|---|---|---|---|---|---|---|
| MVP11.5 | Intent alignment / response sovereignty / checker enforcement | Docs and policy language present; mission file still default-locks here | `emotiond/response_intent_checker.py`, `emotiond/core.py:1022` | `tests/mvp11/test_mvp115_e2e_harness.py`, `tests/mvp11/test_no_report_v2_matrix.py` | `artifacts/mvp11_5/*`, testbot scenarios | One targeted harness passes, but another key matrix test currently fails at import/collection; natural runtime caveat still needs audit evidence |
| MVP12 | Developmental core sandbox under governance | Docs/tests present | `emotiond/developmental_core/*`, `emotiond/developmental_core/daemon_integration.py` | `tests/mvp12/test_developmental_core.py`, `tests/mvp12/test_replay.py` | `artifacts/mvp12/*` | Passing tests show module exists; main runtime wiring to audited core path still needs explicit proof |
| MVP13 | Persistent self-model with audit/revision continuity | Docs/tests/artifacts present | `emotiond/self_model/schema.py`, `persistence.py`, `updates.py`, `integration.py`; but audited core calls legacy path | `tests/mvp13/test_self_model_infra.py`, `tests/mvp13/test_integration.py`, `tests/mvp13/test_e2e_gate_b.py` | `artifacts/mvp13/*` | New package exists, but `core.py` currently evidences legacy `get_self_model_v0` usage |
| MVP14 | Endogenous drives + self-maintenance | Docs/tests/artifacts present | `emotiond/drives/*`, but audited core imports old `emotiond.drive_homeostasis` | `tests/mvp14/test_drive_infra.py`, `tests/mvp14/test_drive_integration.py`, `tests/mvp14/test_e2e_gate_b.py` | `artifacts/mvp14/*` | New drives package appears phase-local; main decision-chain influence not yet proven |
| MVP15 | Reflection / counterfactual / approval mechanism | Docs/tests/commit history present | `emotiond/reflection_engine/*`, but audited core calls `emotiond/reflection.py` | `tests/mvp15/test_reflection_infra.py` | commit `6901a7a`, no direct main-chain artifact found yet | Strong risk that new engine is implemented but not runtime-active in main chain |
| MVP16 | Open developmental self / long-horizon continuity | Docs/tests/observation docs present | `emotiond/developmental/*`, `tools/mvp16_daily_check.py` | `tests/mvp16/test_developmental.py` | `artifacts/mvp16/*`, `artifacts/mvp16-observation/day_1.md` | Daily check resets manager and reads defaults; current Day 1 PASS cannot be treated as long-horizon evidence |

## Version naming / snapshot drift
1. Roadmap history starts at MVP13 in `ROADMAP_STATE.json`; MVP11.5 and MVP12 are absent there despite audit scope.
2. Mission file default lock is stale against roadmap/handoff.
3. Runtime chain still references older MVP7.6 / MVP8 / old drive modules while roadmap claims MVP13–16 completion.
