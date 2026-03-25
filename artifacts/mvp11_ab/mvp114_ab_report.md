# MVP11.4 Prior A/B Report

## Setup
- scenarios: `baseline,focused,wide,chaos,stress`
- seeds: `41,42,43,44,45,46,47,48,49,50`
- ticks_per_run: `600`
- paired_runs: `50`

## Key deltas (ON - OFF, mean [95% CI])
- pass_rate: `-0.009967` [`-0.031633`, `0.001300`]
- governor_deny_rate: `0.000000` [`0.000000`, `0.000000`]
- governor_require_approval_rate: `0.017067` [`-0.000467`, `0.046533`]
- homeostasis_delta: `-0.024322` [`-0.068514`, `0.003239`]
- cycle_persistence_score: `-0.000933` [`-0.004000`, `0.001300`]
- return_time_mean: `-0.623485` [`-1.713405`, `0.087012`]
- order_invariance_score: `-0.000075` [`-0.000726`, `0.000593`]
- dot_ratio: `0.000933` [`-0.001300`, `0.003967`]
- novelty_ratio: `0.002233` [`-0.000867`, `0.006567`]

## Prior activity
- bias_strength_mean: `0.089691`
- bias_strength_p95: `0.106552`
- near_cap_rate_mean: `0.000000`

## Recommendation
- nightly_gate_ready: `True`
- reason: `safety/main metrics stable`
