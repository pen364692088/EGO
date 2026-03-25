# TASK_PROTO_SELF_KERNEL_V1.md

## 任务概述

实现 Proto-Self Kernel v1：最小可持续主体内核。

**权威源**：
- 设计稿：`docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
- 接口草案：`docs/PROTO_SELF_KERNEL_V1_SPEC.md`

## 分支策略

- **Base Branch**: `main`
- **Working Branch**: `feature/proto-self-kernel-v1`

## Frozen Scope（不可改范围）

以下范围在本任务中冻结，若必须改，必须单独列出兼容性影响 + 回归证据：

### 1. 已验证主链行为

| 能力 | 验证状态 | 文件路径 |
|------|----------|----------|
| `cycle_core_v1` | verified_telegram_e2e | `openemotion/cycle/` |
| `WS_C1` 三层记忆模型 | verified_e2e | `openemotion/memory/` |
| `long-term self summary` | verified_e2e | `openemotion/identity/long_term_self_summary.py` |

**冻结内容**：
- 已验证的写入/读取/过滤/覆盖行为
- Telegram E2E 命中率和跨轮状态连续性
- 偏好/目标/约束/纠正写入逻辑
- 闲聊不误写行为

### 2. 架构原则

| 原则 | 说明 |
|------|------|
| trace-driven replay | replay 优先读 trace，不允许用当前 store 反推旧轮结果 |
| hard gate | 语义未定义不实现，authority 未确认不猜 |
| deterministic | 两层确定性保证 |
| artifact discipline | 所有验收证据必须有 artifact |

### 3. 双核边界定义

| 边界 | 约束 |
|------|------|
| EgoCore 职责 | 渠道接入、运行时、工具执行、安全边界、治理、审计 |
| OpenEmotion 职责 | identity、self-model、memory、appraisal、reflection 本体解释权 |
| 禁止项 | EgoCore 禁止拥有 self-model/memory/appraisal/reflection 最终解释权 |

---

## Changed Scope（将要改变的范围）

### OpenEmotion 侧新增

```
openemotion/
  proto_self/
    __init__.py           # 模块入口
    schemas.py            # KernelEvent / KernelOutput / ReflectionNote / ResponseTendency
    state.py              # ProtoSelfState / IdentityInvariants / SelfModel / DriveField / CycleStore
    kernel.py             # process_event 主循环
    appraisal.py          # drive_field 更新
    self_model.py         # self_model 更新
    cycles.py             # cycle consolidation
    reflection.py         # reflection note 生成
    reducers.py           # apply_updates 状态写回
    trace_types.py        # trace payload 结构
    tests/
      test_kernel_identity.py
      test_kernel_drive_field.py
      test_kernel_cycles.py
      test_kernel_reflection.py
      test_kernel_boundaries.py
      test_kernel_replay.py
```

### EgoCore 侧新增

```
egocore/
  app/
    openemotion_adapter/
      proto_self_adapter.py      # 事件标准化 + kernel 调用 + 结果桥接
      proto_self_restore.py      # 状态恢复注入
      proto_self_trace_bridge.py # trace 写入桥接
```

---

## 实施阶段

### WS-PSK-0：合同落锁 ✅ (当前)

目标：明确 frozen scope / changed scope，创建任务文档。

### WS-PSK-1：Schema 与状态骨架

产出：
- `schemas.py`：KernelEvent / KernelOutput / ReflectionNote / ResponseTendency
- `state.py`：ProtoSelfState 及其组件
- `trace_types.py`：trace payload 结构
- `__init__.py`：模块入口

Gate：schema 未冻结，不准进入 kernel。

### WS-PSK-2：最小内核主循环

产出：
- `kernel.py`：process_event 主循环
- `appraisal.py`：drive_field 更新
- `self_model.py`：self_model 更新
- `cycles.py`：cycle consolidation
- `reducers.py`：状态写回

Gate：若 policy_hint / response_tendency / trace_payload 不能稳定产出，不准进入 adapter。

### WS-PSK-3：最小反思与边界保护

产出：
- `reflection.py`：反思触发与修正建议生成
- boundary assertion：输出中不得出现直接执行命令

Gate：任意一例越权，直接打回。

### WS-PSK-4：单元测试补齐

产出：
- 6 组核心测试全部通过

Gate：6 组核心测试未全绿，不准接 EgoCore。

### WS-PSK-5：EgoCore 薄接线

产出：
- `proto_self_adapter.py`
- `proto_self_restore.py`
- `proto_self_trace_bridge.py`

Gate：发现 adapter 偷做本体，直接回滚该阶段。

### WS-PSK-6：Replay + E2E + 回归

产出：
- replay regression 报告
- 3+ E2E 场景 artifact
- cycle_core_v1 / WS_C1 / long-term self summary 回归报告

Gate：无真实 artifact，不准报完成。

---

## 验收标准

只有同时满足以下条件，才允许报"Proto-Self Kernel v1 完成"：

1. `openemotion/proto_self/` 正式模块已落库，且不是空壳
2. EgoCore 侧只有薄 adapter，没有主体本体逻辑渗漏
3. 6 类必测验证全部通过
4. 至少 1 份 replay artifact + 1 份 E2E artifact + 1 份回归报告齐全
5. 输出中无任何直接工具执行命令或现实裁决越权
6. 失败场景下确实出现 reflection_note，并影响下一轮状态或 revision_counter
7. 重复相似事件确实强化同一 cycle_id
8. 不破坏现有 cycle_core_v1 / WS_C1 / long-term self summary 旧行为
9. 报告口径：已实现并通过独立验收 / 已实现但待真实主链接入验证（无真实 E2E 证据时）

---

## 不允许事项

1. **不允许** 在 EgoCore 新增主体本体语义
2. **不允许** OpenEmotion 直接执行现实动作
3. **不允许** 用 prompt 文本临时拼接口
4. **不允许** 为了实现 Proto-Self Kernel v1 重写已有已验证主链
5. **不允许** 用"通过单元测试"冒充闭环完成
6. **不允许** 把 Proto-Self Kernel v1 扩成 v2/vNext

---

## 交付物

1. 代码改动清单
2. 新增/修改文件清单
3. 单元测试清单与结果
4. replay artifact 路径
5. E2E artifact 路径
6. 旧行为回归报告
7. 边界自查说明
8. 设计对齐报告

---

## 失败回退

若任一 Gate 未过：

1. 保留 OpenEmotion 内核代码，但关闭 EgoCore adapter 接线
2. 回退到 shadow / mirror only 模式
3. 不动旧主链
4. 只修 Proto-Self Kernel v1 自身
