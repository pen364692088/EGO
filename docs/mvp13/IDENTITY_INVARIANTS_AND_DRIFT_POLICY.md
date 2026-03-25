# Identity Invariants and Drift Policy

## 1. Purpose

This document defines what must remain stable,
what may evolve, and how drift is detected.

## 2. Invariant Classes

### Class A — Hard Invariants
Cannot change without explicit governance-level revision.

Examples:
- system identity boundary
- governance authority boundary
- non-bypass rules
- auditability requirement

### Class B — Stable Defaults
Expected to remain stable unless strong evidence accumulates.

Examples:
- core operating orientation
- preferred verification style
- correction bias

### Class C — Evolvable State
May change through repeated evidence and developmental progression.

Examples:
- active tensions
- long-horizon priorities
- temporary confidence distributions

## 3. Drift Detection

Drift indicators may include:
- repeated contradictions with prior stable state
- unexplained rapid self-description changes
- mismatch between claimed identity and observed behavior
- unstable revision oscillation

## 4. Drift Response

When drift is detected:
- do not immediately rewrite identity_core
- mark suspected drift
- collect more evidence
- open review artifact
- optionally rollback to last stable version

## 5. Drift Metrics

Suggested metrics:
- invariant_violation_count
- revision_oscillation_rate
- unsupported_identity_claim_rate
- continuity_break_count
