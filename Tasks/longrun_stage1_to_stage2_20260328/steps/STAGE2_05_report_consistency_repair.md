# STAGE2_05_report_consistency_repair

```yaml
step_id: STAGE2-05-REPORT-CONSISTENCY
type: repair
status: completed
repair_loop_index: 1
blocker_class: report_consistency
```

## real_goal

Correct the mixed Layer 2 rerun summary so repeated regex hits do not get over-reported as additional violation-class events, while preserving the raw match counts for auditability.

## success_criteria

- `T07.3` summary reports primary violation classes using `sample_level_unique_violation_type`
- raw regex match counts remain available for audit comparison
- post-repair rerun completes and the readiness recompute uses the corrected summary semantics

## authority_source

- `OpenEmotion/docs/archive/mvp11/T07_3_MIXED_LAYER2_RERUN.md`
- `OpenEmotion/artifacts/roadmap/evidence/MVP11_5_T07.3.md`
- `OpenEmotion/tests/test_t07_3_mixed_layer2_rerun.py`
- `OpenEmotion/emotiond/response_intent_checker.py`

## current_layer

```yaml
current_layer: implementation
main_chain_status: shadow
```

## required_artifacts

- `reports/05_report_consistency_repair.md`
- `reports/06_rerun_after_repairs.md`
- refreshed `runtime/stage2_readiness_decision.json`

## required_tests

- `./EgoCore/.venv/bin/python -m pytest -s -q OpenEmotion/tests/test_t07_3_mixed_layer2_summary.py OpenEmotion/tests/test_response_intent_checker.py`
- `cd OpenEmotion && ../EgoCore/.venv/bin/python tests/test_t07_3_mixed_layer2_rerun.py`

## promotion_blockers

- repair silently changes `overall_violation_rate` or `would_block_rate`
- repair removes raw match visibility

## next_minimal_closure_action

Close this repair loop, then move to the next bounded strengthening candidate.
