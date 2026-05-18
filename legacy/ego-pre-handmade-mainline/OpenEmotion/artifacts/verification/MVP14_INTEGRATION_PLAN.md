# MVP14 Integration Plan

> 目标：将 `DriveManager` 接线到 `core.py`
> 时间：2026-03-13

---

## 1. 现状分析

### Legacy API (当前使用)
```python
from emotiond.drive_homeostasis import DriveState, drive_error, emotion_from_drive
```

使用位置：
- Line 67-68: 导入
- Line 1056: 创建 `DriveState()`
- `get_drive_modulation_params()` 调用

### 新 MVP14 API
```python
from emotiond.drives import DriveManager, get_drive_manager
```

关键方法：
- `get_state()` → DriveState (Pydantic)
- `get_drive_value(name)` → float
- `update_drive(name, delta)` → 更新

---

## 2. 接线策略

### 方案: 简单替换 (低风险)

`DriveState` 是独立组件，不依赖其他模块，可以直接替换。

### Step 1: 导入

```python
# Before
from emotiond.drive_homeostasis import DriveState, drive_error, emotion_from_drive

# After
from emotiond.drives import get_drive_manager, DriveState
```

### Step 2: 使用

```python
# Before
drive_state = DriveState()

# After
drive_manager = get_drive_manager()
drive_state = drive_manager.get_state()
```

---

## 3. 验证计划

### Gate A: Contract
- [ ] DriveManager 初始化正确
- [ ] get_state() 返回有效状态

### Gate B: E2E
- [ ] 运行 tests/mvp14
- [ ] 验证因果干预

### Gate C: Preflight
- [ ] 无破坏性变更

---

## 4. 风险评估

- 风险等级: **低**
- 原因: DriveState 独立性强，无复杂依赖
- 回滚: 简单恢复导入

---

*创建时间: 2026-03-13*
