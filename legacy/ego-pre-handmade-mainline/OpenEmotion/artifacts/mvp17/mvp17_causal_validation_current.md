# MVP17 Causal Validation

- generated_at: `2026-04-04T05:49:43.249393+00:00`
- git_commit_short: `f340e7f`
- status: `pass`
- verification_level: `V3`
- evidence_level: `E3`
- pair_count: `4`
- passed_count: `4`

## Pairs

- `negative_trust_drift`: `pass` {'control_trust_bias': None, 'intervention_trust_bias': 'guarded', 'intervention_surface_reasons': ['trust_drift']}
- `commitment_breach_repair_bias`: `pass` {'control_commitment_guard': 'normal', 'intervention_commitment_guard': 'strict', 'control_repair_bias': 'normal', 'intervention_repair_bias': 'elevated'}
- `boundary_caution_weighting`: `pass` {'control_boundary_mode': 'open', 'intervention_boundary_mode': 'firm', 'control_boundary_bias': None, 'intervention_boundary_bias': 'cautious'}
- `text_only_change_has_no_effect`: `pass` {'control_social_policy_hints': {'relationship_continuity': 'stable', 'trust_bias': 'normal', 'commitment_guard': 'normal', 'repair_bias': 'normal', 'boundary_mode': 'open', 'counterpart_id': 'telegram:8420019401'}, 'intervention_social_policy_hints': {'relationship_continuity': 'stable', 'trust_bias': 'normal', 'commitment_guard': 'normal', 'repair_bias': 'normal', 'boundary_mode': 'open', 'counterpart_id': 'telegram:8420019401'}}
