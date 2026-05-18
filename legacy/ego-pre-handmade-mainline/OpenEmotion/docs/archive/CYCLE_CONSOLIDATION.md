# MVP11.3 Cycle-Guided Consolidation

## Scope

This document defines the **C0 → C3** rollout for cycle-guided consolidation.

- **C0 (required first)**: cycle metric self-consistency (dot/persistence invariant)
- **C1**: candidate marking only (no runtime policy/write impact)
- **C2**: consolidate structural invariants into `cycle_memory.json`
- **C3**: runtime prior feedback (feature-flagged, default OFF)

---

## C0: Self-consistency invariant

Invariant:

```text
cycle_persistence_score <= 1 - dot_ratio + eps
```

Where `eps` defaults to `1e-6`.

### Behavior

- If invariant holds: `sanity.status = OK`
- If violated: `sanity.status = WARN_INCONSISTENT`
- CI short-run: warning is allowed (no hard fail)
- Nightly long-run: can be upgraded to hard gate

### Required diagnostics

`cycle_report` includes:
- `sanity.invariant_ok`
- `sanity.invariant_violation`
- `sanity.status`
- possible causes (SCC mismatch / aliasing / definition mismatch)

---

## Aliasing diagnostics

To separate real branching from coarse bucket aliasing, cycle metrics include:

- `max_out_degree`
- `branching_nodes_ratio`
- `unique_nodes`
- `unique_edges`

Interpretation rule:
- Rising branching/obstruction may be real overlap conflict **or** bucket aliasing.

---

## Order invariance decomposition (new)

`order_invariance_score` now has two explainable components:

- `order_invariance_action_multiset`
- `order_invariance_goal_closure`

This distinguishes:
- action-sequence variability
- closure-semantic variability

while preserving a single aggregate score.

---

## C1: Candidate marking

`cycle_analyze_mvp11.py` emits `cycle_candidates_topK` (default K=10) using conservative defaults:

- `counts >= 3`
- `cycle_member == true` (SCC member and count>=2)
- `return_time_p50` within configured range
- `order_invariance_score >= 0.7`

No raw trajectory text is persisted.

---

## C2: ConsolidatedCycle storage

`cycle_store.v1` item fields:

- `signature`
- `prototype_bucket` (canonical bucket)
- `stats` (counts/return_time/persistence/order invariance)
- `plan_template_hash` (optional)
- `provenance` (run_id/scenario_id/seed/policy/schema)

Write policy:

- only if `sanity.status == OK`
- output path: `artifacts/mvp11/cycle_memory.json`

Capacity governance:

- `max_entries` (default `10000`)
- dedupe by signature
- rolling stats merge for repeated signature
- confidence-ranked eviction when over cap

---

## C3: Runtime prior feedback (default OFF)

Flags:

- `CYCLE_CONSOLIDATION_ENABLED=0`
- `CYCLE_PRIOR_ENABLED=0`

When enabled, runtime must log:
- `cycle_prior_applied`
- `matched_signatures_topK`
- `bias_strength`

Governor v2 remains authoritative.

---

## Soak + Gate automation

### 1) Distribution profile runner

```bash
python scripts/soak_profile_mvp11.py \
  --scenarios baseline,focused,wide \
  --seeds 41,42,43,44,45 \
  --ticks 10000 \
  --sentinel-ticks 100000 \
  --sentinel-scenarios baseline,focused,wide \
  --sentinel-rotation-mode weekday \
  --output artifacts/mvp11/profiles/soak_profile.json
```

Sentinel strategy:
- default `weekday` rotation (Mon→baseline, Tue→focused, Wed→wide, loop)
- keeps 100k cost fixed while covering all scenarios over time

Outputs:
- `sanity_ok_coverage`
- distribution summaries (p50/p95) for key metrics
- recommended threshold baseline for Gate-L

### 2) Gate evaluator

