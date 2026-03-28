# Step 06 — Rerun After Repairs

## 改了什么

- 在 `report_consistency repair #1` 后，重新跑了 `T07.3 mixed Layer2 rerun`。
- 新 artifact 已写回：
  - `OpenEmotion/artifacts/self_report/t07.3_mixed_layer2_results.json`

## 我自 review 发现并修了什么

- 这轮 rerun 的统计解释必须与 repair 目标绑定：
  - 允许 `top_violation_classes` 下降
  - 不允许 `overall_violation_rate / would_block_rate` 被偷偷改低
- 已确认本轮只收正 summary 口径，没有把 block / overall rate 做成假改善。

## 我实际跑了什么验证

- `cd OpenEmotion && ../EgoCore/.venv/bin/python tests/test_t07_3_mixed_layer2_rerun.py`
- 当前 rerun 关键输出：
  - `sample_size = 100`
  - `overall_violation_rate = 0.71`
  - `would_block_rate = 0.71`
  - `top_violation_classes = certainty_upgrade(30), commitment_upgrade(29), numeric_leak(25)`
  - `raw_violation_class_matches = commitment_upgrade(47), certainty_upgrade(45), numeric_leak(38)`
  - `results = 100`（全量保留，可供后续复核）

## 还没证明什么

- rerun 仍然没有让系统达到 `ready`
- rerun 只说明 report consistency 已收正，不代表 strengthening blockers 已解决
- 下一步仍需新的 bounded repair 候选，而不是直接 admission
