# T40_LEGACY_DEMOTION_AND_COMPAT_MAP

```yaml
task_id: T40_LEGACY_DEMOTION_AND_COMPAT_MAP
parent_authority: Tasks/MVS_task_plan.md
phase: WP15
goal: Demote historical proactive substrate and roadmap materials to reference-only / host-substrate-only without creating a second truth source.
non_goals:
  - New runtime functionality
  - Closeout claims
write_scope:
  - Tasks/active/mvp20_host_governed_initiative_continuity/*
  - OpenEmotion/tools/verify_mvp20_mainline_wiring.py
  - OpenEmotion/tests/mvp20/test_mvp20_mainline_reference_demotion.py
dependencies:
  - T00_AUTHORITY_FREEZE
success_criteria:
  - host proactive substrate is explicitly registered as reference-only to WP15 semantics
  - no-second-truth verifier exists
verification_commands:
  - pytest -q OpenEmotion/tests/mvp20/test_mvp20_mainline_reference_demotion.py
  - python3 OpenEmotion/tools/verify_mvp20_mainline_wiring.py --json
rollback_point:
  - revert initiative demotion docs and verifier only
```
