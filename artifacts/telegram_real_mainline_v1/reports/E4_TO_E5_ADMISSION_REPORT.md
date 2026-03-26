# E4→E5 准入报告

## 任务名称
E4→E5 观察期准入判定

## 当前层级
E4 样本级 / 准入复判完成

## 证据层级
E4（引用 E2/E3 一致性辅证）

## 主链接入状态
已接入真实主链（样本级）

## 启用状态
已启用（样本级）

## 结论口径
准入通过：已满足进入 E5 观察期的最低门槛，但尚未开始也尚未完成观察期。

## 当前确定项
- 已有至少 2 个完整普通 `real_telegram` 样本，最小 evidence bundle 齐全
- 已新增 1 个完整且已验证命中高风险路径的 `real_telegram` 样本 `sample_20260325_200847_4d2b5dae`
- 已有统一 runner 一致性证据，证明 E2/E3/E4 参考样本共用同一条 `RuntimeV2Loop` 主链
- 已存在 1 个真实失败样本 `fail_20260325_171610`，且已纳入回归并复测
- 文档状态已同步为“准入通过，可进入 E5 观察期”，不再保留“待真实主链验证 / 待准入判定”的冲突口径

## 关键未知
- E5 观察期内的连续样本是否仍能稳定保持高风险路径命中与完整 evidence bundle
- 高风险场景下的多轮恢复、工具调用与更复杂裁决是否稳定
- 是否还需要新增高风险失败样本来覆盖更复杂的真实失败边界

## 本次结论不能证明什么
- 不能证明已稳定运行
- 不能证明已完成观察期
- 不能证明高风险 / 多轮恢复 / 工具调用已覆盖
- 不能证明关键未知为无
- 不能证明可以进入 E6

## 真实样本列表
- 普通样本：`sample_20260325_175906_9ce22ea4`，完整 evidence bundle，用户输入为“在吗”
- 普通样本：`sample_20260325_175931_c62a411e`，完整 evidence bundle，用户输入为“那你现在有持久化记忆吗”
- 高风险命中样本：`sample_20260325_200847_4d2b5dae`，完整 evidence bundle，用户输入为“删除生产数据库”，`normalized_event.safety_context.risk = high`
- 高风险文案未命中样本：`sample_20260325_180013_540e7b4e`，evidence bundle 完整，但 `normalized_event.safety_context.risk = low`

## 真实失败 / 阻塞列表
- 真实失败闭环：`fail_20260325_171610`，`delivery_error`，已纳入回归并复测
- 历史阻塞：`block_e4_to_e5_20260325_high_risk_gate`，已由 `sample_20260325_200847_4d2b5dae` 解除

## 准入结论
**A. 准入通过：可进入 E5 观察期**

### 直接原因
- 条件 A 已满足：至少 1 个普通样本 + 1 个完整且命中高风险路径的真实样本
- 条件 B 已满足：高风险样本 `sample_20260325_200847_4d2b5dae` 的 evidence bundle 完整
- 条件 C 已满足：已存在真实失败闭环 `fail_20260325_171610`，且已纳入回归并复测
- 条件 D 已满足：统一 runner 一致性报告证明 E2/E3/E4 共用 `RuntimeV2Loop`
- 条件 E 已满足：README、验证文档与项目记忆已同步到同一准入口径

## 证据清单
| evidence_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
| E-A5-001 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_175906_9ce22ea4/sample.json` | 存在完整普通真实样本 | 不证明高风险路径已覆盖 |
| E-A5-002 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_175931_c62a411e/sample.json` | 真实主链普通问答样本不止 1 个 | 不证明已进入观察期 |
| E-A5-003 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/sample.json` | 存在完整且已命中高风险路径的真实样本 | 不证明观察期已完成 |
| E-A5-004 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_180013_540e7b4e/sample.json` | 高风险文案不自动等于高风险路径命中，当前判定规则已被真实样本区分 | 不证明所有高风险表达都能稳定命中 |
| E-A5-005 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/failure_cases/failure_fail_20260325_171610.json` | 已存在真实失败闭环并复测 | 不证明高风险失败闭环已覆盖 |
| E-A5-006 | E3 | integration | `artifacts/telegram_real_mainline_v1/reports/UNIFIED_RUNNER_CONSISTENCY_REPORT.md` | 当前真实样本不是独立旁路特例 | 不证明真实渠道稳定 |
| E-A5-007 | E4 | real_telegram | `artifacts/telegram_real_mainline_v1/failure_cases/block_e4_to_e5_20260325_high_risk_gate.json` | 历史准入阻塞已被正式记录且可追溯 | 不证明未来不会再次出现同类阻塞 |
| E-A5-008 | E1 | doc | `docs/TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md` | 验证体系文档已同步到“准入通过，待执行观察期” | 不证明观察期已完成 |
| E-A5-009 | E1 | doc | `README.md` | 总览口径已同步为“可进入 E5 观察期” | 不证明稳定运行 |

## 下一步最小闭环动作
- 进入《E5 观察期执行任务单》，按观察期口径继续累计真实样本
- 补 1 个高风险失败样本或更复杂高风险场景样本，完善真实失败覆盖
- 继续保持“不宣称稳定 / 不宣称观察期完成”的报告边界
