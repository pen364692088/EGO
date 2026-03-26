# P0 STATE_MATRIX

| 功能项 | 当前层级 | 最高证据 | 主链接入状态 | 启用状态 | 当前可用口径 | 本次不能证明什么 | 权威源 |
|---|---|---|---|---|---|---|---|
| `RuntimeV2Loop` 统一 runner | 主链一致性验证层 | E3（辅以 E4 参考） | E2/E3 已接统一主链；E4 有参考样本 | E2/E3 受控执行已跑通 | 集成验证通过；主链候选可用；三层共享同一主链入口 | 不证明真实 Telegram 稳定；不证明观察期 | `artifacts/telegram_real_mainline_v1/reports/UNIFIED_RUNNER_CONSISTENCY_REPORT.md` |
| Telegram 真实主链样本 | E4 样本级 | E4 | 已接入真实主链（样本级） | 已启用（样本级） | 已有真实触发证据；样本级生效 | 不证明稳定运行；不证明观察期完成 | `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_E4_SAMPLE_001.md` |
| E4→E5 准入 | 准入判定层 | E4 + E3 辅证 | 已接入真实主链（样本级） | 已启用（样本级） | E5 准入通过；可进入观察期 | 不证明已进入观察期执行；不证明稳定运行 | `artifacts/telegram_real_mainline_v1/reports/E4_TO_E5_ADMISSION_REPORT.md` |
| Proto-Self Kernel v1 | 主链基础接线层 | E4（Telegram 样本） | 已被 runtime 主链调用 | 样本级启用 | 基础接线已完成；在真实样本范围内有触发证据 | 不证明“稳态收口”；不证明长期可靠 | `README.md` + `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/sample.json` |
| 失败样本账本 | 失败闭环层 | E4 | 已存在真实失败样本 | 已纳入回归 | 已有失败归因与复测闭环 | 不证明高风险失败覆盖充分 | `artifacts/telegram_real_mainline_v1/failure_cases/index.json` |
