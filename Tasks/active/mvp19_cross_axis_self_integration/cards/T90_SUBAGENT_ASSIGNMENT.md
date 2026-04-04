# T90_SUBAGENT_ASSIGNMENT

```yaml
task_id: T90_SUBAGENT_ASSIGNMENT
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Keep the WP14 subagent routing table synchronized with the authority package.
non_goals:
  - Implement any phase code
write_scope:
  - Tasks/active/mvp19_cross_axis_self_integration/SUBAGENT_ASSIGNMENT.md
read_scope:
  - Tasks/MVP19_task_plan.md
  - Tasks/active/mvp19_cross_axis_self_integration/cards/*
dependencies:
  - T00_AUTHORITY_FREEZE
success_criteria:
  - assignment table matches current cards and write scopes
  - initial worker mapping matches the frozen supervisor contract
verification_commands:
  - rg -n "docs worker|OpenEmotion owner worker|proto_self worker|EgoCore worker|proof/observation worker|T00|T10|T20|T30|T40|T50|T60|T70|T80|T90" Tasks/active/mvp19_cross_axis_self_integration/SUBAGENT_ASSIGNMENT.md
proof_required:
  - docs consistency only
rollback_point:
  - revert subagent assignment only
subagent_ready: true
```
