# Cycle Report · mvp11_1772690557_0db25586

## Core Metrics

- dot_ratio: `0.733333`
- cycle_persistence_score: `0.266667`
- return_time_mean/p50/p95: `16.667` / `10.000` / `41.000`
- order_invariance_score: `0.383333`
- obstruction_count: `2`

## Sanity Check

- invariant: `cycle_persistence_score <= 1 - dot_ratio + eps`
- status: `OK`
- invariant_ok: `True`
- invariant_violation: `0.000000000`

## Aliasing Diagnostics

- unique_nodes: `51`
- unique_edges: `59`
- max_out_degree: `3`
- branching_nodes_ratio: `0.039216`

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
