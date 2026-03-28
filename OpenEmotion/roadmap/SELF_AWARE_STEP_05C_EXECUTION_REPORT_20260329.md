# SELF_AWARE_STEP_05C_EXECUTION_REPORT_20260329

## Summary

Step05C 完成了 `MVP14 drive behavioral influence` 的最小正式证明链。

这轮不再停在 helper-level 或静态 wiring 上，而是命中了当前已经 boundedly
converged 的真实 `emotiond` decision mainline：

- `POST /decision/target?test_mode=true&target_id=...`
- `emotiond.api.make_decision_target()`
- `emotiond.core.select_action_with_explanation_v31()`
- `emotiond.core.generate_explanation_v31()`
- `emotiond.core.score_action_with_target()`
- `emotiond.core._get_drive_owner_backed_action_bias()`
- `emotiond.drive_adapter.DriveStateAdapter.get_owner_backed_action_bias()`
- `emotiond.drives.manager.DriveManager.get_priority_bias()`

paired intervention/control 样本使用同一 target、同一 target_id、同一 API
入口、同一 deterministic decision point，只改变 formal owner
`emotiond/drives/*` 的 drive priorities，最终把决策从 `approach`
稳定翻转到 `withdraw` / `boundary`。

## Chosen Proof Path

Step05C 选择的唯一正式 proof path 是：

- formal owner:
  - `emotiond/drives/manager.py::DriveManager.get_priority_bias()`
- bounded mainline surface:
  - `emotiond/drive_adapter.py::get_owner_backed_action_bias()`
- real decision entry:
  - `POST /decision/target?test_mode=true`
- downstream decision point:
  - `score_action_with_target()`

原因：

1. 这是当前仓库里最短、最真实、最可 replay 的 `emotiond` 决策主链。
2. Step05B 已经证明 `core.py` 当前决策主链 boundedly converge 到
   `drive_adapter.py`，所以 Step05C 应该直接沿这条主线证明
   `emotiond/drives/*` 的行为因果。
3. `score_action_with_target()` 同时服务 explanation candidates 与最终选中的
   decision action，避免 helper-only proof。
4. 这条路径允许 formal owner 保持在 `emotiond/drives/*`，同时把 adapter
   明确约束为 bounded compatibility surface，而不是新的 authority source。

## Paired Intervention / Control

测试固定了：

- same target: `mvp14_drive_target`
- same target_id: `session:mvp14_drive_target`
- same request payload
- same deterministic endpoint: `POST /decision/target?test_mode=true`
- same base predictions: all zero
- same relationship state
- same self-model bias: disabled to isolate drive effect

只改变 formal owner `DriveManager` 中的 drive intensities。

### Control

高 `completion + exploration`，低 `conservation + verification + stability`。

结果：

- action = `approach`
- explanation.selected = `approach`
- explanation.candidates[0].action = `approach`

### Intervention

高 `conservation + verification + stability`，低 `completion + exploration`。

结果：

- action = `withdraw` 或 `boundary`
- explanation.selected = 当前选中的 defensive action
- explanation.candidates[0].action = 当前选中的 defensive action
- DB latest decision for the same target also updates to the intervention action

## Formal Owner Boundary

这轮 proof 明确区分：

- formal owner：`emotiond/drives/*`
- bounded surface：`emotiond/drive_adapter.py`

adapter 在这轮中的角色仅是：

- 把已 boundedly converged 的主链暴露成可消费 surface
- 将 formal owner 的 priority bias 送入当前 decision scoring point

这轮 proof **不**把 adapter 升格为新的 formal owner。

## Verification Result

本轮实际 verifier 结果：

- `python -m py_compile OpenEmotion/emotiond/core.py OpenEmotion/emotiond/drive_adapter.py OpenEmotion/tests/mvp14/test_drive_behavioral_influence_formal_proof.py`
  - passed
- `pytest -q OpenEmotion/tests/mvp14/test_drive_behavioral_influence_formal_proof.py OpenEmotion/tests/mvp14/test_mainline_wiring.py OpenEmotion/tests/mvp14/test_drive_infra.py OpenEmotion/tests/mvp14/test_drive_integration.py OpenEmotion/tests/mvp14/test_e2e_gate_b.py OpenEmotion/tests/test_decision_target_api.py`
  - `53 passed`
- independent reviewer:
  - `OpenEmotion/roadmap/SELF_AWARE_STEP_05C_REVIEW_20260329.md`

## What Step05C Proves

- `emotiond/drives/*` 的受控变化已经能够在 boundedly converged 的
  `emotiond` decision API mainline 上改变同一决策点的输出
- 这条因果链可 paired、可 replay、可比较、可审计
- 当前 proof grounded on the same `target` / `target_id` / endpoint / decision point
- 在当前 MVP14 contract 与当前 controlled paired harness 口径下，这足以满足：
  - `formal_owner_behavioral_influence_e4_proven`

## What Step05C Does Not Prove

- 不证明 `MVP14 passed`
- 不证明长期阶段已经正式进入 `Stage 5`
- 不证明 `workspace.py` 的 legacy path 已经收敛
- 不证明长期稳定观测已经成立
- 不证明 `MVP16` 已解阻；`MVP15 formal proof` 仍未完成

## Formal Outcome

Step05C 的正式结论是：

- `MVP14 owner-backed behavioral influence = established on the boundedly converged emotiond decision mainline`
- `MVP14` 的核心缺口从 “formal-owner behavioral influence 未证”
  收敛为 “已证”
- 后续主路线唯一切到 `SELF_AWARE_STEP_06_mvp15_formal_proof.md`
