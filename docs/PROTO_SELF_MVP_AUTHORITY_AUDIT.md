# MVP11.4–16 与 Proto-Self 权威审计

> 本文是代码证据基线；基于本文作出的收口决策见 [PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)。

## Executive Summary
本次审计按当前 formal mainline 反推，结论是：`proto_self_v2` 不是历史分支，也不是候选实现，而是当前正式主实现表面；但它仍显著依赖 `proto_self` v1 substrate，并在 `MVP12` 上继续依赖 `emotiond.developmental_core`。`MVP12–15` 的能力并未全部收束到单一路径：`MVP13/14/15` 已有 formal owner，但 `identity/self-model/drives/reflection` 仍存在“formal owner + v1 substrate 并行”的双层语义面；`long_term_self_summary` 与 `openemotion.memory/*` 目前存在库实现，但不在当前 formal mainline 上。

**A. Proto-Self Kernel 当前定位**

- `proto_self_v2`：当前**主实现（formal surface）**
- `proto_self` v1：当前**活跃 substrate**，不是历史分支；`proto_self_v2/kernel.py` 仍直接调用 `process_event_v1`
- 结论：当前真实结构是 `proto_self_v2 formal surface + proto_self v1 substrate + owner-context overlays`

**B. MVP12–15 能力当前主要由哪组文件承担**

