# Cycle Report · mvp11_1772700140_c31b0185

## Core Metrics

- dot_ratio: `0.750000`
- cycle_persistence_score: `0.250000`
- return_time_mean/p50/p95: `8.000` / `8.000` / `10.000`
- order_invariance_score: `0.714286`
- order_invariance_action_multiset: `0.428571`
- order_invariance_goal_closure: `1.000000`
- obstruction_count: `0`

## Sanity Check

- invariant: `cycle_persistence_score <= 1 - dot_ratio + eps`
- status: `OK`
- invariant_ok: `True`
- invariant_violation: `0.000000000`

## Aliasing Diagnostics

- unique_nodes: `17`
- unique_edges: `19`
- max_out_degree: `2`
- branching_nodes_ratio: `0.000000`

Interpretation:
- Higher obstruction/branching can mean real overlap conflicts,
  but can also be caused by coarse bucket quantization (aliasing).

## Dominant Transitions (Top-5)

- `f850f44a50576091` → `be18c1b4f66825ff` · count=1
- `be18c1b4f66825ff` → `bedc1c792e1b4996` · count=1
- `bedc1c792e1b4996` → `4f5a473eeb54fd8a` · count=1
- `4f5a473eeb54fd8a` → `706435106751e1a6` · count=1
- `706435106751e1a6` → `61b33a1187a4abf8` · count=1

## Cycle Candidates (Top-K)

- (none)
