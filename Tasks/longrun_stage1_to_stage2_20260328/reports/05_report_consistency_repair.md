# Step 05 — Report Consistency Repair

## 改了什么

- 把 `T07.3` mixed rerun 的主 violation class 统计从“raw regex matches”收正为“每样本唯一 violation type”。
- 保留了 `raw_violation_class_matches`，避免把这次修复做成信息丢失。
- 把 `fabricated_*_share` 调整为与 fabrication 场景本身对齐的 category detection share，避免长期误报为接近 `0`。
- rerun artifact 现在保存全量 `100` 条结果，不再只截前 `30` 条。
- 这轮 repair 的目标是修 `report_consistency`，不是声称已经修掉 `numeric_leak` 本身。

## 我自 review 发现并修了什么

- 发现 `T07.3` 当前 summary 会把同一条回复里的重复 `numeric_leak` regex 命中累计成多个 class events。
- verifier 还抓到一个真实 bug：`summarize_results()` 在没有 `safe_controls` 的最小样本里会触发 `KeyError`；已修。

## 我实际跑了什么验证

- `./EgoCore/.venv/bin/python -m pytest -s -q OpenEmotion/tests/test_t07_3_mixed_layer2_summary.py OpenEmotion/tests/test_response_intent_checker.py`
- `cd OpenEmotion && ../EgoCore/.venv/bin/python tests/test_t07_3_mixed_layer2_rerun.py`
- 修后关键变化：
  - `overall_violation_rate = 0.71`（未被美化）
  - `would_block_rate = 0.71`（未被美化）
  - `numeric_leak`: `38 raw matches -> 25 sample-level unique hits`
  - `certainty_upgrade`: `45 raw matches -> 30 sample-level unique hits`
  - `commitment_upgrade`: `47 raw matches -> 29 sample-level unique hits`

## 还没证明什么

- 还没证明 `numeric_leak` 已经被根因修掉。
- 还没证明 `certainty_upgrade / commitment_upgrade` 已被压到 readiness 可接受范围。
- 还没证明 `sample_size / Layer 3 natural evidence / gate-report closure` 已补齐。
