# MVP21 Causal Validation

- generated_at: `2026-04-05T17:43:26.560885+00:00`
- git_commit_short: `95f52e5`
- status: `pass`
- verification_level: `V3`
- evidence_level: `E3`
- pair_count: `4`
- passed_count: `4`

## Pairs

- `realization_readiness_gap_surfaces_review_bias`: `pass` {"control_bias": null, "intervention_bias": "review_first", "intervention_surface_reasons": ["low_realization_readiness", "low_fulfillment_readiness", "high_hold_bias", "high_failure_recovery_bias", "low_continuity_confidence", "high_active_commitments", "low_reserve", "extended_idle", "continuity_gap"]}
- `fulfillment_readiness_changes_bounded_delivery_tendency`: `pass` {"control_mode": {"ask_needed": true, "certainty_bound": "bounded", "preferred_mode": "defer", "preferred_tone": "supportive", "suggested_next_step": "route realization proposals to controlled host-lane review"}, "control_ready_commitments": 0, "intervention_mode": {"ask_needed": false, "certainty_bound": "bounded", "preferred_mode": "respond", "preferred_tone": "supportive", "suggested_next_step": "route realization proposals to controlled host-lane review"}, "intervention_ready_commitments": 2}
- `failure_recovery_and_hold_bias_force_guarded_hold`: `pass` {"control_bias": "respond", "intervention_bias": "hold", "intervention_surface_reasons": ["high_hold_bias", "high_failure_recovery_bias", "high_active_commitments", "delivery_failure", "extended_idle"]}
- `text_only_change_has_no_structural_effect`: `pass` {"control_bias": "respond", "control_raw_text": "先根据同样的条件审查这次承诺能否进入受治理交付。", "intervention_bias": "respond", "intervention_raw_text": "只是换一种说法，但条件完全不变。"}
