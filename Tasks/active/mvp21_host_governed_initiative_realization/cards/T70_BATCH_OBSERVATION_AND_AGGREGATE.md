# T70_BATCH_OBSERVATION_AND_AGGREGATE

```yaml
task_id: T70_BATCH_OBSERVATION_AND_AGGREGATE
parent_authority: Tasks/MVS_task_plan.md
phase: WP16
goal: Promote MVP21 from a single controlled sample to repeated batch E5.
non_goals:
  - Maintenance closeout
write_scope:
  - OpenEmotion/scenarios/mvp21_observation_bank/*
  - OpenEmotion/tests/mvp21/*
  - OpenEmotion/tools/*
  - OpenEmotion/artifacts/mvp21/*
dependencies:
  - T60_CONTROLLED_OBSERVATION_SINGLE
success_criteria:
  - report_count >= 3
  - accepted_count == report_count
  - proposal_only_discipline_count == report_count
  - behavioral_authority_none_count == report_count
verification_commands:
  - pytest -q OpenEmotion/tests/mvp21/test_controlled_observation_batch.py
  - python3 OpenEmotion/tools/run_mvp21_controlled_observation_batch.py
rollback_point:
  - revert batch observation only
```
