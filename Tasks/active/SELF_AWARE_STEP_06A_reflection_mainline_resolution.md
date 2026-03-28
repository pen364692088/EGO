# SELF_AWARE_STEP_06A_reflection_mainline_resolution

```yaml
task_id: SELF_AWARE_STEP_06A
created_at: "2026-03-29T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: published
```

## real_goal

把 `MVP15` 从“shadow artifact only”推进到“存在正式 mainline writeback / downstream consumer”，为后续 reflection / counterfactual causal proof 提供唯一正式入口。

## success_criteria

- reflection formal owner 与 counterfactual formal owner 的 consumer 位置唯一化
- shadow artifact path 与正式 writeback / downstream consumer 明确区分
- 至少存在一条受治理、可 replay 的 mainline consumer path
- 不把 reflection proposal 直接升格为 authority

## authority_source

- `OpenEmotion/roadmap/SELF_AWARE_STEP_06_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- `OpenEmotion/docs/mvp15/`
- `OpenEmotion/emotiond/reflection_shadow.py`
- `OpenEmotion/emotiond/reflection_engine/`
- `OpenEmotion/emotiond/self_counterfactual.py`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/emotiond/api.py`
- `OpenEmotion/emotiond/workspace.py`

## current_layer

```yaml
current_layer: implementation
main_chain_status: bounded reflection_guidance consumer is now present on /plan and /decision explanation; behavioral relevance remains unproven
```

## required_artifacts

- `OpenEmotion/roadmap/SELF_AWARE_STEP_06_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_06_REVIEW_20260329.md`

## required_tests

- `pytest -q OpenEmotion/tests/mvp15/test_mainline_wiring.py`
- `python OpenEmotion/tools/verify_mvp15_mainline_wiring.py --json`
- `independent reviewer on authority / writeback boundary`
- `git diff --check`

## workflow_requirements

```yaml
full_spec_required: true
self_reviewer_required: true
independent_reviewer_required: true
verifier_required: true
publisher_required: true
```

## promotion_blockers

- behavioral relevance paired proof still missing
- workspace 仍不在当前 bounded convergence 范围
- proposal discipline 不能在后续 relevance proof 中被破坏

## next_minimal_closure_action

当前 bounded mainline consumer 已唯一化；下一步进入 `SELF_AWARE_STEP_06B_reflection_behavioral_relevance_formal_proof.md`。
