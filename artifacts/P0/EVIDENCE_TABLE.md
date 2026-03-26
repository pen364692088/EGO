# P0 EVIDENCE_TABLE

| evidence_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
| P0-E-001 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/sample.json` | 存在完整真实 Telegram 高风险命中样本 | 不证明观察期已完成 |
| P0-E-002 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_E4_SAMPLE_001.md` | 当前 Telegram 真实主链最高可安全表达到 E4 样本级 | 不证明稳定运行 |
| P0-E-003 | E3 | integration | `artifacts/telegram_real_mainline_v1/reports/UNIFIED_RUNNER_CONSISTENCY_REPORT.md` | `simulated / integration / real_telegram` 共用同一主链候选 | 不证明真实渠道稳定 |
| P0-E-004 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/reports/E4_TO_E5_ADMISSION_REPORT.md` | 当前已通过 E5 准入门槛，可进入观察期 | 不证明观察期已开始执行 |
| P0-E-005 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/failure_cases/index.json` | 已存在失败样本账本，且有真实失败闭环 | 不证明失败覆盖充分 |
| P0-E-006 | E1 | doc | `README.md` | 公开总览是当前最容易被误读的强口径入口 | 不证明 README 自身是真相源 |
| P0-E-007 | E1 | doc | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md` | 存在历史汇总快照，需与当前状态源区分 | 不证明当前最新状态 |
| P0-E-008 | E0 | protocol | `docs/EGO 验收证据分级协议 v1.md` | 提供口径分级规则与禁用口径基线 | 不证明任何具体能力已生效 |
