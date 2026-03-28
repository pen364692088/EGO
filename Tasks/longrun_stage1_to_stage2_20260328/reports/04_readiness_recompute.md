# Step 04 — Readiness Recompute

## 改了什么

- 用最新 `T07.3` mixed rerun 结果重算了 Stage 2 readiness。
- 生成了机器可读判定：
  - `runtime/stage2_readiness_decision.json`
- 把这次判定的适用范围明确写成：`当前 Layer 2 mixed baseline 的负向 readiness 映射`，不是 promotion 充分证明。
- 在 `report_consistency repair #1` 后，改用 `sample_level_unique_violation_type` 重新解释主 violation class 统计，同时保留 raw match 统计用于对照。

## 我自 review 发现并修了什么

- 明确区分了两个层级：
  - `T07.3 rerun succeeded`
  - `readiness still not ready`
- 没有把 mixed baseline 重建误报成 Stage 2 promotion。
- 追加了权威反证：
  - `OpenEmotion/artifacts/roadmap/evidence/MVP11_5_T07.3.md` 明确写明 `T07.3` 是分布稳定性与可观测性证据，不是 promotion-readiness proof。

## 我实际跑了什么验证

- 读取并解释：
  - `OpenEmotion/artifacts/self_report/t07.3_mixed_layer2_results.json`
  - `OpenEmotion/docs/archive/mvp11/MVP11_5_READINESS_CRITERIA.md`
  - `OpenEmotion/artifacts/testbot/intent_alignment_report.json`
- 当前 readiness 判定：
  - `decision = not_ready`
  - `formal_stage_outcome = stay_stage1`
- 关键 blocker：
  - `numeric_leak != 0`，当前为 `25`（样本级唯一 violation type），raw matches 仍为 `38`
  - `overall_violation_rate = 0.71`
  - `sample_size = 100`，低于 readiness 建议累计规模 `>= 200`
  - `certainty_upgrade = 30` / `commitment_upgrade = 29`（样本级唯一 violation type）
  - `Layer 3 natural evidence` 仍缺
  - `Gate/report closure` 仍不完整

## 还没证明什么

- 还没证明任何 blocker 已被修掉。
- 还没达到可以进入 `Stage 2` 的 `V4 / E4` 级证据。
- `report_consistency` 已收正，但这还不是 readiness 修复本身。
- 下一步是进入下一轮 bounded strengthening repair，当前候选转为 `certainty_upgrade`，同时继续保留 evidence-closure blockers。
