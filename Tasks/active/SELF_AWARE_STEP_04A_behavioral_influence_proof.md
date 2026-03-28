# SELF_AWARE_STEP_04A_behavioral_influence_proof

```yaml
task_id: SELF_AWARE_STEP_04A
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: published
```

## real_goal

在正式进入 `behavioral influence` 证明前，先判定当前仓库是否已经具备唯一、无歧义的 self-model authority；若没有，则把该问题收口为 authority-split diagnosis，并把下一步唯一化到 authority resolution。

## success_criteria

- 明确当前 behavioral proof 所依赖的 self-model authority 是否唯一
- 若 authority split 存在，给出正式诊断并阻止继续构造伪因果证明
- 明确下一步唯一正式入口
- 不允许 adapter 或 bridge 被偷偷升级成正式语义 owner

## authority_source

- `OpenEmotion/roadmap/versions/MVP13.spec.yaml`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_04_EXECUTION_REPORT_20260328.md`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/emotiond/self_model_adapter.py`
- `OpenEmotion/tools/main_chain_wiring_check.py`
- `OpenEmotion/tools/e2e_self_model_adapter.py`
- `EgoCore/POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md`

## current_layer

```yaml
current_layer: strategy
main_chain_status: component proof published; behavioral influence proof blocked by authority split
```

## required_artifacts

- `OpenEmotion/artifacts/verification/causal_intervention_results.json`
- `OpenEmotion/artifacts/verification/CAUSAL_INTERVENTION_REPORT.md`
- `OpenEmotion/artifacts/mvp13/mirror_metrics.json`
- `OpenEmotion/docs/archive/E2E_SELF_MODEL_ADAPTER_REPORT.md`

## required_tests

- `pytest -q tests/mvp13/test_self_model_infra.py`
- `pytest -q tests/mvp13/test_integration.py`
- `pytest -q tests/mvp13/test_e2e_gate_b.py`
- `python tools/main_chain_wiring_check.py`
- `python tools/e2e_self_model_adapter.py`
- `new formal proof harness or replayable intervention check that isolates MVP13 new self-model influence`

## workflow_requirements

```yaml
full_spec_required: true
self_reviewer_required: true
independent_reviewer_required: true
verifier_required: true
publisher_required: true
```

## promotion_blockers

- 当前主链行为偏置仍由 legacy `SelfModelV0` 提供
- shadow dual-run 不等于 behavior influence
- 旧 causal report 的 wiring 结论已过时，但行为影响未证这条仍未被 fresh verifier 推翻
- `openemotion/self_model/*` 与 `emotiond/self_model/*` 不是同一 authority

## next_minimal_closure_action

已完成 authority-split diagnosis；下一步切到 `SELF_AWARE_STEP_04B_self_model_authority_resolution.md`。
