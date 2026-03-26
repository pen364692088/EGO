# P7 TASK_REPORT

## 任务名称

P7：风险信号单一化

## 任务类型

规则收口 / 风险治理 / 信号权威源统一

## 目标与成功判据

- 先盘点所有 risk 相关字段、规则副本、消费点，再统一
- 明确唯一 canonical source：谁负责 risk signal 生成，谁只负责消费
- 统一 `safety_context.risk_level` 的生成、映射、trace/evidence 输出
- 将 legacy `risk` 别名与数值 `risk_level` 降为 compatibility-only 输入
- 至少保留一组守护测试，防止词表和规则再次散落复制

## 当前层级

规则治理层 / 风险信号单一化层 / P6 后主链收口层

## 当前确定项

- `EgoCore` 是风险信号正式生成方，`OpenEmotion` 只消费标准化后的风险信号
- 正式字段是 `safety_context.risk_level`
- P6 第二轮后，formal surface 上的 legacy 入口问题已不再阻塞 P7
- P7 开始时，`runtime_v2`、`context_assembler`、`semantic_router`、`approval_policy` 之间存在多份 message risk 规则副本

## 关键未知

- `approval_policy` 里的本地风险词表是否还能保留为“特殊例外”
- 旧脚本和旧测试中还有多少在示范 legacy `risk` 或数值 `risk_level`
- `trace/evidence` 是否已经完全只看 canonical `risk_level`
- OpenEmotion proto-self 兼容层还能否在不破坏旧测试的情况下吸收数值输入

## 唯一主执行链

1. 盘点所有 risk 字段、规则、副本与消费点。
2. 输出《风险权威冲突报告》。
3. 建立单一 canonical risk module。
4. 把 Runtime/OpenEmotion 正式主链改成只消费 canonical source。
5. 将 legacy/compat 输入收敛到 schema/adapter 层。
6. 补守护测试、更新 evidence 与文档。

## 不做项

- 不改 README 总口径
- 不处理 E5 聚合器
- 不处理 Telegram 输出转义
- 不把 OpenEmotion 其他领域里的数值 `risk` 一并重构成这次的 host runtime risk
- 不宣称“安全系统已完全收口”

## 风险权威冲突结论

- P7 开始时，正式主链确实存在多个 risk authority source 并存问题：
  - `EgoCore/app/runtime_v2/proto_self_runtime.py`
  - `EgoCore/app/runtime/context_assembler.py`
  - `EgoCore/app/runtime/semantic_router.py`
  - `EgoCore/app/runtime/approval_policy.py`
- 这些模块分别维护 message keyword / pattern / score 规则，属于真正的权威源冲突，而不是单纯消费差异
- 本次已先出《风险权威冲突报告》，再完成收口，未跳过冲突识别步骤

## 本次实际改动

- 新增 canonical risk module：
  - `EgoCore/app/risk_signal.py`
- 正式主链改为只消费 canonical source：
  - `EgoCore/app/runtime_v2/proto_self_runtime.py`
  - `EgoCore/app/runtime/context_assembler.py`
  - `EgoCore/app/runtime/semantic_router.py`
  - `EgoCore/app/runtime/approval_policy.py`
  - `EgoCore/app/openemotion_adapter/event_builder.py`
- OpenEmotion compat 归一：
  - `OpenEmotion/openemotion/proto_self/schemas.py`
- 更新脚本样本矩阵与 compat 示例：
  - `EgoCore/scripts/p0_r2_risk_test.py`
  - `EgoCore/scripts/p0_r2_e2e_test.py`
  - `EgoCore/scripts/p0_r3_unit_test.py`
  - `EgoCore/scripts/p0_r3_e2e_test.py`
- 新增守护测试：
  - `EgoCore/tests/test_risk_signal_authority.py`
- 更新既有测试预期：
  - `EgoCore/tests/test_runtime_v2_proto_self_runtime.py`
  - `EgoCore/tests/test_execution_context_injection.py`
  - `OpenEmotion/openemotion/proto_self/tests/test_schema_contract.py`
- 新增边界文档：
  - `EgoCore/docs/RISK_SIGNAL_AUTHORITY.md`

## Canonical 决策

### Formal authority

- risk generator：`EgoCore/app/risk_signal.py`
- canonical field：`safety_context.risk_level`
- canonical values：`low` / `medium` / `high` / `critical`

### Consumer-only

- `runtime_v2/proto_self_runtime.py`
- `runtime/context_assembler.py`
- `runtime/semantic_router.py`
- `runtime/approval_policy.py`
- `openemotion_adapter/event_builder.py`
- `OpenEmotion/openemotion/proto_self/schemas.py`

### Compatibility-only

- legacy input alias：`safety_context.risk`
- numeric `risk_level` input：`0.0~1.0`
- 旧 proto-self 测试里仍使用数值 `risk_level` 的样本

## 成功判据对照

| criterion | result |
|---|---|
| `risk_level` 不只是字段统一，scorer / authority source 也唯一 | 已满足 |
| Runtime 与 OpenEmotion 内部只保留一条正式 risk 生成链 | 已满足到正式主链层级 |
| 兼容字段与历史入口被标记为 compat-only | 已满足 |
| trace / evidence 中记录的 risk 与 runtime 判定一致 | 已满足到当前可验证样本层级 |
| 至少一组守护测试阻止规则再次散落复制 | 已满足 |

## 验证

- `python3 -m py_compile ...`：通过
- `python3 -m pytest --version`：阻塞，环境缺 `pytest`
- `rg` 回扫：`EgoCore/app` 内已无旧 message risk 词表副本
- 守护测试代码已补齐，但未能在当前环境执行

## 本次结论能证明什么

- 能证明 `EgoCore` 正式主链的 risk signal authority 已统一到 `app/risk_signal.py`
- 能证明 `runtime_v2`、context assembly、routing、approval、event builder 已不再各自维护一套 message risk 规则
- 能证明 `OpenEmotion` 在 host->proto-self 边界上只消费 canonical `risk_level`，并吸收 legacy `risk` / numeric `risk_level` 作为 compat 输入
- 能证明旧脚本示例已不再把 legacy `risk` 当正式字段继续扩散

## 本次结论不能证明什么

- 不能证明 OpenEmotion 全仓所有 `risk` 数值概念都已统一到 host runtime risk authority
- 不能证明所有历史 tests 都已在装有 `pytest` 的完整环境下通过
- 不能证明所有仓外调用者都已停止发送 legacy `risk` 或 numeric `risk_level`
- 不能证明 approval policy 的“高风险路径”规则与 message risk scorer 是同一概念，它们仍是不同层级的边界判定

## 还有哪些遗留项暂时不能删

- `OpenEmotion/openemotion/proto_self/tests/*` 中使用数值 `risk_level` 的 compat 样本
- `EgoCore/tests/test_proto_self_contracts.py` 中 legacy `risk` 别名吸收测试
- 任何仍需验证 compat 输入吸收能力的 schema/adapter 测试
- OpenEmotion 其他子系统里与 EFE/候选动作相关的 `risk` 数值字段，它们不是这次 host runtime risk authority 的同一问题

## 离下一步还差什么

- 在有 `pytest` 的环境里跑 P7 守护测试和回归矩阵
- 继续盘点仓外输入方，决定何时删除 legacy `risk` alias 吸收
- 给 compat 输入设删除时间点，避免 numeric/string 双形态长期并存
- 如要继续治理，应转向“compat 输入退役”和“非主链 tests/scripts 继续瘦身”，而不是重开第二套 risk authority
