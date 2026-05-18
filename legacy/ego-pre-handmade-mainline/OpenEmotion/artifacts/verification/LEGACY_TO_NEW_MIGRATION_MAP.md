# Legacy to New Migration Map

> 目标：记录 legacy API 到新 API 的迁移路径
> 时间：2026-03-13

---

## 概述

OpenEmotion 存在两套并行的实现：
1. **Legacy**: 原始实现，当前主链使用
2. **New**: MVP12-16 新实现，未接线主链

---

## 迁移映射表

| 阶段 | Legacy 模块 | 新模块 | 状态 | 风险 |
|------|------------|--------|------|------|
| MVP12 | N/A | `developmental_core/` | ✅ WIRED | 低 |
| MVP13 | `emotiond/self_model/legacy.py` | `emotiond/self_model/` | ⚠️ BLOCKED | 高 |
| MVP14 | `emotiond/drive_homeostasis.py` | `emotiond/drives/` | ⚠️ BLOCKED | 中 |
| MVP15 | `emotiond/reflection.py` | `emotiond/reflection_engine/` | ⏳ NOT_STARTED | 中 |
| MVP16 | N/A | `emotiond/developmental/` | ⏳ NOT_STARTED | 低 |

---

## MVP12: DevelopmentalCore

**状态**: ✅ WIRED (2026-03-13)

**Legacy**: 无

**新模块**: `emotiond/developmental_core/`

**接线位置**: `emotiond/daemon.py`

**迁移步骤**:
1. ✅ 导入 `create_dev_daemon`
2. ✅ 初始化 `_dev_daemon`
3. ✅ 创建 `_developmental_cycle_loop()`

---

## MVP13: SelfModel

**状态**: ⚠️ BLOCKED

**Legacy**: `emotiond/self_model/legacy.py`
```python
from emotiond.self_model import get_self_model_v0, build_self_model_v0
```

**新模块**: `emotiond/self_model/`
```python
from emotiond.self_model import SelfModelManager, get_self_model_manager
```

**API 差异**:
| Legacy | New |
|--------|-----|
| `SelfModelV0` | `SelfModelState` |
| `apply_event()` | `update_behavior()` |
| `compute_hash()` | `state.identity_hash` |
| `ValueWeights` | `BehavioralTendencies` |

**迁移策略**:
- 创建适配器 `SelfModelAdapter`
- 逐步替换 `get_self_model_v0()` 调用

---

## MVP14: Drives

**状态**: ⚠️ BLOCKED

**Legacy**: `emotiond/drive_homeostasis.py`
```python
from emotiond.drive_homeostasis import DriveState, get_drive_modulation_params
```

**新模块**: `emotiond/drives/`
```python
from emotiond.drives import DriveManager, get_drive_manager
```

**API 差异**:
| Legacy | New |
|--------|-----|
| `DriveState.setpoints` | `DriveState.active_drives` |
| `update_component()` | `update_drive()` |
| `get_deviation()` | `get_drive_influence()` |
| `components["energy"]` | `active_drives["stability"]` |

**迁移策略**:
- 创建适配器映射字段名
- `energy` → `stability`
- `uncertainty` → `coherence`
- `social` → `completion`
- `safety` → `verification`
- `fatigue` → `repair`

---

## MVP15: Reflection

**状态**: ⏳ NOT_STARTED

**Legacy**: `emotiond/reflection.py`
```python
from emotiond.reflection import run_reflection
```

**新模块**: `emotiond/reflection_engine/`
```python
from emotiond.reflection_engine import ReflectionEngine, get_reflection_engine
```

**API 差异**:
| Legacy | New |
|--------|-----|
| `run_reflection(event, target_id)` | `engine.execute_reflection(job)` |
| 返回 dict | 返回 `ReflectionResult` |

**迁移策略**:
- 创建包装函数适配签名
- 或替换 `run_reflection` 实现

---

## MVP16: Developmental

**状态**: ⏳ NOT_STARTED

**Legacy**: 无

**新模块**: `emotiond/developmental/`
```python
from emotiond.developmental import DevelopmentalManager, get_developmental_manager
```

**接线位置**: 可选 `daemon.py` 或独立进程

**迁移策略**:
- 初始化并积累真实数据
- 连续性指标监控

---

## 执行优先级

1. **P0 - 低风险**: MVP15, MVP16
2. **P1 - 中风险**: MVP14 (需要适配器)
3. **P2 - 高风险**: MVP13 (核心组件)

---

## 回滚方案

每个阶段都有回滚方案：
```bash
# 回滚单个文件
git checkout HEAD -- emotiond/daemon.py
git checkout HEAD -- emotiond/core.py
```

---

*创建时间: 2026-03-13*
