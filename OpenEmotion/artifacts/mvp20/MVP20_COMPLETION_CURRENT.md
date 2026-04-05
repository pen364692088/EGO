# MVP20 / WP15 Completion Report

**Status**: CONTROLLED PASS
**Date**: 2026-04-05
**Phase**: WP15 / MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity

## Completion Boundary

This report closes `WP15` on the formal owner + proposal-only initiative writeback + controlled observation axis.

It does **not** claim:

- live autonomy
- direct OpenEmotion reply authority
- tool authority
- broader transport evidence

## Proven Deliverables

- formal owner fixed to:
  - `OpenEmotion/openemotion/initiative_self/*`
- formal runtime path:
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- governed writeback path:
  - `initiative_self_delta`
  - `initiative_proposal_candidates`
  - `commitment_execution_snapshot`
  - `initiative_policy_hints`
  - `host_proactive_candidate`
  - `initiative_audit_entries`
  - `initiative_writeback_candidate`
  - `initiative_writeback`
- bounded initiative projection consumed by `proto_self_v2`
- `WP7` host proactive substrate demoted to host-execution-substrate / reference-only for `WP15`
- `WP8~WP14` surfaces frozen as read-only inputs for `WP15`
- EgoCore bridge returns initiative context and gated writeback result to mainline

## Evidence Stack

- Causal behavioral proof:
  - `OpenEmotion/artifacts/mvp20/mvp20_causal_validation_current.md`
  - `verification_level = V3`
  - `evidence_level = E3`
- Single controlled mainline sample:
  - `OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_current.md`
  - `verification_level = V4`
  - `evidence_level = E4`
- Batch controlled stability sample:
  - `OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_batch_current.md`
  - `verification_level = V5`
  - `evidence_level = E5`

## Stable Batch Result

- `report_count = 3`
- `accepted_count = 3`
- `replay_consistent_count = 3`
- `initiative_proposal_present_count = 3`
- `proposal_only_discipline_count = 3`
- `behavioral_authority_none_count = 3`
- `bounded_influence_present_count = 3`
- `distinct_targets = [continuity_fragility_review, delivery_failure_hold_review, initiative_followup_medium_reserve]`
- `source_breakdown = {repo_authored: 3}`

## Exit Criteria Status

| Criteria | Status |
| --- | --- |
| Formal owner uniqueness | PASS |
| Runtime mainline integration | PASS |
| Proposal discipline preserved | PASS |
| Replayability | PASS |
| Causal behavioral influence | PASS |
| Controlled stability observation | PASS |
| Governance integrity preserved | PASS |

## Residual Risk

- chat provider may emit transient `429/401` during single or batch runs
- this affects repeat-run budget stability
- it does not invalidate the recorded `V5/E5` controlled observation result

## Next Mainline Action

`WP15` should stay in maintenance mode.

If the project continues forward, the next step is to define the next authority package before expanding scope.
