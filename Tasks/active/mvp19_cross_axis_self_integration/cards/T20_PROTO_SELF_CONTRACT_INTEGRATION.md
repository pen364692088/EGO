# T20_PROTO_SELF_CONTRACT_INTEGRATION

```yaml
task_id: T20_PROTO_SELF_CONTRACT_INTEGRATION
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Connect selfhood_integration through a bounded proto_self_v2 contract.
non_goals:
  - Implement EgoCore runtime bridge
  - Grant any action authority
write_scope:
  - OpenEmotion/openemotion/proto_self_v2/*
  - OpenEmotion/tests/mvp19/test_selfhood_integration_proto_self_integration.py
read_scope:
  - Tasks/MVP19_task_plan.md
  - OpenEmotion/openemotion/selfhood_integration/*
dependencies:
  - T10_FORMAL_OWNER_PACKAGE
success_criteria:
  - proto_self_v2 consumes the frozen WP8~WP13 integration read surfaces
  - outputs stay proposal-only with behavioral_authority none
verification_commands:
  - pytest -q OpenEmotion/tests/mvp19/test_selfhood_integration_proto_self_integration.py
proof_required:
  - contract integration tests
rollback_point:
  - revert selfhood_integration proto-self changes only
subagent_ready: true
```

