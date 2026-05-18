# SELF_AWARE_STEP_06B_EXECUTION_REPORT_20260329

## Summary

Step06B 完成了 `MVP15 reflection / counterfactual behavioral relevance` 的最小正式证明链。

本轮没有把 reflection / counterfactual 升成 direct behavioral authority，而是在
当前已 boundedly converged 的 `reflection_guidance` mainline surface 上，证明它们会对：

- `POST /plan`
- `POST /decision/target` explanation

产生受治理、可 paired、可 replay 的 downstream relevance。

## Authority Source

- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_06A_REVIEW_20260329.md`
- `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- `OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp15/MVP15_EXIT_CRITERIA.md`
- `OpenEmotion/emotiond/reflection_adapter.py`
- `OpenEmotion/emotiond/reflection_engine/`
- `OpenEmotion/emotiond/self_counterfactual.py`
- `OpenEmotion/emotiond/core.py`

## Chosen Proof Line

本轮选择的是 bounded relevance proof，而不是 direct action proof：

1. 保持 `proposal_discipline = proposal_only`
2. 保持 `behavioral_authority = none`
3. 只让强 reflection/counterfactual 信号影响：
   - `/plan` 的 `constraints`
   - `/plan` 的 `key_points`
   - `/plan` 的 `language_guidance.reflection_considerations`
   - `/decision/target` explanation 的 `reflection_relevance`
4. 不让 reflection/counterfactual 直接改写 selected action

## Implementation

### 1. bounded relevance helper

`emotiond/core.py` 当前新增：

- `_dedupe_strings(...)`
- `_build_reflection_relevance(...)`

正式职责：

- 从 `reflection_guidance` 中读取：
  - `counterfactual.mode`
  - `counterfactual.info_seeking_weight`
  - `counterfactual.risk_tolerance`
  - `counterfactual.preferred_actions`
  - `reflection.pending_proposals`
  - `reflection.latest_job.proposal_count`
- 生成 bounded downstream hints，而不是 direct authority

### 2. /plan bounded downstream relevance

`generate_plan(...)` 现在会在强信号下：

- 追加 bounded `constraints`
- 追加 bounded `key_points`
- 在 `language_guidance` 中记录 `reflection_considerations`
- 保留原始 `reflection_guidance` 作为可 replay surface

### 3. /decision explanation bounded downstream relevance

`generate_explanation_v31(...)` 现在会在强信号下追加：

- `reflection_relevance`

该字段只记录：

- `proposal_discipline`
- `behavioral_authority`
- `considerations`

因此 explanation surface 获得了 bounded downstream relevance，但没有取得
direct decision authority。

### 4. paired proof harness

新增：

- `OpenEmotion/tests/mvp15/test_behavioral_relevance_formal_proof.py`

proof harness 特性：

- same target
- same target_id
- same endpoint
- same entry path
- same behavioral authority contract
- 唯一变量是 `reflection_guidance`

control / intervention 的区别只在：

- `counterfactual.mode`
- `info_seeking_weight`
- `risk_tolerance`
- `preferred_actions`
- `pending_proposals`
- `latest_job.proposal_count`

## Verification Result

### Static / preflight

- `python3 -m py_compile OpenEmotion/emotiond/core.py OpenEmotion/tests/mvp15/test_behavioral_relevance_formal_proof.py`
  - passed
- `git diff --check`
  - passed

### Tests

已通过：

- `OpenEmotion/tests/mvp15/test_behavioral_relevance_formal_proof.py`
- `OpenEmotion/tests/mvp15/test_mainline_resolution.py`
- `OpenEmotion/tests/mvp15/test_mainline_wiring.py`
- `OpenEmotion/tests/mvp15/test_reflection_infra.py`
- `OpenEmotion/tests/test_decision_target_api.py`
- `OpenEmotion/tests/test_plan_api.py`

合计：

- `40 passed`

## What Step06B Proves

- `reflection_guidance` 不再只是 bounded consumer presence
- 在当前真实 mainline surface 上，reflection/counterfactual guidance 已经具有
  bounded downstream behavioral relevance
- paired proof 使用同一入口、同一 target、同一 target_id
- proposal discipline 仍保持为 `proposal_only`
- behavioral authority 仍保持为 `none`

## What Step06B Does Not Prove

- 不证明 `MVP15 passed`
- 不证明 `Stage 6 passed`
- 不证明 reflection/counterfactual 已直接改变 action selection
- 不证明长期 utility / 长期稳定性已经成立
- 不证明 `MVP16 unblocked`

## Formal Outcome

Step06B 的正式结论是：

- `MVP15 reflection/counterfactual guidance now shows bounded downstream behavioral relevance on the current /plan and /decision/target explanation mainline surfaces`
- `proposal_only` 与 `behavioral_authority = none` 仍被保留
- `OE_MVP:15` 可继续保持为：`component-level verified but stage unproven`
- 下一步唯一切到：`SELF_AWARE_STEP_07_mvp16_unblock.md`
