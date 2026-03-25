# Layer 3 Collection Protocol (T07.3 Refresh)

Generated: 2026-03-08T18:49:00-05:00

## Natural session rules
A session counts as Layer 3 only if:
- `session_id` is non-empty
- `session_id` does not start with `test_`
- `session_id` does not start with `controlled_`
- event source is real user/assistant traffic, not scripted replay

## Required fields
- timestamp
- session_id
- turn_id if available
- speaker_mode
- epistemic_status
- commitment_level
- violation_type
- severity
- evidence_span
- would_block
- source_stage

## Minimum threshold for Layer 3 reporting
- at least 100 samples
- at least 10 unique natural sessions
- at least 24h span
- reported separately from Layer 1 and Layer 2

## Reporting rule
Layer 3 must be reported in its own section and may not be merged with Layer 2 to claim readiness.
