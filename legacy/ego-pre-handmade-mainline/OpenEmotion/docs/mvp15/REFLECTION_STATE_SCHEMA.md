# Reflection State Schema

## 1. Top-Level Schema

The reflection system should maintain at least:

- reflection_queue
- reflection_targets
- diagnosis_records
- counterfactual_records
- revision_proposals
- unresolved_reflection_items
- reflection_history

## 2. reflection_queue

Represents pending reflection jobs.

Each job should include:
- reflection_id
- target_type
- target_reference
- priority
- trigger_source
- created_at

## 3. diagnosis_records

Represents completed self-diagnosis outputs.

Each record should include:
- diagnosis_id
- analyzed_target
- detected_pattern
- confidence
- supporting_evidence
- suggested_action

## 4. counterfactual_records

Represents analyses of alternative self-trajectories or choices.

Each record should include:
- counterfactual_id
- baseline_reference
- alternative_path
- expected_difference
- evidence_basis
- uncertainty_level

## 5. revision_proposals

Represents governed proposals derived from reflection.

Each proposal should include:
- proposal_id
- target_layer
- proposed_change
- justification
- reversibility
- required_gate

## 6. unresolved_reflection_items

Represents unresolved self-analysis issues that require follow-up.
