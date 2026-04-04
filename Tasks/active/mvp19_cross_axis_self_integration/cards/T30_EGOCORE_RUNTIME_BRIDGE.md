# T30_EGOCORE_RUNTIME_BRIDGE

```yaml
task_id: T30_EGOCORE_RUNTIME_BRIDGE
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Inject bounded selfhood integration context into the current EgoCore runtime mainline.
non_goals:
  - Direct reply / tool / transport authority
  - Live autonomy or transport expansion
write_scope:
  - EgoCore/app/runtime_v2/*
  - EgoCore/app/openemotion_adapter/*
  - EgoCore/tests/test_runtime_v2_proto_self_runtime.py
read_scope:
  - Tasks/MVP19_task_plan.md
  - OpenEmotion/openemotion/proto_self_v2/*
dependencies:
  - T20_PROTO_SELF_CONTRACT_INTEGRATION
success_criteria:
  - runtime_v2 injects the frozen selfhood integration context
  - self_integration_writeback remains gated and proposal-only
verification_commands:
  - pytest -q EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k selfhood_integration
proof_required:
  - runtime bridge tests
rollback_point:
  - revert selfhood integration runtime bridge only
subagent_ready: true
```

