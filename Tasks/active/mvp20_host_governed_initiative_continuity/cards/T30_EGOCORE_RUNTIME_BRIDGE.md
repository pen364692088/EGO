# T30_EGOCORE_RUNTIME_BRIDGE

```yaml
task_id: T30_EGOCORE_RUNTIME_BRIDGE
parent_authority: Tasks/MVS_task_plan.md
phase: WP15
goal: Inject initiative context into the formal runtime mainline and record gated initiative writeback.
non_goals:
  - Direct proactive send
  - Runtime authority transfer
write_scope:
  - EgoCore/app/runtime_v2/*
  - EgoCore/app/openemotion_adapter/*
  - EgoCore/tests/test_runtime_v2_proto_self_runtime.py
dependencies:
  - T20_PROTO_SELF_CONTRACT_INTEGRATION
success_criteria:
  - runtime summary includes initiative context in the formal mainline
  - writeback remains gated and proposal_only
verification_commands:
  - pytest -q EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k initiative
rollback_point:
  - revert initiative runtime bridge only
```
