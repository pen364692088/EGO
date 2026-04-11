# MVS Replay Validator Scored

- generated_at: `2026-04-11T15:31:15.135345+00:00`
- selection_decision: `bridge_pass`
- candidate_pass: `True`

## Target Scores

- `mvs_baseline_proto_self_mainline`: composite=`0.5333` T1=`1.0` T2=`0.75` T3=`0.3333` T4=`0.3333` T5=`0.25`
- `mvs_challenger_active_inference_self_model`: composite=`1.0` T1=`1.0` T2=`1.0` T3=`1.0` T4=`1.0` T5=`1.0`
- `baseline_chat_surface`: composite=`0.0` T1=`0.0` T2=`0.0` T3=`0.0` T4=`0.0` T5=`0.0`

## Selection

- target_deltas_vs_baseline_a: `{'T1': 0.0, 'T2': 0.25, 'T3': 0.6667, 'T4': 0.6667, 'T5': 0.75}`
- target_delta_rules: `{'T1': 'non_regression>=-0.02', 'T2': 'delta>=0.05', 'T3': 'delta>=0.05', 'T4': 'delta>=0.05', 'T5': 'delta>=0.05'}`
- composite_delta_vs_baseline_a: `0.4667`
- ablation_drops: `{}`
- weak_ablations: `[]`
- challenger_status: `not_applicable`
- challenger_pass: `False`
- challenger_target_deltas_vs_baseline_a: `{}`
- challenger_target_delta_rules: `{}`
- challenger_composite_delta_vs_baseline_a: `0.0`
- challenger_switch_advantage: `False`

## Bridge Checks

- authority_drift_status: `pass`
- trace_contract_status: `pass`