- `MVP12`：`OpenEmotion/openemotion/proto_self_v2/developmental.py` + `OpenEmotion/emotiond/developmental_core/*` + `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `MVP13`：`OpenEmotion/openemotion/self_model/*` + `EgoCore/app/runtime_v2/proto_self_runtime.py` + `OpenEmotion/openemotion/proto_self_v2/self_model_context.py` + `OpenEmotion/openemotion/proto_self/*`
- `MVP14`：`OpenEmotion/openemotion/endogenous_drives/*` + `EgoCore/app/runtime_v2/proto_self_runtime.py` + `OpenEmotion/openemotion/proto_self_v2/endogenous_drive_context.py` + `OpenEmotion/openemotion/proto_self/*`
- `MVP15`：`OpenEmotion/openemotion/reflective_self/*` + `EgoCore/app/runtime_v2/proto_self_runtime.py` + `OpenEmotion/openemotion/proto_self_v2/reflective_self_context.py` + `OpenEmotion/openemotion/proto_self/reflection.py`

**C. 是否存在重复实现或双权威源**

- 存在，主要在四处：
  - `identity invariants`：`openemotion.proto_self.state.IdentityInvariants` 仍是当前执行面；`openemotion.identity.identity_invariants` 存在但未接入主链
  - `self-model`：`openemotion.self_model` 已是 formal owner，但 `openemotion.proto_self.self_model` 仍在产出 base delta，并被 `proto_self_v2` 合并消费
  - `drives`：`openemotion.endogenous_drives` 已是 formal owner，但 `openemotion.proto_self` 的 `DriveField/appraisal` 仍活跃
  - `reflection`：`openemotion.reflective_self` 已是 formal owner，但 `openemotion.proto_self.reflection` 仍活跃并贡献 `reflection_note`
- `MVP12` 的 `emotiond.developmental_core` 不是纯历史残留；它是当前 active implementation library，但 formal owner 状态面已经迁到 `openemotion.developmental_self`

**D. 若要收口，最小删改方案**

- `保留`
  - `EgoCore/app/runtime_v2/proto_self_runtime.py`
  - `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
  - `OpenEmotion/openemotion/proto_self_v2/*`
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/openemotion/endogenous_drives/*`
  - `OpenEmotion/openemotion/reflective_self/*`
  - `OpenEmotion/openemotion/developmental_self/*`
- `降级为 compat/shim`
  - `OpenEmotion/emotiond/self_model_adapter.py`
  - `EgoCore/app/openemotion_adapter/proto_self_restore.py`
- `明确 reference-only`
  - `OpenEmotion/emotiond/self_model_mirror.py`
  - `OpenEmotion/openemotion/cycle_core/*`
  - `OpenEmotion/emotiond/memory_legacy.py`
  - `OpenEmotion/openemotion/identity/long_term_self_summary.py`
  - `OpenEmotion/openemotion/memory/*`
- `候选删除`
  - 在确认无 formal caller 后，移除 `emotiond/self_model_adapter.py`、`emotiond/self_model_mirror.py`、`proto_self_restore.py` 这类仅 shadow/restore 的兼容面
  - 真正需要先收口的不是再造新核，而是先选定 `identity/self-model/drives/reflection` 的单一语义权威面

## Real Mainline Call Chain
当前 formal mainline 的真实调用链是：

1. `EgoCore/app/openemotion_hooks/native_hooks.py:36-45`
   - `NativeOpenEmotionHooks` 初始化 `ProtoSelfAdapter + RuntimeV2ProtoSelfRuntime`
2. `EgoCore/app/openemotion_hooks/subject_gate.py:61-104`
   - `MandatorySubjectGate` 以 `process_ingress / process_finalized_result / capture_response_plan` 把已授权 turn 强制送进主体链
3. `EgoCore/app/runtime_v2/loop.py:99-109`
   - `RuntimeV2Loop` 在正式 runtime 内持有 `ProtoSelfAdapter` 与 `RuntimeV2ProtoSelfRuntime`
4. `EgoCore/app/runtime_v2/proto_self_runtime.py:3941-4065`
   - `process_ingress()` 构造 proto-self 事件
   - 调用 `self.adapter.handle_event(...)`
   - 对 `self_model / drives / reflective / developmental / social / embodied / integration / initiative / realization` 逐个做 host-side governed writeback
5. `EgoCore/app/openemotion_adapter/proto_self_adapter.py:66-115`
   - `normalize_to_proto_self_input()`
   - `load_latest_state()`
   - `process_update_packet()` 或 `process_event()`
   - `save_mirror()` + trace bridge
6. `OpenEmotion/openemotion/proto_self_v2/kernel.py:7-10, 143-149, 265-375`
   - `proto_self_v2` 读取 owner projection/context
   - 但 `_process_default_v2()` 仍调用 `process_event_v1(...)`
   - `policy_hint / response_tendency` 也是 `v1_output` 与各 context output merge 后返回
7. `OpenEmotion/openemotion/proto_self_v2/developmental.py:11-19`
   - `MVP12` 的 developmental sandbox 仍直接依赖 `emotiond.developmental_core`

结论：

- 当前 formal mainline 确实是 `proto_self_v2`
- 但它不是完全独立的新核
- 当前结构是：
  - `proto_self_v2`：formal surface / orchestration
  - `proto_self` v1：identity/self-model/drives/cycles/memory_update/policy_hint 的 base substrate
  - `openemotion/* formal owners`：投影输入与 governed writeback target
  - `emotiond.developmental_core`：MVP12 implementation library

## Capability Audit Table
| 能力项 | 路线阶段 | 当前真实实现文件路径 | 所属仓库 | 是否由 proto_self 承担 | 是否还有第二实现 | 当前调用入口 | 权威源 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| identity invariants | `MVP11.4→proto_self base` | `OpenEmotion/openemotion/proto_self/state.py` -> `OpenEmotion/openemotion/proto_self/kernel.py` -> `OpenEmotion/openemotion/proto_self/reducers.py` -> `OpenEmotion/openemotion/proto_self_v2/kernel.py` | OpenEmotion | 是 | 是，`OpenEmotion/openemotion/identity/identity_invariants.py` 存在但未接 formal mainline | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | 当前执行面是 `openemotion.proto_self.state.IdentityInvariants`；`openemotion.identity.identity_invariants` 尚未成为 formal mainline authority | 主实现 |
| self-model | `MVP11.4 proto_self base + MVP13 formal owner` | `OpenEmotion/openemotion/self_model/model.py` -> `EgoCore/app/runtime_v2/proto_self_runtime.py::_inject_self_model_context/_apply_self_model_writeback` -> `OpenEmotion/openemotion/proto_self_v2/self_model_context.py` -> `OpenEmotion/openemotion/proto_self_v2/kernel.py` -> `OpenEmotion/openemotion/proto_self/self_model.py` | OpenEmotion | 部分，经 proto_self 消费 | 是，formal owner 与 v1 substrate 并行活跃 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | `openemotion.self_model.*` 是 formal owner；`openemotion.proto_self.self_model` 仍是 active runtime substrate | 主实现 |
| long-term self summary | `MVP13 support line` | `OpenEmotion/openemotion/identity/long_term_self_summary.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `openemotion.identity.long_term_self_summary` | dead code |
| episodic trace / short-horizon memory | `MVP11.4` | `OpenEmotion/openemotion/proto_self/reducers.py` -> `OpenEmotion/openemotion/proto_self/state.py` -> `OpenEmotion/openemotion/proto_self_v2/state.py` | OpenEmotion | 是 | 否 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | `openemotion.proto_self.reducers.update_memory` | 主实现 |
| event memory | `MVP11.5 support line` | `OpenEmotion/openemotion/memory/event_memory.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `openemotion.memory.event_memory` | dead code |
| narrative memory | `MVP11.5 support line` | `OpenEmotion/openemotion/memory/narrative_memory.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `openemotion.memory.narrative_memory` | dead code |
| policy memory | `MVP11.5 support line` | `OpenEmotion/openemotion/memory/policy_memory.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `openemotion.memory.policy_memory` | dead code |
| appraisal / drive field | `MVP11.4 proto_self base + MVP14 formal owner` | `OpenEmotion/openemotion/endogenous_drives/state.py` -> `EgoCore/app/runtime_v2/proto_self_runtime.py::_inject_endogenous_drive_context/_apply_endogenous_drive_writeback` -> `OpenEmotion/openemotion/proto_self_v2/endogenous_drive_context.py` -> `OpenEmotion/openemotion/proto_self_v2/kernel.py` -> `OpenEmotion/openemotion/proto_self/kernel.py` / `reducers.py` | OpenEmotion | 部分，经 proto_self 消费 | 是，formal owner drives 与 v1 `DriveField/appraisal` 并行活跃 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | `openemotion.endogenous_drives.*` 是 formal owner；`openemotion.proto_self` 仍提供 base drive semantics | 主实现 |
| developmental sandbox / cycle prior | `MVP12 + MVP16 formal owner writeback` | `OpenEmotion/openemotion/proto_self_v2/developmental.py` -> `OpenEmotion/emotiond/developmental_core/*` -> `EgoCore/app/runtime_v2/proto_self_runtime.py::_apply_developmental_self_writeback` -> `OpenEmotion/openemotion/developmental_self/*` | OpenEmotion | 部分，经 proto_self 编排 | 否（当前是 split stack，不是双活 owner） | `RuntimeV2ProtoSelfRuntime.process_developmental_tick` 与主链 `process_ingress/process_finalized_result` | runtime implementation library=`emotiond.developmental_core`；formal owner state=`openemotion.developmental_self` | 主实现 |
| cycle consolidation / cycle prior | `MVP11.4 / MVP11.5` | `OpenEmotion/openemotion/proto_self/cycles.py` -> `OpenEmotion/openemotion/proto_self/kernel.py` -> `OpenEmotion/openemotion/proto_self_v2/state.py` / `kernel.py` | OpenEmotion | 是 | 否，`openemotion/cycle_core/*` 不在当前 formal mainline | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | `openemotion.proto_self.cycles` | 主实现 |
| reflection / structured revision | `MVP11.4 proto_self reflection + MVP15 formal owner` | `OpenEmotion/openemotion/reflective_self/state.py` -> `EgoCore/app/runtime_v2/proto_self_runtime.py::_inject_reflective_self_context/_apply_reflective_self_writeback` -> `OpenEmotion/openemotion/proto_self_v2/reflective_self_context.py` -> `OpenEmotion/openemotion/proto_self_v2/kernel.py` -> `OpenEmotion/openemotion/proto_self/reflection.py` | OpenEmotion | 部分，经 proto_self 消费 | 是，formal owner 与 v1 reflection note 并行活跃 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | `openemotion.reflective_self.*` 是 structured revision formal owner；`openemotion.proto_self.reflection` 仍是 base trigger layer | 主实现 |
| policy_hint / response_tendency | `MVP11.5 base + MVP14/15/16 overlays` | `OpenEmotion/openemotion/proto_self/reducers.py` -> `OpenEmotion/openemotion/proto_self/kernel.py` -> `OpenEmotion/openemotion/proto_self_v2/kernel.py` + `*_context.py` overlays | OpenEmotion | 是 | 是，但属于同一 kernel stack 内的 v1 base + v2 overlay merge，不是第二主链 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result` | 当前聚合权威是 `openemotion.proto_self_v2.kernel`；base producer 仍是 `openemotion.proto_self.reducers` | 主实现 |
| trace/replay writeback | `MVP11.5 + MVP13/14/15/16 replay/writeback` | `OpenEmotion/openemotion/proto_self_v2/kernel.py` trace payload -> `EgoCore/app/openemotion_adapter/proto_self_adapter.py` trace/mirror -> `EgoCore/app/runtime_v2/proto_self_runtime.py::_apply_*_writeback` -> `OpenEmotion/openemotion/*/store.py` / `replay.py` + `EgoCore/app/telegram_evidence_collector.py` | OpenEmotion + EgoCore | 部分，经 proto_self 产出 trace、由宿主落地与写回 | 否 | `RuntimeV2ProtoSelfRuntime.process_ingress/process_external_result/process_finalized_result/capture_response_plan` | trace authority=`proto_self_v2`; owner replay authority=`openemotion.*.store/replay`; evidence replay authority=`EgoCore telegram_evidence_collector` | 主实现 |
| proto_self adapter bridge | `MVP11.5→current formal mainline bridge` | `EgoCore/app/openemotion_adapter/proto_self_adapter.py` | EgoCore | 否，负责转发 | 否 | `RuntimeV2ProtoSelfRuntime.* -> ProtoSelfAdapter.handle_event` | `EgoCore/app/openemotion_adapter/proto_self_adapter.py` | 主实现 |
| proto_self restore | `MVP11.5 support line` | `EgoCore/app/openemotion_adapter/proto_self_restore.py` | EgoCore | 否 | 否 | `none on formal mainline` | `EgoCore/app/openemotion_adapter/proto_self_restore.py` | shim |
| self_model_adapter (legacy shadow adapter) | `MVP13 legacy compat` | `OpenEmotion/emotiond/self_model_adapter.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `OpenEmotion/emotiond/self_model_adapter.py` | shim |
| self_model_mirror | `MVP13 mirror` | `OpenEmotion/emotiond/self_model_mirror.py` | OpenEmotion | 否 | 否 | `none on formal mainline` | `OpenEmotion/emotiond/self_model_mirror.py` | mirror |

