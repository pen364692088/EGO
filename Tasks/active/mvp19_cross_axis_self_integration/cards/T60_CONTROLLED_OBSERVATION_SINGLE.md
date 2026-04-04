# T60_CONTROLLED_OBSERVATION_SINGLE

```yaml
task_id: T60_CONTROLLED_OBSERVATION_SINGLE
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Obtain the first controlled mainline single-sample E4 for selfhood integration proposal-only writeback.
non_goals:
  - Batch stability proof
  - Maintenance closeout
write_scope:
  - OpenEmotion/tools/run_mvp19_controlled_observation.py
  - OpenEmotion/tests/mvp19/test_controlled_observation.py
  - OpenEmotion/artifacts/mvp19/*
read_scope:
  - Tasks/MVP19_task_plan.md
dependencies:
  - T50_CAUSAL_VALIDATION
success_criteria:
  - self_integration_writeback_gate allow_writeback observed
  - behavioral_authority none preserved
  - single controlled observation pass
verification_commands:
  - pytest -q OpenEmotion/tests/mvp19/test_controlled_observation.py
  - python3 OpenEmotion/tools/run_mvp19_controlled_observation.py
proof_required:
  - V4/E4 single observation artifact
rollback_point:
  - revert selfhood integration single-observation changes only
subagent_ready: true
```

