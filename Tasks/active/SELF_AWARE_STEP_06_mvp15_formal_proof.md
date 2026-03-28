# SELF_AWARE_STEP_06_mvp15_formal_proof

```yaml
task_id: SELF_AWARE_STEP_06
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: pending
```

## real_goal

把 `MVP15` 从“reflection artifacts 存在、质量检查部分存在”推进到“reflection / counterfactual 会回写并改变后续决策”的 formal proof。

## success_criteria

- reflection capability 存在
- counterfactual capability 存在
- outputs 保持 proposal discipline
- 至少一条“反思 -> 修正 -> 后续行为变化”证据链成立

## authority_source

- `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- `OpenEmotion/docs/mvp15/*`
- `OpenEmotion/tests/mvp15/*`

## current_layer

```yaml
current_layer: verification
main_chain_status: 启用
```

## required_artifacts

- `OpenEmotion/artifacts/mvp15/MVP15_PERSISTENCE_INTEGRITY_REPORT.md`
- `OpenEmotion/artifacts/mvp15/quality_report.json`

## required_tests

- `pytest -q tests/mvp15/test_reflection_infra.py`
- `python tools/mvp15_artifact_integrity_check.py`
- `python tools/mvp15_funnel_check.py`

## promotion_blockers

- reflection 质量报告未自动等于行为因果证明
- counterfactual 与后续策略修正链未正式收口

## next_minimal_closure_action

补一条完整的 reflection causal chain，并定义 admission 可接受的最小证据包。

