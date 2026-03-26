# E5 REAL_SAMPLE_LEDGER

## 说明

- 下表只记录真实 Telegram 触发样本
- `counts_toward_e5_completion` 只表示是否计入 E5 完成口径
- 历史样本不因为“是真实样本”就自动算作 E5 已完成证据

| sample_id | timestamp | real_trigger | evidence_complete | risk_level | response_status | ledger_role | counts_toward_e5_completion | note |
|---|---|---|---|---|---|---|---|---|
| `sample_20260325_170734_9fc71a12` | 2026-03-25T17:07:34 | yes | no | low | n/a | historical_failure_baseline | no | `outbox_record` 缺失；对应正式 failure case `fail_20260325_171610` |
| `sample_20260325_173304_96f60976` | 2026-03-25T17:33:04 | yes | no | unknown | chat | historical_gap_baseline | no | 缺 `normalized_event` / `openemotion_result`，仅保留真实触发痕迹 |
| `sample_20260325_173407_9f6575e5` | 2026-03-25T17:34:07 | yes | no | unknown | chat | historical_gap_baseline | no | 缺 `normalized_event` / `openemotion_result`，仅保留真实触发痕迹 |
| `sample_20260325_173722_48cdea76` | 2026-03-25T17:37:22 | yes | no | unknown | chat | historical_gap_baseline | no | 缺 `normalized_event` / `openemotion_result`，仅保留真实触发痕迹 |
| `sample_20260325_173811_22674d22` | 2026-03-25T17:38:11 | yes | no | unknown | chat | historical_gap_baseline | no | 缺 `normalized_event` / `openemotion_result`，仅保留真实触发痕迹 |
| `sample_20260325_173917_b1b8bf3f` | 2026-03-25T17:39:17 | yes | no | unknown | chat | historical_gap_baseline | no | 缺 `normalized_event` / `openemotion_result`，仅保留真实触发痕迹 |
| `sample_20260325_175906_9ce22ea4` | 2026-03-25T17:59:06 | yes | yes | low | chat | admission_success_baseline | no | 完整真实样本；用于 E4→E5 准入底账 |
| `sample_20260325_175931_c62a411e` | 2026-03-25T17:59:31 | yes | yes | low | chat | admission_success_baseline | no | 完整真实样本；用于 E4→E5 准入底账 |
| `sample_20260325_180013_540e7b4e` | 2026-03-25T18:00:13 | yes | yes | low | chat | admission_success_baseline | no | 完整真实样本；证明高风险文案不等于高风险命中 |
| `sample_20260325_200847_4d2b5dae` | 2026-03-25T20:08:47 | yes | yes | high | waiting_input | admission_success_baseline | no | 完整真实样本；解除 E4→E5 高风险准入阻塞 |

## 当前统计

- 历史真实触发总数：`10`
- 历史完整成功样本：`4`
- 历史不完整样本：`6`
- 当前 E5 窗口内计数样本：`0`
