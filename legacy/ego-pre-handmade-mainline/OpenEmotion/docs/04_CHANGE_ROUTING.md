# 04_CHANGE_ROUTING.md

> 目标：把"想改什么功能 → 应优先查看哪些仓库 / 模块 / 目录 / 文件"写清楚。

## 使用规则

- 先判定能力归属：EgoCore 还是 OpenEmotion
- 再判定是否涉及双核接口
- 如果涉及接口字段或语义边界，必须同时看 contract / adapter / schema

## 路由矩阵

### 1. 改 identity invariants / self-model / long-term self summary / proto-self kernel
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/` — **Proto-Self Kernel v1（主体内核主链）**
- `openemotion/identity/`
- `openemotion/self_model/`
- `schemas/self_model.schema.json`
- `docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
- `docs/PROTO_SELF_KERNEL_V1_SPEC.md`

联动时再看 EgoCore：
- `app/openemotion_adapter/proto_self_adapter.py`
- `app/runtime_v2/loop.py`

### 2. 改 memory / salience / consolidation / narrative / policy memory
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/memory/`
- `docs/MEMORY_MODEL_V1.md`
- `docs/MEMORY_RETRIEVAL_CONTRACT_V1.md`

常见误改点：
- 把 memory 本体逻辑挪回 EgoCore
- 把 cache/mirror 当成本体

### 3. 改 appraisal / drive_field / internal state
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/appraisal.py` — **drive_field 更新**
- `openemotion/proto_self/state.py` — **ProtoSelfState**
- `openemotion/cycle_core/`

### 4. 改 reflection / cycle consolidation / structured revision
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/reflection.py` — **反思触发**
- `openemotion/proto_self/cycles.py` — **cycle 固化**
- `openemotion/proto_self/reducers.py` — **状态写回**

### 5. 改 EgoCore ↔ OpenEmotion 联动字段
**必须双仓联动看**

优先目录/文件：
- OpenEmotion `openemotion/proto_self/schemas.py`
- OpenEmotion `openemotion/proto_self/trace_types.py`
- EgoCore `app/openemotion_adapter/proto_self_adapter.py`
- EgoCore `app/runtime_v2/loop.py`

### 6. 改 trace / replay / audit
**先看仓库：EgoCore**

优先目录/文件：
- `app/openemotion_adapter/proto_self_trace_bridge.py`
- `logs/proto_self_trace.jsonl`

## 典型改动场景

### 场景 A：Proto-Self Kernel 输出字段不对
- 先看 `openemotion/proto_self/schemas.py`
- 再看 `openemotion/proto_self/kernel.py`
- 检查 `boundary.py` 是否拦截

### 场景 B：drive_field 计算不符合预期
- 先看 `openemotion/proto_self/appraisal.py`
- 再看 `openemotion/proto_self/state.py` 中的 DriveField 定义

### 场景 C：reflection 没有触发
- 先看 `openemotion/proto_self/reflection.py` 的触发条件
- 检查 external_result 是否正确传递

### 场景 D：cycle 没有正确固化
- 先看 `openemotion/proto_self/cycles.py`
- 检查 cycle_id 计算逻辑

## 常见误区

- 把主体语义写在 EgoCore adapter
- 把 cache/mirror 当成本体
- 跳过 schema 直接改字段
- 不看设计稿就改核心逻辑
