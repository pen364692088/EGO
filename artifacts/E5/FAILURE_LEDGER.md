# E5 FAILURE_LEDGER

## 说明

- 这里只记录真实 Telegram 主链相关失败与未收口 gap
- integration 级失败不计入 E5 真实观察失败账本
- 若结论来自不完整 artifact 推断，会明确标注为 `inferred_from_gap`

| failure_or_gap_id | related_sample | trigger_type | cause_type | status | retest_status | counts_as_closed_failure | note |
|---|---|---|---|---|---|---|---|
| `fail_20260325_171610` | `sample_20260325_170734_9fc71a12` | real_telegram | delivery_error / capture_gap | 已关闭 | 已复测 | yes | `outbox_record` 缺失；已有正式 failure case，且 `sample_20260325_175931_c62a411e` 作为复测证据 |
| `gap_20260325_173304_96f60976` | `sample_20260325_173304_96f60976` | real_telegram | evidence_gap | 未归因 | 未复测 | no | `inferred_from_gap`：缺 `normalized_event` / `openemotion_result` |
| `gap_20260325_173407_9f6575e5` | `sample_20260325_173407_9f6575e5` | real_telegram | evidence_gap | 未归因 | 未复测 | no | `inferred_from_gap`：缺 `normalized_event` / `openemotion_result` |
| `gap_20260325_173722_48cdea76` | `sample_20260325_173722_48cdea76` | real_telegram | evidence_gap | 未归因 | 未复测 | no | `inferred_from_gap`：缺 `normalized_event` / `openemotion_result` |
| `gap_20260325_173811_22674d22` | `sample_20260325_173811_22674d22` | real_telegram | evidence_gap | 未归因 | 未复测 | no | `inferred_from_gap`：缺 `normalized_event` / `openemotion_result` |
| `gap_20260325_173917_b1b8bf3f` | `sample_20260325_173917_b1b8bf3f` | real_telegram | evidence_gap | 未归因 | 未复测 | no | `inferred_from_gap`：缺 `normalized_event` / `openemotion_result` |

## 当前判断

- 当前正式登记并关闭的真实失败：`1`
- 当前仍悬空的历史真实 gap：`5`
- 这些 gap 不能拿来报“稳定运行”
- 在 E5 完成前，这 5 个 gap 至少需要明确：
  - 是否补建正式 failure case
  - 是否只作为 pre-E5 collector 历史缺口归档关闭
