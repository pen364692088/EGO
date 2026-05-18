# MVP18 Causal Validation

- generated_at: `2026-04-04T16:06:59.876420+00:00`
- git_commit_short: `1c784aa`
- status: `pass`
- verification_level: `V3`
- evidence_level: `E3`
- pair_count: `4`
- passed_count: `4`

## Pairs

- `high_resource_pressure_changes_weighting`: `pass` {"control_resource_bias": null, "intervention_resource_bias": "conserve", "intervention_surface_reasons": ["resource_pressure", "resource_slack_low", "high_load"]}
- `consequence_memory_changes_weighting`: `pass` {"control_consequence_candidates": 0, "control_stabilization_bias": null, "intervention_consequence_candidates": 1, "intervention_stabilization_bias": "normal"}
- `boundary_guard_changes_weighting`: `pass` {"control_boundary_bias": null, "control_boundary_mode": "open", "intervention_boundary_bias": "cautious", "intervention_boundary_mode": "guarded"}
- `text_only_change_has_no_effect`: `pass` {"control_embodied_policy_hints": {"action_ref": "env:act:001", "boundary_mode": "open", "consequence_mode": "observe", "resource_bias": "normal", "self_world_guard": "bounded", "stabilization_bias": "normal"}, "intervention_embodied_policy_hints": {"action_ref": "env:act:001", "boundary_mode": "open", "consequence_mode": "observe", "resource_bias": "normal", "self_world_guard": "bounded", "stabilization_bias": "normal"}}
