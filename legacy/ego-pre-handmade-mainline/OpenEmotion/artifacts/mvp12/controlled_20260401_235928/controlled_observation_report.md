# MVP12 Controlled Observation Report

- generated_at: `2026-04-01T23:59:32.530195`
- artifacts_dir: `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260401_235928`
- session_id: `session:mvp12:controlled`
- verification_level: `V3`
- completion_class: `controlled_evidence_only`

## Summary

- total_cycles: `10`
- governance_violation_count: `0`
- replay_consistent: `True`
- shadow_revision_final: `57`
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
- candidate_hashes: `['2d3d70c08295ec7b', 'b7a3cec02fde5d59']`
- observation_ref_count: `0`
- observation_count: `3`

### synthetic_tension
- cycles: `1`
- observation_source: `synthetic`
- trigger: `unresolved_tension`
- governance_violation_count: `0`
- candidate_hashes: `['59a8f951eef373e8', '32e1b5c308b8943a']`
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
- candidate_hashes: `['444a6df270614d5e']`
- observation_ref_count: `4`
- observation_count: `2`

### direct_real_window_02
- cycles: `2`
- observation_source: `direct_real`
- trigger: `window`
- governance_violation_count: `0`
- candidate_hashes: `['a0e9a239d1b88ec0']`
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
