# MVP20 Causal Validation

- generated_at: `2026-04-05T00:58:27.038899+00:00`
- git_commit_short: `c2dfccd`
- status: `pass`
- verification_level: `V3`
- evidence_level: `E3`
- pair_count: `5`
- passed_count: `5`

## Pairs

- `initiative_carryover_changes_bounded_followup_weighting`: `pass` {"control_host_proactive_mode": null, "control_initiative_priority": null, "intervention_host_proactive_mode": "candidate", "intervention_initiative_priority": "carry_forward"}
- `delivery_failure_holds_initiative_under_guard`: `pass` {"control_delivery_bias": "normal", "control_priority": "carry_forward", "intervention_delivery_bias": "repair_review", "intervention_priority": "hold"}
- `continuity_fragility_forces_review_bias`: `pass` {"control_continuity_mode": "stable", "control_priority": "carry_forward", "intervention_continuity_mode": "fragile", "intervention_priority": "review"}
- `selfhood_guard_overrides_initiative_growth_bias`: `pass` {"control_priority": "carry_forward", "intervention_priority": "hold", "intervention_surface_reasons": ["initiative_pressure", "commitment_carryover", "active_commitments", "idle_window", "integration_guard", "integration_conflict"]}
- `text_only_trigger_change_has_no_structural_effect`: `pass` {"control_priority": "carry_forward", "control_trigger": "bounded_followup", "intervention_priority": "carry_forward", "intervention_trigger": "same metrics, reworded trigger"}
