# P0 WORDING_CONFLICTS

## 已确认冲突

| conflict_id | location | original_wording | issue_type | evidence_level_ceiling | action |
|---|---|---|---|---|---|
| P0-WC-001 | `README.md:7` | `已完成稳态收口` | 口径高于当前证据；易被理解为 E5/E6 稳定态 | E4 / E5 准入 | 已降级为“已完成主链基础接线，并形成当前最高到 E5 准入的证据” |
| P0-WC-002 | `README.md:29` | `真实 Telegram 双样本验证通过` | 描述过旧，且易被误读为更高稳定性 | E4 | 已改为“形成样本级验证证据” |
| P0-WC-003 | `README.md:87` | `EgoCore 服务在真实 Telegram 环境正常运行` | “正常运行”超出样本级证据强度 | E4 | 已降级为“形成样本级触发证据” |
| P0-WC-004 | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md:31` | `6/6 完整证据包` | 与当前 E4 最小证据包标准不一致，属于历史快照口径 | E4 历史快照 | 已补“历史快照”声明，明确以新报告为准 |
| P0-WC-005 | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md:149` | `所有样本已纳入回归` | 结论范围过大，超出文内已列样本范围 | E4 | 已改为“当前报告列出的失败样本已纳入回归” |

## 当前未判定为冲突但需注意

| note_id | location | wording | reason |
|---|---|---|---|
| P0-N-001 | `README.md:12` | `可进入 E5 观察期` | 与当前准入报告一致，但不等于“观察期已开始” |
| P0-N-002 | `docs/TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md:6` | `E5 准入通过，待执行观察期` | 与准入报告一致，当前未越级 |
| P0-N-003 | `artifacts/telegram_real_mainline_v1/reports/E4_TO_E5_ADMISSION_REPORT.md:19` | `准入通过` | 当前证据允许，但不能被外推为稳定运行 |
