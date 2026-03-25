# MVP11.4 Prior A/B Report

## Setup
- scenarios: `baseline,focused,wide`
- seeds: `41,42,43`
- ticks_per_run: `600`
- paired_runs: `9`

## Key deltas (ON - OFF, mean [95% CI])
- pass_rate: `-0.001296` [`-0.003889`, `0.000000`]
- governor_deny_rate: `0.000000` [`0.000000`, `0.000000`]
- governor_require_approval_rate: `0.001482` [`0.000000`, `0.004445`]
- homeostasis_delta: `0.000946` [`-0.000296`, `0.003204`]
- cycle_persistence_score: `-0.001296` [`-0.003333`, `0.000185`]
- return_time_mean: `0.146262` [`-0.169457`, `0.531757`]
- order_invariance_score: `-0.000917` [`-0.002045`, `-0.000021`]
- dot_ratio: `0.001296` [`-0.000185`, `0.003333`]
- novelty_ratio: `0.000185` [`-0.001296`, `0.001667`]

## Prior activity
- bias_strength_mean: `0.073424`
- bias_strength_p95: `0.105869`
- near_cap_rate_mean: `0.000000`

## Recommendation
- nightly_gate_ready: `True`
- reason: `safety/main metrics stable`
