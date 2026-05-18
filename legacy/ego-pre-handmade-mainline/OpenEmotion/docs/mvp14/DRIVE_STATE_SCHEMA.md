# Drive State Schema

## 1. Top-Level Schema

The drive system should maintain at least:

- active_drives
- latent_drives
- homeostatic_signals
- maintenance_debt
- regulation_targets
- drive_history
- priority_snapshot

## 2. active_drives

Represents currently active internal drives.

Each drive should include:
- drive_id
- drive_type
- intensity
- source
- persistence
- last_updated
- linked_tensions
- candidate_effects

## 3. latent_drives

Represents drives not currently dominant but still relevant.

## 4. homeostatic_signals

Represents measurable deviations from desired operating balance.

Example categories:
- continuity instability
- unresolved contradiction load
- audit debt
- maintenance lag
- self-model inconsistency
- goal backlog pressure

## 5. maintenance_debt

Represents accumulated upkeep obligations.

Example:
- replay debt
- unresolved repair queue
- stale self-model review
- unresolved drift flags

## 6. regulation_targets

Represents preferred operating ranges.

Each target should include:
- target_name
- desired_range
- observed_value
- deviation_level

## 7. drive_history

Each meaningful transition should record:
- timestamp
- drive change
- cause
- evidence
- resulting action or candidate bias