## Duplicate / Dual-Authority Findings
只列当前真正值得处理的重叠，不列纯历史噪声。

### 1. `identity invariants` 仍是双层定义
- 当前执行路径使用的是 `openemotion.proto_self.state.IdentityInvariants`
- `openemotion.identity.identity_invariants.IdentityInvariants` 只在 formal-owner 文档和工具侧出现，当前 formal mainline 无 consumer
- 这不是 mirror；是“正式 owner 已存在，但主链仍在跑旧 substrate”

### 2. `self-model` 已 formalize，但旧 substrate 还活着
- `openemotion.self_model` 已被 `RuntimeV2ProtoSelfRuntime` 注入 `runtime_summary.self_model_context`，并承担 governed writeback
- 但 `proto_self_v2/state.py` 仍直接使用 `openemotion.proto_self.state.SelfModel`
- `proto_self_v2/kernel.py` 仍通过 `process_event_v1` 获得 `self_model_delta`
- 结论：当前不是单一权威；是 `formal owner + active substrate` 双层结构

### 3. `drives` 同样是 formal owner 与 v1 drive field 并行
- `openemotion.endogenous_drives` 已 formalize，并有投影与 writeback
- 但 `proto_self` v1 的 `DriveField/appraisal` 仍直接影响 `appraisal_state_delta`
- `proto_self_v2/kernel.py` 最终把两者都写进输出：既保留 `v1_output.appraisal_state_delta`，又附加 `endogenous_drive_delta`
- 结论：当前是双层驱动语义，不是单一 owner

