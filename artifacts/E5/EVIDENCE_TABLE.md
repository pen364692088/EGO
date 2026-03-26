# E5 EVIDENCE_TABLE

| claim | evidence | result |
|---|---|---|
| E5 已具备启动条件 | `artifacts/telegram_real_mainline_v1/reports/E4_TO_E5_ADMISSION_REPORT.md` | 成立 |
| 仓内存在真实 Telegram 主链样本底账 | `artifacts/telegram_real_mainline_v1/real_telegram/*/sample.json` 共 `10` 个目录 | 成立 |
| 仓内存在完整真实成功样本 | `sample_20260325_175906_9ce22ea4`、`sample_20260325_175931_c62a411e`、`sample_20260325_180013_540e7b4e`、`sample_20260325_200847_4d2b5dae` | 成立 |
| 仓内存在真实失败样本并已复测 | `artifacts/telegram_real_mainline_v1/failure_cases/failure_fail_20260325_171610.json` | 成立 |
| 历史真实样本中存在证据不完整 gap | `sample_20260325_173304_96f60976` 等 5 个样本缺 `normalized_event` / `openemotion_result`；`sample_20260325_170734_9fc71a12` 缺 `outbox_record` | 成立 |
| 观察期不能拿 simulated/unit 冒充 | `artifacts/E5/OBSERVATION_WINDOW.md` 中已写入 source constraint | 成立 |
| 当前只能报“E5 已启动” | `artifacts/E5/TASK_REPORT.md` 明确写出“已启动，未完成” | 成立 |
| 当前不能报“稳定运行” | `artifacts/E5/TASK_REPORT.md`、`artifacts/E5/OBSERVATION_WINDOW.md` 明确禁止升级口径 | 成立 |

## 关键数字

| metric | value |
|---|---|
| 历史真实触发总数 | `10` |
| 历史完整 evidence bundle 样本 | `4` |
| 历史高风险命中样本 | `1` |
| 正式登记的真实失败样本 | `1` |
| 历史未收口 gap | `5` |
| E5 窗口内当前计数样本 | `0` |
