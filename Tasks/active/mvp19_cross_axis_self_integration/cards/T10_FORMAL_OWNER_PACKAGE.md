# T10_FORMAL_OWNER_PACKAGE

```yaml
task_id: T10_FORMAL_OWNER_PACKAGE
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Create the OpenEmotion selfhood_integration formal owner package under openemotion/.
non_goals:
  - Implement live integrated behavior
  - Reopen upstream owner packages
write_scope:
  - OpenEmotion/openemotion/selfhood_integration/*
  - OpenEmotion/tests/mvp19/test_selfhood_integration_owner_infra.py
read_scope:
  - Tasks/MVP19_task_plan.md
  - Tasks/MVP13_task_plan.md
  - Tasks/MVP14_task_plan.md
  - Tasks/MVP15_task_plan.md
  - Tasks/MVP16_task_plan.md
  - Tasks/MVP17_task_plan.md
  - Tasks/MVP18_task_plan.md
dependencies:
  - T00_AUTHORITY_FREEZE
success_criteria:
  - selfhood integration owner package exists under openemotion/
  - owner state covers integration, cross-axis priority, proposal conflict, balances, integrated tendency proposal, arbitration hints, and integration ledger
  - owner schema/state are replayable and audit-friendly
verification_commands:
  - pytest -q OpenEmotion/tests/mvp19/test_selfhood_integration_owner_infra.py
proof_required:
  - owner package tests
rollback_point:
  - revert selfhood_integration owner package only
subagent_ready: true
```

