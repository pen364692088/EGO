# Telegram Failure Cases

这里存放从真实 Telegram 故障沉淀下来的固定回归样本。

规则：

1. 每个真实故障至少对应一个 `.json` fixture
2. fixture 必须来自真实 session log / trace，不允许凭空编
3. 修复前先补 fixture，再补 replay test 断言
4. fixture 进入仓库后，`tests/test_telegram_failure_case_replay.py` 必须能自动消费

最小字段：

- `case_id`
- `description`
- `initial_state`
- `turn`
- `expected`

推荐流程：

1. 用 `tools/capture_telegram_failure_case.py` 从 `data/session_logs/*.jsonl` 生成草稿
2. 补齐 `initial_state` 和 `expected`
3. 跑 `tests/test_telegram_failure_case_replay.py`
4. 再跑 `tools/run_telegram_mainline_regression.sh`
