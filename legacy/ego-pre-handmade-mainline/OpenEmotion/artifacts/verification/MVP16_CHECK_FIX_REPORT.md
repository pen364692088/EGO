# MVP16 Check Fix Report

## Scope
P0 only repairs the MVP16 verification-system false-positive chain.
It does **not** by itself prove MVP16 long-horizon continuity has been verified.

## Root cause
The old daily check path executed:
1. `reset_developmental_manager()`
2. `get_developmental_manager()`
3. read summary/metrics from a fresh instance seeded with defaults

This caused boot defaults to be misread as observational evidence, producing false PASS results.

## Fix implemented
### A. Removed false-positive chain
`tools/mvp16_daily_check.py` no longer resets the manager before reading.

### B. Real-data gate added
Daily verification now requires real evidence via manager-level `has_real_data()`.
If real persisted data is absent, the check returns:
- `insufficient_evidence` at component level
- `blocked` at overall level

### C. Evidence source separation
The repaired check now distinguishes:
- boot defaults
- observed metrics
- computed verdict

## Current expected behavior
### Empty / fresh state
- tests may pass
- daily verification must **not** PASS
- overall status must be `blocked`

### Persisted real state exists
- continuity / metrics / invariants may be evaluated
- verdict can be derived from persisted evidence and accumulated runtime state

## Local verification evidence
Observed local run after repair:
- 30 tests passed
- continuity: `insufficient_evidence`
- metrics: `insufficient_evidence`
- invariants: `insufficient_evidence`
- overall: `blocked`

This confirms the old `reset -> default -> PASS` path is no longer active in local repaired code.
