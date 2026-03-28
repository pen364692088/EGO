# PROTO_SELF_KERNEL_V2_IMPLEMENTATION_TASK

> 任务类型：L3 dual_repo implementation entry
> 状态：verify_passed
> 作用：固定 Proto-Self V2 下一轮双仓实现的 authority source、contract 边界、最小 E4 证据与回退规则

---

## 真实目标

把 `Proto-Self V2` 从纯规格层推进到 **可在双仓中跑通的 bounded vertical slice**：

- `UpdatePacketV2 / KernelOutputV2 / TracePayloadV2` 有正式 contract
- OpenEmotion 有可调用的 `proto_self_v2` kernel 路径
- EgoCore adapter / runtime 能显式消费 `proto_self.v2`
- replay / evidence 能接住 `proto_self.trace.v2`

本轮目标不是取代当前 V1 默认主线，而是提供 **可验证、可回退、显式启用** 的 V2 实现入口。

---

## 成功判据

- [ ] `proto_self.v2` 输入 contract 明确且有 repo-tracked 文件承载
- [ ] OpenEmotion 存在 `proto_self_v2` 可执行 kernel 路径
- [ ] EgoCore adapter 能按 `schema_version=proto_self.v2` 正确分流
- [ ] runtime 可通过显式入口构造并发送 `UpdatePacketV2`
- [ ] output / trace / replay evidence 至少有一条 V2 子链路验证
- [ ] 保持当前 V1 默认主线不被隐式替换

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
- 主链 runtime 显式启用与回退

### 明确禁止

- 在 EgoCore adapter 中发明主体语义
- 让 OpenEmotion 直接现实执行
- 无显式入口就替换当前 V1 默认主线
- 用 prompt 或自由文本绕过结构字段

---

## 最小 E4 证据

本轮最低 E4 不要求真实 Telegram，而要求 **真实双仓主链可触发**：

1. 同一条 EgoCore runtime 入口显式选择 `proto_self.v2`
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

- 默认主线保持 `proto_self.v1`
- `proto_self.v2` 必须显式启用
- 任一 contract / adapter / evidence gate 未过：
  - 停止提升口径
  - 保留代码
  - 回退到 V1 默认入口

---

## 下一步最小闭环动作

1. 补发布收口并同步远端
2. 保持 `proto_self.v1` 为默认主线
3. 下一轮如需提升口径，补显式 E4 runtime evidence

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

- 已证明：`proto_self.v2` bounded vertical slice 已实现并可在双仓内显式进入
- 未证明：真实 runtime 主链 E4 证据、Telegram 主链、长期 replay/stability
