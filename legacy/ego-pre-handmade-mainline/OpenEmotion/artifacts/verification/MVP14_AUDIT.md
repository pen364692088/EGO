# MVP14 Audit Report

> Phase F: MVP14 验证
> 审计时间: 2026-03-13

---

## 验证范围

MVP14 核心验证点：
- 内部驱动变量是否真实推动行为
- homeostasis variables
- endogenous policy shifts
- self-maintenance routines
- internal goal pressure

---

## 验证结果汇总

| 项目 | 状态 | 证据 |
|------|------|------|
| 测试通过 | ✅ PASS | 40 passed |
| 新模块存在 | ✅ PASS | emotiond/drives/ |
| Legacy 模块存在 | ✅ PASS | emotiond/drive_homeostasis.py |
| 新模块接线 | ❌ FAIL | DriveManager 未使用 |
| Legacy 接线 | ✅ PASS | core.py 使用 drive_homeostasis |
| Legacy 因果效力 | ✅ PASS | 之前审计验证 |
| 新模块因果效力 | ❌ N/A | 未接线 |

**最终裁决**: **PARTIAL**

---

## 详细证据

### 1. 模块结构

**新 MVP14 模块** (`emotiond/drives/`):
```
drives/
├── __init__.py        # 模块导出
├── schema.py          # 新 Schema (DriveState, DriveType, etc.)
├── manager.py         # DriveManager
└── integration.py     # 集成层
```

**Legacy 模块** (`emotiond/drive_homeostasis.py`):
```python
class DriveState:
    """Homeostatic drive state management"""
    def __init__(self):
        self.setpoints = {
            "energy": 0.75,
            "uncertainty": 0.25,
            "social": 0.5,
            "safety": 0.75,
            "fatigue": 0.15,
        }
```

### 2. 测试验证

```
tests/mvp14/: 40 passed
```

测试覆盖：
- `test_drive_infra.py` - Drive 基础设施
- `test_drive_integration.py` - Drive 集成
- `test_e2e_gate_b.py` - E2E Gate B

### 3. 主链使用分析

**core.py 导入**:
```python
from emotiond.drive_homeostasis import (
    DriveState, drive_error, emotion_from_drive,
)
```

**实际调用**:
```python
# core.py line 1056
drive_state = DriveState()
```

**结论**: ✅ 使用 legacy `drive_homeostasis`，❌ 未使用新 `DriveManager`

### 4. 新旧 API 对比

| 特性 | Legacy (drive_homeostasis.py) | MVP14 (drives/) |
|------|-------------------------------|-----------------|
| 数据结构 | dict-based | Pydantic model |
| 持久化 | ❌ | ✅ (设计存在) |
| 主链使用 | ✅ | ❌ |
| 因果效力 | ✅ 验证过 | ❌ 未验证 |

**Legacy DriveState 字段**:
- `energy`, `uncertainty`, `social`, `safety`, `fatigue`

**新 MVP14 DriveState 字段**:
- `active_drives`, `latent_drives`, `homeostatic_signals`
- `maintenance_debt`, `regulation_targets`, `drive_history`

---

## 因果干预验证 (Legacy)

**之前审计结果**: ✅ Legacy drive 有因果效力

**实验**: 修改 DriveState，观察调制参数变化

```
Default: risk_aversion=0.036, initiative_level=0.982
Modified: risk_aversion=0.048, initiative_level=0.976
```

**结论**: Legacy drive 确实影响决策参数。

---

## 因果干预验证 (新 MVP14)

**状态**: ❌ 无法执行

**原因**: `DriveManager` 未接入主链，无法验证其对行为的影响。

---

## 持久化验证

### 新 MVP14 DriveManager

**API 存在**: ✅
```python
class DriveManager:
    def get_state(self) -> DriveState
    def save(self) -> bool
    def load(self) -> bool
```

**实际使用**: ❌ 未在主链调用

### Legacy DriveState

**持久化机制**: ❌ 无

**状态**: 每次创建新实例，无持久化

---

## 发现的问题

### 1. 新 API 未接线 (CRITICAL)

**现象**: `DriveManager` 未在主链使用。

**影响**:
- 宣称的"Endogenous Drives"新功能未生效
- 主链使用旧实现
- 持久化机制未真正使用

### 2. 两套 Drive 系统并存

**现象**: 
- `emotiond/drives/` (新，未使用)
- `emotiond/drive_homeostasis.py` (旧，使用中)

**风险**:
- 混淆
- 维护负担
- 测试与实际不一致

### 3. 无持久化 (Legacy)

**现象**: Legacy `DriveState` 无持久化机制。

**影响**: 驱动状态不跨会话保留。

---

## 判定理由

### PARTIAL 判定

1. ✅ 新模块存在且测试通过
2. ✅ Legacy 模块有因果效力
3. ❌ 新 MVP14 API 未接线
4. ❌ 宣称的是新功能，实际用的是旧实现
5. ⚠️ 无持久化

### 为什么不是 PASS_WEAK

PASS_WEAK 要求"机制存在且可运行"。MVP14 的新机制 (`DriveManager`) 存在但未运行。虽然 legacy 有因果效力，但宣称的是 MVP14 新功能。

---

## 建议行动

### 立即行动 (P0)

1. 在 `core.py` 中集成 `DriveManager`
2. 替换 `DriveState()` 调用为 `get_drive_manager().get_state()`

### 中期行动 (P1)

1. 添加集成测试验证主链调用
2. 实现新 API 的因果干预验证
3. 实现持久化

### 长期行动 (P2)

1. 统一 API，废弃 legacy
2. 添加跨会话连续性验证

---

## 裁决

**MVP14**: **PARTIAL**

- 新模块存在: ✅
- 可运行: ✅ (测试通过)
- 起作用: ⚠️ (仅 legacy)
- 可证明起作用: ⚠️ (仅 legacy 验证过)
- 持久化: ❌

**注**: 如果只评估 legacy 实现，可以是 PASS_WEAK。但宣称的是 MVP14 新功能，因此判 PARTIAL。

---

*审计完成时间: 2026-03-13*