### 4. `reflection` 也是双层
- `openemotion.reflective_self` 已 formalize，并由 host 做 gated writeback
- 但 `openemotion.proto_self.reflection.maybe_reflect()` 仍会生成 base `reflection_note`
- `proto_self_v2` 把 v1 note 与 reflective context/output 一起带出
- 结论：结构化 revision 已 formalize，但 lightweight reflection trigger 仍在旧 substrate

### 5. `MVP12` 是 split stack，不是纯历史包袱
- `proto_self_v2/developmental.py` 当前 formal mainline 可达
- 它仍直接 import `emotiond.developmental_core`
- 同时 developmental formal owner state 又在 `openemotion.developmental_self`
- 这不是“完全重复建设”，但的确是“formal surface / implementation library / formal owner state” 三层分离

### 6. 这些不是当前 mainline duplicate
- `OpenEmotion/emotiond/self_model_adapter.py`
- `OpenEmotion/emotiond/self_model_mirror.py`
- `EgoCore/app/openemotion_adapter/proto_self_restore.py`
- `OpenEmotion/openemotion/cycle_core/*`
- `OpenEmotion/emotiond/memory_legacy.py`
- `OpenEmotion/openemotion/memory/*`

原因：
- formal mainline 无 caller，或只在 tools/tests/reference 路径出现
- 它们是 shim/mirror/reference/historical residue，不应误报成主链 duplicate

