# P3 TASK_REPORT

## 任务名称
P3：Proto-Self 契约单一化

## 任务类型
契约治理 / schema 收口 / 边界清理

## 目标与成功判据
- 把 EgoCore → OpenEmotion 输入事件与 OpenEmotion → EgoCore 输出结果收口成唯一结构化契约
- 宿主侧不再多处手拼兼容字段
- 兼容层只保留在单点
- contract tests 能卡住未来字段漂移

## 当前层级
边界契约层 / 跨仓接口收口层

## 当前确定项
- P2 已经把状态边界收口，P3 不需要再改状态主权。
- 现有主链里确实存在 `risk` 与 `risk_level` 并存。
- 当前 runtime/event builder/adapter 之间此前并没有唯一 canonical 输入归一化入口。

## 关键未知
- 旧兼容字段在其他非主链模块里还可能残留，但本轮只对 Proto-Self 主链与正式 schema 收口。
- 旧 replay/evidence 周边是否还有历史对象依赖 partial output shape，仍需后续观察。

## 唯一主执行链
1. 列出现有 event/result 字段全集
2. 标记别名 / 漂移 / 冗余字段
3. 指定唯一 canonical schema
4. 把兼容映射收回 schema/adapter 单点
5. 建 contract tests

## 本次改动
- 在 [`schemas.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/schemas.py) 新增：
  - `normalize_safety_context()`
  - `kernel_event_from_payload()`
  - `serialize_kernel_output()`
- `KernelEvent.__post_init__()` 现在会自动把 legacy `risk` 吸收为 canonical `risk_level`。
- [`proto_self_adapter.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py) 改为调用 `kernel_event_from_payload()` 做输入兼容归一化，并直接用 `serialize_kernel_output()` 返回 canonical output。
- [`proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py) 不再手拼 `risk` 别名，只写 canonical `risk_level`。
- [`event_builder.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/event_builder.py) 也去掉了双字段并存。
- OpenEmotion 内部消费侧 [`appraisal.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/appraisal.py) 和 [`cycles.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/cycles.py) 改为只读 canonical `risk_level`。

## Canonical 结论
- 输入 canonical
  - `safety_context.risk_level`
- 输入兼容别名
  - `safety_context.risk`
  - 只允许在 `normalize_safety_context()` / `kernel_event_from_payload()` 被吸收
- 输出 canonical
  - 直接使用 `KernelOutput.to_dict()` / `serialize_kernel_output()`
- 输出兼容策略
  - 不再在 adapter 手写 partial 子集；以 canonical output 全量字典为唯一正式结果形状

## 验证结果
- `python3 -m py_compile ...`：通过
- `cmd.exe /c "py -3 -m pytest tests\\test_runtime_v2_proto_self_runtime.py tests\\test_proto_self_contracts.py -q"`：`7 passed`
- `cmd.exe /c "py -3 -m pytest OpenEmotion\\openemotion\\proto_self\\tests\\test_schema_contract.py OpenEmotion\\openemotion\\proto_self\\tests\\test_kernel_replay.py OpenEmotion\\openemotion\\proto_self\\tests\\test_kernel_boundaries.py -q"`：`14 passed`

## 兼容与废弃计划
- 现阶段仍接受 legacy `safety_context.risk` 输入，但只能在 schema 层被吸收。
- 从本轮开始，runtime/event builder 不再主动发 `risk`。
- 下一阶段若仓内观察稳定，可删除 `normalize_safety_context()` 对 `risk` 的吸收分支。

## 本次结论能证明什么
- 能证明 Proto-Self 输入风险字段已经有唯一 canonical 名称：`risk_level`
- 能证明兼容映射已收回 schema/adapter 单点，而不是继续散在 runtime 与 builder
- 能证明 adapter 输出现在直接遵循 canonical `KernelOutput` 形状，而不是手写 partial dict
- 能证明新增 contract tests 已能卡住最明显的字段漂移

## 本次结论不能证明什么
- 不能证明所有历史非主链模块都已迁移到同一契约
- 不能证明 trace / evidence / replay 账本已经统一
- 不能证明未来不会再新增新的兼容字段
- 不能证明经过长期观察期后的边界稳定性

## 仍是过渡方案的点
- `normalize_safety_context()` 对 legacy `risk` 的吸收仍保留
- 旧非主链模块若还有历史 OpenEmotion result 对象，本轮未全量清坟

## 离 P4 还差什么
- 需要把 trace / evidence / replay 的字段口径与 Proto-Self canonical contract 对齐
- 需要明确哪些 replay artifact 应直接引用 canonical output，哪些仍是宿主派生视图
