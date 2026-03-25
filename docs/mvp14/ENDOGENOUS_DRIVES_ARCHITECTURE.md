# Endogenous Drives Architecture

## 1. Objective

The endogenous drive system models internal pressures that arise
from the system's own state, continuity, unfinished goals, tensions,
and maintenance needs.

These drives influence internal prioritization, candidate weighting,
and self-maintenance behavior under governance constraints.

## 2. Component Layout

drives/
    drive_manager.py
    drive_types.py
    drive_accumulator.py
    drive_decay.py
    drive_prioritizer.py
    maintenance_router.py
    drive_audit.py

## 3. Input Sources

Drives may be fed by:
- self-model tensions
- continuity breaks
- unresolved contradictions
- long-horizon unfinished goals
- stability degradation signals
- maintenance debt indicators

## 4. Output Targets

Drives may influence:
- developmental cycle priority
- candidate scoring
- maintenance task triggering
- memory review priority
- tension resolution urgency

Drives MUST NOT:
- directly emit final user-facing actions
- rewrite policy or governance boundaries
- self-authorize privileged actions

## 5. Drive Classes

Suggested classes:
- stability drive
- coherence drive
- completion drive
- verification drive
- repair drive
- exploration drive
- conservation drive

## 6. Lifecycle

Each drive should support:
- activation
- accumulation
- competition
- decay
- resolution
- archival
