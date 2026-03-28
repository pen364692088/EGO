# SELF_AWARE_STEP_06B_reflection_behavioral_relevance_formal_proof

```yaml
task_id: SELF_AWARE_STEP_06B
created_at: "2026-03-29T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: pending
```

## real_goal

在当前已 boundedly converged 的 `reflection_guidance` mainline surface 上，证明 reflection / counterfactual proposal 对后续 plan / explanation / maintenance prioritization 具有受治理、可 replay、可 paired 对照的 behavioral relevance。

## success_criteria

- 在同一真实入口上形成 control / intervention paired proof
- intervention 唯一变量来自 reflection / counterfactual guidance
- proposal discipline 仍保持为 `proposal_only`
- 结果表现为 downstream relevance，而不是直接 authority takeover

## authority_source

- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_REVIEW_20260329.md`
- `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- `OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp15/MVP15_EXIT_CRITERIA.md`
- `OpenEmotion/emotiond/reflection_adapter.py`
- `OpenEmotion/emotiond/reflection_engine/`
- `OpenEmotion/emotiond/self_counterfactual.py`
- `OpenEmotion/emotiond/core.py`

## current_layer

```yaml
current_layer: verification
main_chain_status: bounded reflection_guidance surface is present on /plan and /decision explanation, but behavioral relevance remains unproven
```

## required_artifacts

- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_REVIEW_20260329.md`

## required_tests

- `pytest -q OpenEmotion/tests/mvp15/test_mainline_resolution.py`
- `python OpenEmotion/tools/verify_mvp15_mainline_wiring.py --json`
- `paired intervention/control proof on current mainline`
- `independent reviewer on proposal-discipline / authority boundary`
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

- reflection_guidance 目前只证明 bounded consumer presence
- behavioral relevance 还没有 paired proof
- proposal discipline 不能在 proof harness 中被破坏

## next_minimal_closure_action

设计一条受治理、可 replay、同入口 paired harness，证明 reflection / counterfactual guidance 会改变 downstream relevance，但不会取得 direct authority。
