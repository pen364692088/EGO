# MVP12 Controlled Observation Report

- generated_at: `2026-04-02T00:14:15.031158`
- artifacts_dir: `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260402_001410`
- session_id: `session:mvp12:controlled`
- verification_level: `V3`
- completion_class: `controlled_evidence_only`

## Summary

- total_cycles: `10`
- governance_violation_count: `0`
- replay_consistent: `True`
- shadow_revision_final: `67`
- unique_candidate_hash_sets: `9`
- direct_real_cycles: `4`
- direct_real_windows: `2`
- direct_real_source_type: `observation_record_v1`
- direct_real_transport_sources: `['runtime_harness']`

## Batches

### synthetic_idle
- cycles: `3`
- observation_source: `synthetic`
- trigger: `idle`
- governance_violation_count: `0`
- candidate_hashes: `['16001a0a7948d181', 'd226d591bc6840c5']`
- observation_ref_count: `0`
- observation_count: `3`

### synthetic_tension
- cycles: `1`
- observation_source: `synthetic`
- trigger: `unresolved_tension`
- governance_violation_count: `0`
- candidate_hashes: `['9f45cbb837d891f0', 'c94964b85ae6ca7e']`
- observation_ref_count: `0`
- observation_count: `1`

### replay_a
- cycles: `1`
- observation_source: `replay`
- trigger: `replay_event`
- governance_violation_count: `0`
- candidate_hashes: `['18cb55b0f5330841']`
- observation_ref_count: `0`
- observation_count: `1`

### replay_b
- cycles: `1`
- observation_source: `replay`
- trigger: `replay_event`
- governance_violation_count: `0`
- candidate_hashes: `['18cb55b0f5330841']`
- observation_ref_count: `0`
- observation_count: `1`

### direct_real_window_01
- cycles: `2`
- observation_source: `direct_real`
- trigger: `window`
- governance_violation_count: `0`
- candidate_hashes: `['4bd485d2074671e0']`
- observation_ref_count: `4`
- observation_count: `2`

### direct_real_window_02
- cycles: `2`
- observation_source: `direct_real`
- trigger: `window`
- governance_violation_count: `0`
- candidate_hashes: `['e300308075d6dab9']`
- observation_ref_count: `4`
- observation_count: `2`

## Gate

- [x] no_direct_reply_authority
- [x] no_direct_execution_authority
- [x] no_response_plan_injection
- [x] shadow_only_writeback

## Notes

- This is controlled evidence only. It does not prove live enablement or action authority handoff.
- The sandbox still has no direct reply authority and no direct execution authority.
