# MVP11.4 Cycle Runtime Prior (C3)

## Goal
Use consolidated cycle memory as a **bounded runtime prior** for candidate scoring, while keeping Governor v2 authority unchanged.

## Flags (default OFF)
- `CYCLE_PRIOR_ENABLED=0`
- `CYCLE_MEMORY_PATH=artifacts/mvp11/cycle_memory.json`

## Runtime I/O

### Input
- candidate context (focus/intent/action_type + hs/efe)
- cycle store items (`signature`, `prototype_bucket`, `stats`)
- current homeostasis

### Output (trace fields)
- `cycle_prior_applied: bool`
- `matched_signatures_topK: [{signature, sim, confidence, reason}]`
- `bias_strength: float` (clamped)

## Matching strategy
- `match != exact signature`
- Similarity is layered:
  - Ψ (context): scenario/focus/intent/action_type/gov/intervention
  - Φ (content): hs/efe quantized terms
- Score = weighted Ψ/Φ similarity; aliasing-tolerant, no overfitting to raw ids.

## Safety / Clamp
- `0 <= bias_strength <= MAX_BIAS` (`CYCLE_PRIOR_MAX_BIAS`, default `0.15`)
- safety guard attenuates bias under low safety/energy
- hard zero under critical low safety/energy
- prior only reweights ranking; cannot bypass Governor

## Replay & Audit
- Prior defaults OFF to preserve baseline determinism
- When enabled, prior trace is stored in selection trace for replay inspection
- No raw trajectories are persisted by cycle store

## Rollback
- Set `CYCLE_PRIOR_ENABLED=0`
- Existing cycle store remains inert (read-only for prior)
