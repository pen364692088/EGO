# PROGRAM_STATE_UNIFIED_SPEC.md

> 双仓统一进度账规范  
> 版本: v1.0.0  
> 最后更新: 2026-03-16

---

## 1. 什么是统一进度账

统一进度账是双仓系统的**唯一总口径**，用于回答：

1. 当前系统整体处于什么状态
2. 下一步到底允许做什么
3. 哪个阶段是"代码存在"，哪个是"已验证"
4. 哪个结论来自 EgoCore，哪个来自 OpenEmotion

---

## 2. 四轴模型

### 2.1 Host Axis（宿主轴）

- 命名空间: `EG_PHASE`
- 回答: EgoCore 宿主、runtime、tools、governance 是否成熟
- 状态值: `planned` → `code_exists` → `integrated` → `shadow_running` → `enforced` → `verified_full`

### 2.2 Subject Axis（主体能力轴）

- 命名空间: `SELF_WS`
- 回答: Minimum Viable Self 当前推进到哪里
- 状态值: `planned` → `code_exists` → `integrated` → `verified_contract` → `verified_full`

### 2.3 Verification Axis（验证轴）

- 命名空间: `OE_MVP`
- 回答: 代码只是存在，还是已经被证明
- 状态值: `planned` → `code_exists` → `shadow_running` → `verified_e2e` → `verified_full`

### 2.4 Boundary Axis（边界完整性轴）

- 命名空间: `BOUNDARY`
- 回答: 是否发生双主、边界是否回退
- 状态值: `contract_defined` → `verified_integrity`

---

## 3. 状态语义字典

### 3.1 计划态

| 状态 | 含义 |
|------|------|
| `planned` | 已明确计划，未开始 |
| `scoped` | 范围已定义，未落代码 |
| `contract_defined` | 契约/边界/schema 已定义 |

### 3.2 实现态

| 状态 | 含义 |
|------|------|
| `code_exists` | 代码存在，但未完成验证 |
| `integrated` | 已接入主链，但未完成验证 |
| `shadow_running` | 已进入 shadow 观察 |
| `enforced` | 已正式启用 |

### 3.3 证明态

| 状态 | 含义 |
|------|------|
| `verified_contract` | 契约证明已完成 |
| `verified_e2e` | E2E 已证明 |
| `verified_integrity` | 完整性已证明 |
| `verified_full` | A/B/C 全通过 |

### 3.4 风险态

| 状态 | 含义 |
|------|------|
| `blocked` | 有明确阻塞，不允许继续晋级 |
| `disputed` | 真相源冲突，禁止乐观口径 |
| `refuted` | 已有证据推翻旧结论 |
| `deprecated` | 已废弃 |
| `legacy_compat_only` | 仅保留兼容 |

---

## 4. 裁决规则

### 4.1 优先级

```
boundary_axis > verification_axis > subject_axis > host_axis
```

### 4.2 一票否决

出现以下任一情况，总状态自动不得高于 `blocked`：

- `boundary_axis = blocked | violated`
- `verification_axis = blocked | refuted`
- `subject_axis = disputed`
- 任一主线条目是 `code_exists` 却被写成 `completed`

### 4.3 阻塞优先

一旦出现 `blocked` / `disputed` / `refuted` / `code_exists_but_unverified`，不得用"已完成"覆盖。

---

## 5. 命名空间

### 5.1 EG_PHASE（EgoCore）

描述宿主工程进度。

```
EG_PHASE:P0      - 宿主化接线
EG_PHASE:P0.5    - 宿主化收口审计
EG_PHASE:P1-A    - Identity Invariants
EG_PHASE:P1-B    - Self-Model
EG_PHASE:P1-C    - Long-Term Self Summary + Restore
EG_PHASE:P2-A/B/C/D - 后续阶段
EG_PHASE:P3-A/B/C/D - 模块化治理
```

### 5.2 OE_MVP（OpenEmotion）

描述 OpenEmotion 版本主线。

```
OE_MVP:11.5 - SRAP Stabilization
OE_MVP:12   - Developmental Core
OE_MVP:13   - Persistent Self-Model
OE_MVP:14   - Endogenous Drives
OE_MVP:15   - Reflective Self
OE_MVP:16   - Open Developmental Self
```

### 5.3 SELF_WS（主体能力）

描述 Minimum Viable Self 主线。

```
SELF_WS:A   - 持续身份
SELF_WS:B   - Self-Model v1
SELF_WS:C1  - 三层记忆模型 v1
SELF_WS:C2  - Salience
SELF_WS:D   - Appraisal
SELF_WS:E   - Reflection
```

---

## 6. 与 Gate 的关系

| Gate | 进度账字段 |
|------|------------|
| Gate A: Contract | `boundary_axis.contract_defined` |
| Gate B: E2E | `verification_axis.verified_e2e` |
| Gate C: Integrity | `boundary_axis.verified_integrity` |

---

## 7. 更新规则

每次更新必须写明：

1. 更新人
2. 变更前状态
3. 变更后状态
4. 触发证据
5. 影响的下一步

---

## 8. 同步文件

以下文件必须引用统一进度账：

- `OpenEmotion README.md`
- `OpenEmotion artifacts/handoff/LATEST_HANDOFF.md`
- `OpenEmotion roadmap/ROADMAP_STATE.json`
- `EgoCore docs/CURRENT_STATE.md`
- `EgoCore README.md`

---

## 9. 一句话裁决准则

> **局部编号描述局部推进；统一进度账裁决整体状态。**
