# SELF_AWARE_STEP_04A_behavioral_influence_proof

```yaml
task_id: SELF_AWARE_STEP_04A
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: pending
```

## real_goal

在不破坏 governor / boundary constitution 的前提下，补一条正式的 `self-model intervention -> downstream behavior change` 证明链，判断 `MVP13` 是否能从“component-level verified but stage unproven”继续升到更强状态。

## success_criteria

- 设计一条受治理、可 replay、可审计的 intervention 链
- 明确干预点来自 `MVP13` 新 self-model，而不是 legacy `SelfModelV0`
- 在受控前提下观测到后续 action bias / decision tendency / routed behavior 的可复验变化
- 不允许新 self-model 绕过 governor 或越权成为最终 authority

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
main_chain_status: component proof published; behavioral influence proof pending
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

## next_minimal_closure_action

先设计一条最小、受治理、可 replay 的 intervention harness，明确区分 `legacy self-model bias` 与 `MVP13 new self-model influence`，再决定是补 bounded wiring change 还是收口为“当前阶段仍不可通过”。
