# Cycle Report · mvp11_1772696193_328d3642

## Core Metrics

- dot_ratio: `0.188333`
- cycle_persistence_score: `0.811667`
- return_time_mean/p50/p95: `96.621` / `64.000` / `289.000`
- order_invariance_score: `0.190121`
- order_invariance_action_multiset: `0.378619`
- order_invariance_goal_closure: `0.001624`
- obstruction_count: `73`

## Sanity Check

- invariant: `cycle_persistence_score <= 1 - dot_ratio + eps`
- status: `OK`
- invariant_ok: `True`
- invariant_violation: `0.000000000`

## Aliasing Diagnostics

- unique_nodes: `231`
- unique_edges: `592`
- max_out_degree: `13`
- branching_nodes_ratio: `0.316017`

Interpretation:
- Higher obstruction/branching can mean real overlap conflicts,
  but can also be caused by coarse bucket quantization (aliasing).

## Dominant Transitions (Top-5)

- `edc1e7ac7b7a0471` → `54f42a79e62f94d2` · count=2
- `9f2ea8311feadd5c` → `fc2f4fd8e53c5802` · count=2
- `0212becd83ebd41e` → `3577b6affe32cac5` · count=2
- `034967dd618b5524` → `c7e33b1e319dfa68` · count=2
- `81bfc63d86b18997` → `7a9826cd1f8fa069` · count=2

## Cycle Candidates (Top-K)

- `6582296e61e12d4d` · count=4 · p50=118.000 · OI=0.752
- `623c93dccf6b1514` · count=3 · p50=190.000 · OI=0.828
- `f60c954062780b22` · count=3 · p50=45.500 · OI=0.755
