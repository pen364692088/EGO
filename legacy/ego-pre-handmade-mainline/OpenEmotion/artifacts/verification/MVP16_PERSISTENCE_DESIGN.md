# MVP16 Persistence Design

## Scope
Persistence added only for MVP16 verification-system repair.
No P1 main-chain wiring changes are included here.

## Persistence target
Default persistence path:
- `data/developmental_state.json`

Exposed through:
- `emotiond.developmental.DEFAULT_STATE_PATH`

## Stored state
The persisted developmental state must cover raw state needed for later verification, including:
- trajectory episodes
- trajectory transitions
- tracked metrics and histories
- summary-relevant state reconstructed from persisted model data

## Write timing
Auto-save occurs on mutating operations, including:
- record episode
- complete episode
- record transition
- update metric

## Load timing
`DevelopmentalManager` now attempts load in constructor before creating a fresh default state.
Only when no valid persisted state exists does it initialize defaults.

## Reset semantics
`reset_developmental_manager()` now supports two modes:
- non-destructive reset: clears singleton instance only
- destructive reset: clears instance and deletes persisted file when explicitly requested via `clear_persistence=True`

This prevents normal verification flows from accidentally erasing accumulated state.

## Corruption handling
If persisted JSON is missing or corrupted:
- load returns `None`
- manager falls back to fresh initialization
- daily verification still requires `has_real_data()` and therefore cannot convert defaults into PASS evidence

## Why state file is not committed as evidence
`data/developmental_state.json` is runtime-generated state, not stable completion evidence.
The externally auditable evidence for P0 is:
- code path changes
- regression tests
- verification reports
not a checked-in live runtime snapshot.
