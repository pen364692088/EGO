# MVP13 Exit Criteria

MVP13 is complete only when the system demonstrates
a persistent, structured, and auditable self-model.

## 1. Persistence

The self-model survives across sessions and cycle boundaries.

## 2. Structural Integrity

The self-model is represented in structured schema form,
not only in free-form text.

## 3. Replayability

Self-model revisions can be replayed and audited.

## 4. Identity Continuity

The system maintains continuity across time without
unexplained identity resets or drift spikes.

## 5. Drift Governance

Drift detection and rollback policy are implemented
and verified.

## 6. Metrics

Suggested thresholds:
- self_model_load_success >= 99%
- replay_consistency >= 99%
- unsupported_identity_claim_rate < threshold
- invariant_violation_count = 0 for hard invariants
- continuity_break_count within allowed bound
