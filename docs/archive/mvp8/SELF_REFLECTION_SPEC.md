# MVP-8 Self-Reflection & Emotional Reasoning Spec

## Scope
After every `process_event`, generate deterministic `self_report` for auditing/replay.

## Trigger Timing
- Trigger: end of `emotiond.core.process_event()` after state update + appraisal.
- Exactly once per successfully processed event.

## Output Paths
- Per-report JSON: `reports/self_reports/{target_id}/{YYYYMMDDTHHMMSSZ}.json`
- Audit index (JSONL): `reports/self_reports/index.jsonl`
- Base dir configurable via `EMOTIOND_REPORTS_DIR` environment variable (for test isolation).

## Required `self_report` Fields
- `schema_version`: `mvp8.v1`
- `generated_at` (ISO8601 UTC) — **excluded from hash**
- `seed` (deterministic seed)
- `target_id` (session isolation key)
- `counterparty_id` (relationship continuity key)
- `event` (type/actor/target/text/meta)
- `state_snapshot` (valence/arousal/prediction_error/social_safety/energy/uncertainty/energy_budget)
- `appraisal` (goal_progress, expectation_violation, controllability, social_threat, novelty, intensity, etc.)
- `emotional_reasoning` (primary_emotion, interpretation, predicted_risk, action_tendency, confidence)
- `self_consistency` (has_conflict, items, repair_strategy)
- `narrative_memory` (state + compressed summary)
- `audit` (source, deterministic, hash_algo, hash_excludes, self_hash)

## Determinism Requirements
- No external dependencies.
- Same input + same seed must produce same logical reasoning outputs.
- Hash computed from canonical JSON (`sort_keys=True`, compact separators).
- **Cross-process stable**: `hash_excludes` uses `sorted()` to ensure consistent order across Python processes.

## Hash Rules (Critical for Cross-Process Replay)

### Stable Hash Guarantee
`self_hash` is computed from **only stable fields**, ensuring:
- Same input + same seed → **same hash across runs**
- Same input + same seed → **same hash across processes** (different PYTHONHASHSEED)
- Enables replay verification: recompute hash from archived data

### Excluded from Hash
- `generated_at` — varies by clock
- `report_path` — runtime-specific
- `self_hash` — circular (hash cannot include itself)

### Implementation
```python
_HASH_EXCLUDE_TOP = frozenset({"generated_at", "report_path"})
_HASH_EXCLUDE_NESTED = frozenset({"self_hash"})

def _extract_stable_payload(report: Dict) -> Dict:
    stable = {}
    for k, v in report.items():
        if k in _HASH_EXCLUDE_TOP:
            continue
        if isinstance(v, dict):
            stable[k] = {kk: vv for kk, vv in v.items() if kk not in _HASH_EXCLUDE_NESTED}
        else:
            stable[k] = v
    return stable

self_hash = sha256(canonical_json(_extract_stable_payload(report)))

# CRITICAL: Use sorted() for cross-process determinism
"hash_excludes": sorted(_HASH_EXCLUDE_TOP | _HASH_EXCLUDE_NESTED)
```

### Replay Verification
To verify a stored report:
1. Extract stable payload (exclude `generated_at`, `self_hash`)
2. Recompute hash
3. Compare with `audit.self_hash`

## Consistency/Repair Rules
- Detect contradictions between beliefs, commitments, and action tendency.
- Emit `repair_strategy` (e.g. `downgrade_to_observe_or_boundary`, `prefer_repair_offer`).

### Conflict Types
| Type | Trigger | Repair |
|------|---------|--------|
| `approach_under_high_threat` | approach tendency + threat > 0.7 | `downgrade_to_observe_or_boundary` |
| `withdraw_despite_safety` | withdraw + high safety + low threat | `consider_repair_offer_or_approach` |
| `commitment_action_mismatch` | promise_repair + withdraw/protect | `prefer_repair_offer` |

## Narrative Memory Rules
- Per-target stateful memory in process (`target_id` keyed).
- Compress into single-line summary:
  - who am I
  - what I am doing
  - why
  - event/conflict counters

## Scenario Expect Assertions

Each eval scenario must include `expect` with one or more:
- `primary_emotion`: expected emotion label
- `action_tendency`: expected action (approach/withdraw/observe/etc.)
- `has_conflict`: boolean
- `repair_strategy`: string (partial match allowed)
- `narrative_summary_contains`: substring to find in compressed summary

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `EMOTIOND_REPORTS_DIR` | Base dir for self_reports | `reports` |
| `EMOTIOND_DB_PATH` | Database path | `emotiond.db` |
