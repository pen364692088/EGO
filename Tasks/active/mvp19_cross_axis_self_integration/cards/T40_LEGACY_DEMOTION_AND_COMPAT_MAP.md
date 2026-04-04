# T40_LEGACY_DEMOTION_AND_COMPAT_MAP

```yaml
task_id: T40_LEGACY_DEMOTION_AND_COMPAT_MAP
parent_authority: Tasks/MVS_task_plan.md
phase: WP14
goal: Freeze the upstream read-only map and demote any cross-axis integration fallback surfaces to reference-only.
non_goals:
  - Delete upstream owner files
  - Use upstream owner packages as WP14 fallback owner
write_scope:
  - OpenEmotion/tools/verify_mvp19_mainline_wiring.py
  - OpenEmotion/tests/mvp19/test_mainline_reference_demotion.py
  - Tasks/active/mvp19_cross_axis_self_integration/LEGACY_REFERENCE_REGISTER.md
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
  - upstream authority surfaces are explicitly registered as read-only to WP14
  - no-second-truth verifier exists
verification_commands:
  - pytest -q OpenEmotion/tests/mvp19/test_mainline_reference_demotion.py
proof_required:
  - demotion tests and verifier
rollback_point:
  - revert WP14 legacy demotion only
subagent_ready: true
```

