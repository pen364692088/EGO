# SELF_AWARE_STEP_04F_EXECUTION_REPORT_20260329

## Summary

Step04F 完成了 `MVP13 behavioral influence` 的最小正式证明链。

这轮不再停在局部 `core.select_action()` 或 legacy comparative path，而是命中了
真实 `emotiond` decision mainline：

- `POST /decision/target?test_mode=true`
- `emotiond.api.make_decision_target()`
- `emotiond.core.select_action_with_explanation_v31()`
- `emotiond.core.generate_explanation_v31()`
- `emotiond.core.score_action_with_target()`
- `emotiond.core._get_owner_backed_action_bias()`

paired intervention/control 样本使用同一 target、同一 target_id、同一 API
入口、同一 deterministic decision point，只改变 formal owner 的
`confidence_by_domain["action:<action>"]`，最终把决策从 `approach`
稳定翻转到 `withdraw`。

## Chosen Proof Path

Step04F 选择的唯一正式 proof path 是：

- formal owner field:
  - `openemotion/self_model/model.py::SelfModel.confidence_by_domain`
- mainline endpoint:
  - `POST /decision/target?test_mode=true`
- downstream decision point:
  - `generate_explanation_v31()` / `select_action_with_target()`

原因：

1. 这是当前仓库里最短、最真实、最可 replay 的 `emotiond` decision mainline。
2. `generate_explanation_v31()` 和 `select_action_with_target()` 都消费
   `score_action_with_target()`，而后者会真实引入
   `_get_owner_backed_action_bias()`。
3. 它避免了普通 `/decision` 路径在 `test_mode` 下仍以旧 candidate
   score 口径选 top candidate 的不一致问题。
4. 它同时覆盖：
   - API trigger
   - explanation generation
   - decision persistence
   - same-point intervention/control comparison

## Paired Intervention / Control

测试固定了：

- same target: `mvp13_behavior_target`
- same target_id: `session:mvp13_behavior_target`
- same request payload
- same deterministic endpoint: `POST /decision/target?test_mode=true`
- same base predictions: all zero
- same relationship state

只改变 formal owner 字段：

### Control

```text
confidence_by_domain["action:approach"] = 1.0
confidence_by_domain["action:withdraw"] = 0.0
```

结果：

- action = `approach`
- explanation.selected = `approach`
- explanation.candidates[0].action = `approach`

### Intervention

```text
confidence_by_domain["action:approach"] = 0.0
confidence_by_domain["action:withdraw"] = 1.0
```

结果：

- action = `withdraw`
- explanation.selected = `withdraw`
- explanation.candidates[0].action = `withdraw`
- DB latest decision for the same target also becomes `withdraw`

## Legacy Exclusion

这轮 proof 明确禁止 legacy-only self-model 路径参与因果证明。

测试里把 legacy fallback 替换成：

- `LegacyMustNotDriveProof.get_action_bias() -> raise AssertionError`

最终 paired proof 仍然通过，说明本轮 formal proof 不依赖
`emotiond/self_model/*` 的 legacy-only bias 字段。

## Verification Result

本轮实际 verifier 结果：

- `python -m py_compile OpenEmotion/tests/mvp13/test_behavioral_influence_formal_proof.py`
  - passed
- `pytest -q OpenEmotion/tests/mvp13/test_behavioral_influence_formal_proof.py OpenEmotion/tests/mvp13/test_owner_backed_decision_surface.py`
  - `4 passed`
- `pytest -q OpenEmotion/tests/test_decision_target_api.py OpenEmotion/tests/test_mvp31_explanation.py`
  - `17 passed`
- independent reviewer:
  - `OpenEmotion/roadmap/SELF_AWARE_STEP_04F_REVIEW_20260329.md`

## What Step04F Proves

- formal owner `confidence_by_domain["action:<action>"]` 已经能够在真实
  `emotiond` decision API mainline 上改变同一决策点的输出
- 这条因果链可 replay、可比较、可审计
- proof path 不依赖 legacy-only `emotiond/self_model/*`
- 在当前 MVP13 contract 与当前 controlled paired harness 口径下，这足以满足：
  - `behavioral_influence_e4_proven`

## What Step04F Does Not Prove

- 不证明长期阶段已经正式进入 `Stage 4`
- 不证明 `OE_MVP:16` 已解阻
- 不证明更高层的 endogenous drives / reflection / open developmental self 已成立

## Formal Outcome

Step04F 的正式结论是：

- `MVP13 behavioral influence proof = established on the owner-backed emotiond decision mainline`
- `MVP13` 的核心缺口从“behavioral influence 未证”收敛为“已证”
- 后续主路线唯一切到 `SELF_AWARE_STEP_05_mvp14_formal_proof.md`