## Minimum Consolidation Plan
这里不提大重构，只提最小收口动作。

### 保留
- `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
- `OpenEmotion/openemotion/proto_self_v2/*`
- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/openemotion/endogenous_drives/*`
- `OpenEmotion/openemotion/reflective_self/*`
- `OpenEmotion/openemotion/developmental_self/*`

### 降级为 compat/shim
- `OpenEmotion/emotiond/self_model_adapter.py`
- `EgoCore/app/openemotion_adapter/proto_self_restore.py`

### 明确 reference-only
- `OpenEmotion/emotiond/self_model_mirror.py`
- `OpenEmotion/openemotion/cycle_core/*`
- `OpenEmotion/emotiond/memory_legacy.py`
- `OpenEmotion/openemotion/identity/long_term_self_summary.py`
- `OpenEmotion/openemotion/memory/*`

### 候选删除
- 在确认 tools/tests 无主链依赖后，逐步删除：
  - `OpenEmotion/emotiond/self_model_adapter.py`
  - `OpenEmotion/emotiond/self_model_mirror.py`
  - `EgoCore/app/openemotion_adapter/proto_self_restore.py`

### 真正需要先做的收口
1. **选定 identity 单一语义面**
   - 要么把 `openemotion.identity.identity_invariants` 真接入 `proto_self_v2`
   - 要么把它明确降级为未启用 formal owner，停止把它描述成 live authority
2. **对 self-model / drives / reflection 明确“formal owner vs substrate”**
   - 当前最小动作不是重写 Kernel
   - 而是先在 repo 口径里明确：
     - `formal owner` 是谁
     - `active substrate` 是谁
     - 二者是否允许并存，还是后续要消灭 substrate
3. **对 MVP12 明确身份**
   - 要么正式承认 `emotiond.developmental_core` 是当前 implementation library
   - 要么后续再迁入 `openemotion`；但在迁之前，不应把它当 dead code

当前最小正确结论：

- `proto_self_v2` 已经是 formal mainline
- 但 `MVP11.4 base kernel` 并没有真正退役
- 当前不是“全新小核已完全收口”，而是“formal surface 已切到 v2，但核心语义仍部分由 v1 substrate 与少量 `emotiond` implementation library 共同承担”
