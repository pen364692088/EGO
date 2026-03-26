# P0 FAILURE_SAMPLES

## 口径越级 / 状态混淆样本

| failure_id | type | location | observed_issue | risk_if_ignored | disposition |
|---|---|---|---|---|---|
| P0-F-001 | wording_overclaim | `README.md:7` | 使用 `稳态收口`，高于当前证据安全上限 | 会把准入通过误读为稳定运行或观察完成 | 已修正 |
| P0-F-002 | wording_overclaim | `README.md:87` | 使用 `正常运行`，缺少观察期证据支撑 | 会把样本级触发误读为稳定态 | 已修正 |
| P0-F-003 | stale_snapshot | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md:31` | 仍写 `6/6 完整证据包`，与当前最小证据包标准脱节 | 会导致旧报告被误读为当前权威状态 | 已加历史快照声明 |
| P0-F-004 | scope_overclaim | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md:149` | `所有样本已纳入回归` 范围过大 | 会夸大 failure regression 覆盖面 | 已收窄为文内范围 |

## 已存在的真实失败样本

| failure_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
| fail_20260325_162332 | E3 | integration | `artifacts/telegram_real_mainline_v1/failure_cases/failure_fail_20260325_162332.json` | 集成层存在过接口契约失败，且已复测 | 不证明真实渠道失败边界 |
| fail_20260325_162341 | E3 | integration | `artifacts/telegram_real_mainline_v1/failure_cases/failure_fail_20260325_162341.json` | 集成层存在过 runtime 配置失败，且已复测 | 不证明真实渠道稳定 |
| fail_20260325_171610 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/failure_cases/failure_fail_20260325_171610.json` | 真实 Telegram 链路存在过 delivery_error，并已纳入回归 | 不证明高风险失败场景已覆盖 |

## 本次结论不能证明什么
- 不能证明所有历史报告都已经完全无歧义
- 不能证明仓库里不存在其他未被本次 P0 扫描到的夸口表述
- 不能证明 failure 账本已经达到 E5 所需覆盖度
