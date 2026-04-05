# T20_PROTO_SELF_CONTRACT_INTEGRATION

```yaml
task_id: T20_PROTO_SELF_CONTRACT_INTEGRATION
parent_authority: Tasks/MVS_task_plan.md
phase: WP16
goal: Connect initiative_realization to proto_self_v2 through a bounded, versioned, proposal-only contract.
non_goals:
  - EgoCore runtime bridge
  - Delivery / transport execution
write_scope:
  - OpenEmotion/openemotion/proto_self_v2/*
  - OpenEmotion/tests/mvp21/test_realization_proto_self_integration.py
dependencies:
  - T10_FORMAL_OWNER_PACKAGE
success_criteria:
  - proto_self_v2 reads realization context through one formal consumer path
  - outputs remain proposal_only with behavioral_authority none
verification_commands:
  - pytest -q OpenEmotion/tests/mvp21/test_realization_proto_self_integration.py
rollback_point:
  - revert proto_self realization integration only
```
