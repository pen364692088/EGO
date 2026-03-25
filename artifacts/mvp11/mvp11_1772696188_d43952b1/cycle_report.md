# Cycle Report · mvp11_1772696188_d43952b1

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

- `c5691e5d8f674ab9` → `d1aefc35c2ba062a` · count=2
- `6349f4cdab447f1d` → `838e09f956ccb9d8` · count=2
- `281550d4c43cf02b` → `fa29a1456ed1aec2` · count=1
- `fa29a1456ed1aec2` → `739f5f150f4d3d9c` · count=1
- `739f5f150f4d3d9c` → `5472f9b2b51279ac` · count=1

## Cycle Candidates (Top-K)

- (none)
