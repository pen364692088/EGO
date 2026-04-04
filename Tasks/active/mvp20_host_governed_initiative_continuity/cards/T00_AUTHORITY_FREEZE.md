# T00_AUTHORITY_FREEZE

```yaml
task_id: T00_AUTHORITY_FREEZE
parent_authority: Tasks/MVS_task_plan.md
phase: WP15
goal: Freeze WP15/MVP20 authority, ownership, IO contract, upstream boundary terms, and claim ceiling.
non_goals:
  - Implement initiative owner/runtime code
  - Reopen WP7~WP14
  - Claim implementation, mainline wiring, E4/E5, observation, or maintenance
write_scope:
  - Tasks/MVS_task_plan.md
  - Tasks/MVP20_task_plan.md
  - Tasks/active/mvp20_host_governed_initiative_continuity/*
  - PROJECT_MEMORY.md
read_scope:
  - Tasks/MVP12_task_plan.md
  - Tasks/MVP19_task_plan.md
  - OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md
dependencies: []
success_criteria:
  - WP15 appears in Tasks/MVS_task_plan.md
  - MVP20 phase-detail plan and active package exist
  - claim ceiling is explicitly frozen to authority_frozen/task_package_ready
verification_commands:
  - rg -n "WP15|MVP20|authority_frozen|task_package_ready|initiative_self|proposal_only|behavioral_authority = none" Tasks/MVS_task_plan.md Tasks/MVP20_task_plan.md Tasks/active/mvp20_host_governed_initiative_continuity/*
proof_required:
  - docs consistency only
rollback_point:
  - revert WP15 docs only
subagent_ready: true
```
