# Trace Index

> 关键模块调用点索引 | 独立真实性审计

---

## 索引说明

本索引记录关键模块在主链中的调用点。
"未找到"表示该模块/函数未被主处理链调用。

---

## MVP13 — self_model

### 新模块调用点

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `SelfModelState` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `IdentityCore` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `StableConstraints` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `BehavioralTendencies` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `ActiveTensions` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `LongHorizonOrientations` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `ContinuityTrace` | `emotiond/self_model/schema.py` | 未找到 | ❌ 未使用 |
| `SelfModelPersistence` | `emotiond/self_model/persistence.py` | 未找到 | ❌ 未使用 |
| `SelfModelUpdater` | `emotiond/self_model/updates.py` | 未找到 | ❌ 未使用 |
| `SelfModelIntegration` | `emotiond/self_model/integration.py` | 未找到 | ❌ 未使用 |

### Legacy 调用点 (实际使用)

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `get_self_model_v0` | `emotiond/self_model/legacy.py` | Line 42, 827 | ✅ 使用 |
| `reset_self_model_v0` | `emotiond/self_model/legacy.py` | Line 42 | ✅ 使用 |
| `build_self_model_v0` | `emotiond/self_model/legacy.py` | Line 42 | ✅ 使用 |
| `render_self_report` | `emotiond/self_model/legacy.py` | Line 42, 845 | ✅ 使用 |
| `SelfModelV0` | `emotiond/self_model/legacy.py` | 间接使用 | ✅ 使用 |

---

## MVP14 — drives

### 新模块调用点

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `DriveManager` | `emotiond/drives/manager.py` | 未找到 | ❌ 未使用 |
| `get_drive_manager` | `emotiond/drives/manager.py` | 未找到 | ❌ 未使用 |
| `reset_drive_manager` | `emotiond/drives/manager.py` | 未找到 | ❌ 未使用 |
| `DriveState` (新) | `emotiond/drives/schema.py` | 未找到 | ❌ 未使用 |
| `ActiveDrive` | `emotiond/drives/schema.py` | 未找到 | ❌ 未使用 |
| `DriveType` | `emotiond/drives/schema.py` | 未找到 | ❌ 未使用 |
| `HomeostaticSignal` | `emotiond/drives/schema.py` | 未找到 | ❌ 未使用 |
| `MaintenanceDebt` | `emotiond/drives/schema.py` | 未找到 | ❌ 未使用 |
| `drive_integration.sync_with_self_model` | `emotiond/drives/integration.py` | 未找到 | ❌ 未使用 |
| `drive_integration.get_candidate_bias` | `emotiond/drives/integration.py` | 未找到 | ❌ 未使用 |

### Legacy 调用点 (实际使用)

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `DriveState` (旧) | `emotiond/drive_homeostasis.py` | Line 67 | ✅ 使用 |
| `drive_error` | `emotiond/drive_homeostasis.py` | Line 67 | ✅ 使用 |
| `emotion_from_drive` | `emotiond/drive_homeostasis.py` | Line 67 | ✅ 使用 |
| `get_drive_modulation_params` | `emotiond/drive_homeostasis.py` | Line 67 | ✅ 使用 |
| `get_state_hash` | `emotiond/drive_homeostasis.py` | Line 67 | ✅ 使用 |

---

## MVP15 — reflection_engine

### 新模块调用点

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `ReflectionEngine` | `emotiond/reflection_engine/engine.py` | 未找到 | ❌ 未使用 |
| `get_reflection_engine` | `emotiond/reflection_engine/engine.py` | 未找到 | ❌ 未使用 |
| `reset_reflection_engine` | `emotiond/reflection_engine/engine.py` | 未找到 | ❌ 未使用 |
| `ReflectionState` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |
| `ReflectionJob` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |
| `ReflectionType` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |
| `CounterfactualRun` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |
| `DiagnosisRecord` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |
| `ReflectionProposal` | `emotiond/reflection_engine/schema.py` | 未找到 | ❌ 未使用 |

### Legacy 调用点 (实际使用)

| 模块/函数 | 文件位置 | core.py 调用点 | 状态 |
|----------|---------|---------------|------|
| `run_reflection` | `emotiond/reflection.py` | Line 22 | ✅ 使用 |

---

## MVP16 — developmental

### 新模块调用点

| 模块/函数 | 文件位置 | core.py 调用点 | api.py 调用点 | 状态 |
|----------|---------|---------------|--------------|------|
| `DevelopmentalManager` | `emotiond/developmental/manager.py` | 未找到 | 未找到 | ❌ 未使用 |
| `get_developmental_manager` | `emotiond/developmental/manager.py` | 未找到 | 未找到 | ❌ 未使用 |
| `reset_developmental_manager` | `emotiond/developmental/manager.py` | 未找到 | 未找到 | ❌ 未使用 |
| `DevelopmentalState` | `emotiond/developmental/schema.py` | 未找到 | 未找到 | ❌ 未使用 |
| `DevelopmentalEpisode` | `emotiond/developmental/schema.py` | 未找到 | 未找到 | ❌ 未使用 |
| `TransitionRecord` | `emotiond/developmental/schema.py` | 未找到 | 未找到 | ❌ 未使用 |
| `GrowthMetric` | `emotiond/developmental/schema.py` | 未找到 | 未找到 | ❌ 未使用 |
| `DevelopmentalTrajectory` | `emotiond/developmental/schema.py` | 未找到 | 未找到 | ❌ 未使用 |

### 仅在独立脚本中调用

| 脚本 | 调用点 |
|------|--------|
| `tools/mvp16_daily_check.py` | Line 15, 30, 46, 68, 78 |

---

## 汇总统计

| MVP阶段 | 新模块函数/类 | 主链调用次数 | 状态 |
|---------|-------------|-------------|------|
| MVP13 | ~20 | 0 (legacy: 5) | ⚠️ 仅 legacy |
| MVP14 | ~15 | 0 (legacy: 5) | ❌ 未接线 |
| MVP15 | ~10 | 0 (legacy: 1) | ❌ 未接线 |
| MVP16 | ~10 | 0 | ❌ 未接线 |

---

## 验证命令

```bash
# 验证 MVP13 新 schema 未使用
grep -rn "SelfModelState\|IdentityCore\|ContinuityTrace" emotiond/core.py emotiond/api.py
# (无输出)

# 验证 MVP14 新模块未使用
grep -rn "DriveManager\|get_drive_manager" emotiond/core.py emotiond/api.py
# (无输出)

# 验证 MVP15 新模块未使用
grep -rn "ReflectionEngine\|get_reflection_engine" emotiond/core.py emotiond/api.py
# (无输出)

# 验证 MVP16 新模块未使用
grep -rn "DevelopmentalManager\|get_developmental_manager" emotiond/core.py emotiond/api.py
# (无输出)
```

---

*索引生成时间: 2026-03-12*
