# Cycle Report · mvp11_1773432935_dd5861d7

## Core Metrics

- dot_ratio: `0.458333`
- cycle_persistence_score: `0.541667`
- return_time_mean/p50/p95: `27.150` / `23.000` / `60.000`
- order_invariance_score: `0.195569`
- order_invariance_action_multiset: `0.367423`
- order_invariance_goal_closure: `0.023715`
- obstruction_count: `8`

## Sanity Check

- invariant: `cycle_persistence_score <= 1 - dot_ratio + eps`
- status: `OK`
- invariant_ok: `True`
- invariant_violation: `0.000000000`

## Aliasing Diagnostics

- unique_nodes: `80`
- unique_edges: `117`
- max_out_degree: `4`
- branching_nodes_ratio: `0.100000`

Interpretation:
- Higher obstruction/branching can mean real overlap conflicts,
  but can also be caused by coarse bucket quantization (aliasing).

## Dominant Transitions (Top-5)

- `bdc198de1543fa02` → `ab66fcc06a7e9a08` · count=2
- `d62390376e1c980c` → `114eeae6783ffb21` · count=2
- `10c55c4366e579f4` → `105dd3933331039e` · count=1
- `105dd3933331039e` → `0e943f8218d27367` · count=1
- `0e943f8218d27367` → `bddee75ef46b52cc` · count=1

## Cycle Candidates (Top-K)

- (none)
