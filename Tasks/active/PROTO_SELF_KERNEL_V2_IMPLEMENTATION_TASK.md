# PROTO_SELF_KERNEL_V2_IMPLEMENTATION_TASK

> 任务类型：L3 dual_repo implementation entry
> 状态：published
> 作用：固定 Proto-Self V2 作为主体层 state writeback 主入口时的 authority source、contract 边界、最小 E4/E5 证据与兼容回退规则

---

## 真实目标

把 `Proto-Self V2` 从纯规格层推进到 **主体层 state writeback 的唯一主入口**，并保留受控兼容回退：

- `UpdatePacketV2 / KernelOutputV2 / TracePayloadV2` 有正式 contract
- OpenEmotion 有可调用的 `proto_self_v2` kernel 路径
- EgoCore adapter / runtime 默认消费 `proto_self.v2`
- replay / evidence 能接住 `proto_self.trace.v2`

本轮目标是把 `proto_self.v2` 提升为主体层默认主线；若保留 `v1`，只能作为显式兼容 fallback，不再作为默认 owner。

---

## 成功判据

- [ ] `proto_self.v2` 输入 contract 明确且有 repo-tracked 文件承载
- [ ] OpenEmotion 存在 `proto_self_v2` 可执行 kernel 路径
- [ ] EgoCore adapter 能按默认 `schema_version=proto_self.v2` 正确分流
- [ ] runtime 默认构造并发送 `UpdatePacketV2`
- [ ] output / trace / replay evidence 至少有一条 V2 子链路验证
- [ ] 若存在 `v1`，它只能通过显式兼容 fallback 进入

---

## Authority Source

按优先级固定为：

1. [PROTO_SELF_KERNEL_V2_SPEC.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/docs/PROTO_SELF_KERNEL_V2_SPEC.md)
2. [PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md)
3. [Boundary Constitution]( /mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md)
4. [AGENT_DEVELOPMENT_PLAYBOOK.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/AGENT_DEVELOPMENT_PLAYBOOK.md)
5. 当前 V1 主线代码与验证：
   - `OpenEmotion/openemotion/proto_self/*`
   - `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
   - `EgoCore/app/runtime_v2/proto_self_runtime.py`

冲突裁决：

- V2 规格 > V1 历史设计/接口草案
- 当前 runtime 行为 > README 乐观描述
- OpenEmotion 主体语义 > EgoCore adapter 推断

---

## Contract 边界

### OpenEmotion 负责

- `UpdatePacketV2` 的主体语义解释
- `ProtoSelfStateV2` / `KernelOutputV2` / `TracePayloadV2`
- `Fθ(S_t, U_t, R_t, G_t)` 的 bounded implementation
- trace-first replay 所需的最小输出字段

### EgoCore 负责

- 结构化 ingress / external outcome 组包
- `schema_version` 路由
- adapter normalize / invoke / serialize / evidence capture
- 主链 runtime 默认启用与兼容回退

### 明确禁止

- 在 EgoCore adapter 中发明主体语义
- 让 OpenEmotion 直接现实执行
- 在 EgoCore adapter 中维持 `v1` 默认 owner
- 用 prompt 或自由文本绕过结构字段

---

## 最小 E4 证据

本轮最低 E4 不要求真实 Telegram，而要求 **真实双仓主链可触发**：

1. 同一条 EgoCore runtime 入口默认选择 `proto_self.v2`
2. adapter 以 `schema_version=proto_self.v2` 分流到 OpenEmotion V2 kernel
3. OpenEmotion 返回 `proto_self.output.v2`
4. evidence ledger / trace bridge 捕获到 `proto_self.trace.v2`
5. trace 内至少包含：
   - `update_packet_hash`
   - `state_revision_before`
   - `state_revision_after`
   - `retrieval_summary`
   - `constraint_summary`
   - `policy_hint`
   - `response_tendency`

若只有单元测试通过、但没有 runtime 主链触发证据，只能算 `V2/V3`，不能报本轮主线闭环。

---

## 回退规则

- 默认主线保持 `proto_self.v2`
- `proto_self.v1` 如存在，只能通过显式兼容 fallback 启用
- 任一 contract / adapter / evidence gate 未过：
  - 停止提升口径
  - 保留代码
  - 回退到显式 `v1` 兼容入口

---

## 下一步最小闭环动作

1. 把 `proto_self.v2` 保持为主体层默认写回主线
2. 下一轮继续补跨 session / 跨日真实通道稳定性证据

---

## 当前已完成

- [x] L3 dual_repo 任务单已创建
- [x] `proto_self.v2` contract 已落：
  - `EgoCore/contracts/proto_self_v2.schema.json`
- [x] OpenEmotion bounded kernel 已落：
  - `openemotion/proto_self_v2/`
- [x] EgoCore adapter/runtime 显式版本分流已落：
  - `app/openemotion_adapter/proto_self_adapter.py`
  - `app/runtime_v2/proto_self_runtime.py`
- [x] 最小测试已通过：
  - `OpenEmotion/openemotion/proto_self_v2/tests/test_kernel_contract.py`
  - `EgoCore/tests/test_proto_self_v2_contracts.py`
  - `EgoCore/tests/test_runtime_v2_proto_self_runtime.py`

## 当前完成口径

- 已证明：`proto_self.v2` 已实现 bounded vertical slice，并已拿到 runtime / Telegram 真实主链 E4 与同 session E5 证据
- 未证明：跨 session / 跨日稳定性，以及更高层长期 continuity

## 发布状态

- [x] 代码与文档已提交
- [x] 已推送到 `origin/main`
