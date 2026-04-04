# T10_FORMAL_OWNER_PACKAGE

```yaml
task_id: T10_FORMAL_OWNER_PACKAGE
parent_authority: Tasks/MVS_task_plan.md
phase: WP15
goal: Create the OpenEmotion initiative_self formal owner package under openemotion/.
non_goals:
  - Runtime wiring
  - Proactive send authority
write_scope:
  - OpenEmotion/openemotion/initiative_self/*
  - OpenEmotion/tests/mvp20/test_initiative_owner_infra.py
dependencies:
  - T00_AUTHORITY_FREEZE
success_criteria:
  - initiative owner package exists under openemotion/
  - owner state covers initiative, priority, commitment continuity, host-proactive candidate semantics, and initiative ledger
verification_commands:
  - pytest -q OpenEmotion/tests/mvp20/test_initiative_owner_infra.py
rollback_point:
  - revert initiative owner package only
```
