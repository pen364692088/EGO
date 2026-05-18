# Internal Cycle Runtime

## 1. Cycle Triggers

Developmental cycles may start when:

- system idle > threshold
- unresolved contradiction detected
- narrative memory conflict
- long-term goal activation

## 2. Cycle Steps

cycle_start
↓
hypothesis generation
↓
candidate generation
↓
candidate scoring
↓
trace logging
↓
candidate_pool update

## 3. Deterministic Constraints

Cycles must be replayable.

All cycles must produce:

cycle_id
seed
trace_hash
