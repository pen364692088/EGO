# Drive Governance and Priority Policy

## 1. Purpose

This document defines how endogenous drives are governed,
prioritized, limited, and audited.

## 2. Governance Principle

No drive has direct authority.
All drives are inputs to governed prioritization.

## 3. Priority Resolution

When multiple drives compete, priority should consider:
- intensity
- persistence
- evidence quality
- governance safety
- impact scope
- reversibility

## 4. Forbidden Outcomes

Drives must not:
- override hard invariants
- bypass SRAP or Governor
- escalate authority on their own
- create irreversible identity changes directly

## 5. Priority Classes

Suggested classes:
- P0 critical maintenance
- P1 coherence and repair
- P2 completion and stabilization
- P3 exploration
- P4 opportunistic low-cost improvements

## 6. Conflict Handling

When drive conflicts occur:
- record the conflict
- compute weighted resolution
- prefer reversible actions
- preserve hard invariants
- escalate to review when unresolved

## 7. Required Metrics

Suggested metrics:
- drive_conflict_count
- maintenance_trigger_rate
- unresolved_drive_pressure
- governance_block_count
- drive_resolution_latency
