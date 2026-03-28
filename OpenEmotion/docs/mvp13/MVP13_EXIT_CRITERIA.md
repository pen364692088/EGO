# MVP13 Exit Criteria

MVP13 is complete only when the system demonstrates
a persistent, structured, and auditable self-model.

## 1. Formal Owner Contract

The formal owner contract must be converged and unique:

- authoritative owner: `openemotion/self_model/*`
- authoritative schema: `schemas/self_model.schema.json`
- no proof or promotion claim may depend on `emotiond/self_model/*` as the
  semantic owner

## 2. Persistence

The self-model survives across sessions and cycle boundaries.

## 3. Structural Integrity

The self-model is represented in structured schema form,
not only in free-form text.

## 4. Replayability

Self-model revisions can be replayed and audited.

## 5. Identity Continuity

The system maintains continuity across time without
unexplained identity resets or drift spikes.

## 6. Drift Governance

Drift detection and rollback policy are implemented
and verified.

## 7. Behavioral Influence

Behavioral influence must be proven through interventions on the formal owner
contract, not legacy-only fields. At minimum, the proof path must operate on
one or more of:

- `active_goals`
- `standing_commitments`
- `confidence_by_domain`
- capability / limitation state that is exposed by the formal owner

## 8. Metrics

Suggested thresholds:
- self_model_load_success >= 99%
- replay_consistency >= 99%
- unsupported_identity_claim_rate < threshold
- invariant_violation_count = 0 for hard invariants
- continuity_break_count within allowed bound
