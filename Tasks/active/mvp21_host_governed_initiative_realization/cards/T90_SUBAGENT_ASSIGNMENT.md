# T90_SUBAGENT_ASSIGNMENT

```yaml
task_id: T90_SUBAGENT_ASSIGNMENT
parent_authority: Tasks/MVS_task_plan.md
phase: WP16
goal: Freeze write scopes and dependencies for the WP16 package.
non_goals:
  - Functional implementation
write_scope:
  - Tasks/active/mvp21_host_governed_initiative_realization/SUBAGENT_ASSIGNMENT.md
dependencies:
  - T00_AUTHORITY_FREEZE
success_criteria:
  - docs worker / OpenEmotion owner worker / proto_self worker / EgoCore worker / proof-observation worker scopes are explicit
verification_commands:
  - rg -n "docs worker|OpenEmotion owner worker|proto_self worker|EgoCore worker|proof/observation worker|T00|T10|T20|T30|T40|T50|T60|T70|T80|T90" Tasks/active/mvp21_host_governed_initiative_realization/SUBAGENT_ASSIGNMENT.md
rollback_point:
  - revert assignment sync only
```