```bash
python scripts/cycle_gate_mvp11.py \
  --profile artifacts/mvp11/profiles/soak_profile.json \
  --effects artifacts/mvp11/effects/cycle_effects.json \
  --output artifacts/mvp11/profiles/cycle_gate_report.json \
  --markdown artifacts/mvp11/profiles/cycle_gate_report.md
```

### 3) Nightly dashboard renderer

```bash
python scripts/render_mvp11_cycle_dashboard.py \
  --profile artifacts/mvp11/profiles/soak_profile.json \
  --effects artifacts/mvp11/effects/cycle_effects.json \
  --gate artifacts/mvp11/profiles/cycle_gate_report.json \
  --out-json artifacts/mvp11/dashboard/nightly_dashboard.json \
  --out-md artifacts/mvp11/dashboard/nightly_dashboard.md
```

The nightly workflow appends `nightly_dashboard.md` to `$GITHUB_STEP_SUMMARY` for one-screen triage.

### 4) 7-day trend (new)

```bash
python scripts/export_mvp11_trend_entry.py \
  --dashboard artifacts/mvp11/dashboard/nightly_dashboard.json \
  --profile artifacts/mvp11/profiles/nightly_soak_profile.json \
  --gate artifacts/mvp11/profiles/nightly_cycle_gate_report.json \
  --effects artifacts/mvp11/effects/nightly_cycle_effects.json \
  --out artifacts/mvp11/trends/trend_entry.json

python scripts/build_mvp11_trend_7d.py \
  --entries-dir /tmp/mvp11_trend_entries \
  --out-json artifacts/mvp11/trends/trend_7d.json \
  --out-md artifacts/mvp11/trends/trend_7d.md
```

`trend_7d.md` includes gate heatmap, sparklines, and soft drift alert (no hard fail by default).

Gate defaults:
- Gate-1: `sanity_ok_coverage >= 0.99`
- Gate-2: intervention direction assertions all pass
- Gate-3: KPI non-degradation (skipped while C3 is OFF)

---

## Two-phase gate policy

### Gate-S (CI short run)
- cycle report generated
- no schema/runtime crash
- sanity is present (`OK` or `WARN_INCONSISTENT`)
- determinism tests pass

### Gate-L (Nightly long run)
- `sanity_ok_coverage >= 0.99`
- `cycle_persistence_score / dot_ratio / return_time_p95` within learned distribution bands
- intervention direction checks pass
- optional C3 AB non-degradation gate when feature is enabled

---

## MVP11.4 update (Ψ/Φ + CycleGraph + Runtime Prior + DMN rollouts)

### 1) Bucket schema layering
`cycle_bucket` now contains:
- legacy canonical fields for backward-compatible signature
- `psi` (context layer)
- `phi` (content layer)
- `bucket_schema_version = mvp11.4.v1`

Compatibility rule:
- `cycle_signature` is computed from canonical payload only
- extension fields (`psi/phi/schema_version`) do not alter old signature

Additional signatures:
- `cycle_signature_psi`
- `cycle_signature_phi`

### 2) CycleGraph (offline)
New module/script:
- `emotiond/science/cycle_graph.py`
- `scripts/cycle_graph_mvp11.py`

Outputs:
- per-run: `artifacts/mvp11/<run_id>/cycle_graph.json`
- optional merged: `artifacts/mvp11/cycle_graph.json`

Includes capacity governance (`max_nodes`, `max_edges`) with deterministic tie-breakers.

### 3) C3 runtime prior strategy
Matching is similarity-based (Ψ/Φ), not exact signature hit.
Prior trace fields:
- `cycle_prior_applied`
- `matched_signatures_topK`
- `bias_strength`

Clamp/safety:
- bounded by `MAX_BIAS`
- decays to zero under low safety/energy
- Governor v2 authority unchanged

### 4) DMN cycle-driven suggestions
`DMNTick` rollout output is normalized to:
- `suggestions`
- `reason`
- `cycle_refs`

Suggestions remain advisory and must pass full decision chain.
