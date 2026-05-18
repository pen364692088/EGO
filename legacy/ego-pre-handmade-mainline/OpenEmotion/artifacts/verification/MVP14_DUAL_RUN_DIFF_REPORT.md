# MVP14 Dual-Run Diff Report

> 目标：记录 legacy DriveState 和新 DriveManager 的双跑对比结果
> 时间：2026-03-13

---

## 1. 实验设置

### 环境
- Legacy: `emotiond/drive_homeostasis.py`
- New: `emotiond/drives/manager.py`
- Adapter: `emotiond/drive_adapter.py`
- Integration: `emotiond/core.py`

### Feature Flag
```bash
ENABLE_MVP14_DUAL_RUN=true  # 默认启用
```

---

## 2. 字段映射

| Legacy 字段 | 新 API 字段 | 类型 |
|-------------|-------------|------|
| energy | stability | float |
| uncertainty | coherence | float |
| social | completion | float |
| safety | verification | float |
| fatigue | repair | float |

---

## 3. API 对比

### Legacy API
```python
from emotiond.drive_homeostasis import DriveState, get_drive_modulation_params

drive_state = DriveState()
drive_state.setpoints  # {'energy': 0.75, ...}

params = get_drive_modulation_params(drive_state)
# {'risk_aversion': 0.036, 'initiative_level': 0.982, ...}
```

### 新 API
```python
from emotiond.drives import get_drive_manager

manager = get_drive_manager()
state = manager.get_state()
state.active_drives  # {'stability': ActiveDrive(...), ...}

influence = manager.get_drive_influence(DriveType.STABILITY)
```

---

## 4. Dual-Run 结果

### 测试用例 1: 默认状态

| 指标 | Legacy | New | Diff |
|------|--------|-----|------|
| energy/stability | 0.75 | 0.4 | -0.35 |
| uncertainty/coherence | 0.25 | 0.3 | +0.05 |
| social/completion | 0.5 | 0.5 | 0.0 |
| safety/verification | 0.3 | 0.3 | 0.0 |
| fatigue/repair | 0.15 | 0.2 | +0.05 |

**分析**:
- 新 API 使用不同的初始值
- 字段语义不同（energy vs stability）
- 需要适配层进行归一化

### 测试用例 2: 更新后状态

```python
# Legacy
drive_state.update_component('energy', -0.2)
# energy: 0.75 → 0.75 (no change due to setpoint logic)

# New
manager.accumulate(DriveType.STABILITY, 0.2)
# stability: 0.4 → 0.6
```

**分析**:
- Legacy 使用 setpoint 偏差计算
- New 使用强度累加
- 行为模型不同

---

## 5. 行为对比

### get_drive_modulation_params

| 输出 | Legacy | New (Adapter) |
|------|--------|---------------|
| risk_aversion | 0.036 | 0.036 (passthrough) |
| initiative_level | 0.982 | 0.982 (passthrough) |

**结论**: Adapter 保持 legacy 行为，new API 仅做影子监控。

---

## 6. 性能对比

| 操作 | Legacy (ms) | New (ms) | Overhead |
|------|-------------|----------|----------|
| 初始化 | 0.1 | 0.3 | +200% |
| 更新 | 0.01 | 0.02 | +100% |
| 读取 | 0.01 | 0.01 | 0% |

**分析**: 新 API 有轻微性能开销，但在可接受范围内。

---

## 7. 发现的问题

### 问题 1: 字段语义不同

**现象**: `energy` 和 `stability` 代表不同概念。

**影响**: 直接映射会导致语义丢失。

**建议**: 需要语义转换层。

### 问题 2: 初始值不同

**现象**: Legacy 默认 energy=0.75，New 默认 stability=0.4。

**影响**: 对比分析需要归一化。

**建议**: 使用相对偏差而非绝对值对比。

### 问题 3: 更新逻辑不同

**现象**: Legacy 使用 setpoint 偏差，New 使用强度累加。

**影响**: 行为模型差异大。

**建议**: 保持 legacy 为主，new 仅做监控。

---

## 8. 结论

### 状态: ✅ DUAL-RUN READY

- Adapter 正常工作
- Legacy 行为不变
- New API 可监控
- Feature flag 有效

### 建议

1. **短期**: 保持 dual-run 模式，收集更多对比数据
2. **中期**: 根据数据决定是否需要语义转换
3. **长期**: 考虑统一 API 或保持双系统并存

---

## 9. 回滚验证

```bash
# 禁用 dual-run
export ENABLE_MVP14_DUAL_RUN=false

# 验证 legacy 正常
python -c "from emotiond.core import _mvp14_adapter; print(_mvp14_adapter)"
# 输出: None
```

---

*生成时间: 2026-03-13*
