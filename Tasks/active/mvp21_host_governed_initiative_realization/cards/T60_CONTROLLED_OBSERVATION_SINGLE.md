# T60_CONTROLLED_OBSERVATION_SINGLE

```yaml
task_id: T60_CONTROLLED_OBSERVATION_SINGLE
parent_authority: Tasks/MVS_task_plan.md
phase: WP16
goal: Capture the first controlled runtime-mainline realization observation at V4/E4.
non_goals:
  - Batch stability claim
  - Maintenance closeout
write_scope:
  - OpenEmotion/tests/mvp21/*
  - OpenEmotion/tools/*
  - OpenEmotion/artifacts/mvp21/*
dependencies:
  - T50_CAUSAL_VALIDATION
success_criteria:
  - initiative_realization_writeback_gate = allow_writeback
  - behavioral_authority_none = true
  - single controlled observation passes
verification_commands:
  - pytest -q OpenEmotion/tests/mvp21/test_controlled_observation.py
  - python3 OpenEmotion/tools/run_mvp21_controlled_observation.py
rollback_point:
  - revert single observation only
```
