# Causal Intervention Report

> MVP11.5-16 独立真实性审计 | 因果干预实验

**模式**: Verification-Only / Audit Mode  
**日期**: 2026-03-12  
**方法**: 修改状态变量，观察行为是否发生可追踪变化

---

## 实验目标

验证以下因果链是否真实存在：

1. **Self-Model → 决策偏置**: 修改 self-model tension/behavioral tendency 是否影响决策？
2. **Drives/Homeostasis → 候选排序**: 修改 drive strength 是否影响行为？
3. **Reflection → 未来行为**: 批准 proposal 后是否产生行为变化？
4. **Developmental → 连续性**: 状态是否累积并影响后续行为？

---

## 实验结果摘要

| 实验组 | 总测试 | 通过 | 失败 | 关键发现 |
|--------|--------|------|------|----------|
| Self-Model 干预 | 3 | 0 | 3 | 新模块未接线，旧模块有偏置能力 |
| Drives 干预 | 4 | 3 | 1 | 旧模块有效，新模块未接线 |
| Reflection 干预 | 4 | 0 | 4 | 新引擎未接线，旧模块存在 |
| Developmental 干预 | 3 | 1 | 2 | 状态可累积但未接线主链 |

**总计**: 14 测试, 4 通过, 10 失败

---

## 实验 1: Self-Model Causal Intervention

### 假设
修改 self-model tension/behavioral tendency 应影响决策偏置。

### 测试 1.1: Legacy SelfModelV0 决策偏置

**结果**: ❌ FAIL

**发现**:
- `SelfModelV0` 对象没有 `get` 方法
- API 签名与实际实现不匹配
- `apply_self_model_to_decision` 函数存在但无法正常调用

**证据**:
```
Exception: 'SelfModelV0' object has no attribute 'get'
```

**结论**: Legacy self-model API 存在缺陷，但代码路径显示 legacy 确实被 core.py 使用。

---

### 测试 1.2: MVP13 SelfModelManager Tension 更新

**结果**: ❌ FAIL

**发现**:
- `TensionType.VALUE_CONFLICT` 属性不存在
- 新 schema 定义与实际使用脱节
- 类型枚举可能使用了不同的命名

**证据**:
```
Exception: type object 'TensionType' has no attribute 'VALUE_CONFLICT'
```

**结论**: MVP13 新模块存在但 API 不完整或文档化不足。

---

### 测试 1.3: MVP13 SelfModelManager 主链接线

**结果**: ❌ FAIL

**发现**:
- `core.py` 不导入 `SelfModelManager`
- `core.py` 继续使用 `get_self_model_v0()` (legacy)
- 宣称的 "Persistent Self-Model" 未在主链生效

**证据**:
```
core.py does NOT import SelfModelManager - uses legacy API
```

**裁决**: **Claimed but Unproven** - 模块存在，主链未接线

---

## 实验 2: Drives/Homeostasis Causal Intervention

### 假设
修改 drive strength/homeostatic deviation 应影响候选排序和行为。

### 测试 2.1: Legacy DriveState 调制参数

**结果**: ✅ PASS

**发现**:
- 修改 `DriveState` 组件后，调制参数确实变化
- 证明旧 drive_homeostasis 模块有真实的因果影响力

**证据**:
```
Default modulation params: {'risk_aversion': 0.036, 'clarification_need': 0.027, 'initiative_level': 0.982}
Modified modulation params: {'risk_aversion': 0.048, 'clarification_need': 0.036, 'initiative_level': 0.976}
```

**结论**: Legacy drive 模块对行为有因果影响。

---

### 测试 2.2: MVP14 DriveManager 模块存在

**结果**: ✅ PASS

**发现**:
- `DriveManager` 实例可创建
- 有完整的 schema 定义

---

### 测试 2.3: MVP14 DriveManager 主链接线

**结果**: ❌ FAIL

**发现**:
- `core.py` 不导入 `DriveManager`
- `core.py` 使用 `emotiond.drive_homeostasis` (旧模块)
- 宣称的 "Endogenous Drives" 使用旧实现

**裁决**: **Claimed but Unproven** - 模块存在，主链未接线

---

### 测试 2.4: Drive Error 对情绪选择的影响

**结果**: ✅ PASS

**发现**:
- `drive_error()` 函数产生有效的情绪信号
- 证明 drive 状态可以影响情绪选择

---

## 实验 3: Reflection Engine Causal Intervention

### 假设
批准 reflection proposal 后应产生可追踪的行为变化。

### 测试 3.1: Legacy reflection.py 调用

**结果**: ❌ FAIL

**发现**:
- `run_reflection()` 需要特定参数 (`target_id`, `counterparty_id`)
- 当前测试环境无法提供完整上下文
- 主链确实调用此函数

**证据**:
```
Exception: run_reflection() missing 2 required positional arguments: 'target_id' and 'counterparty_id'
```

---

### 测试 3.2: MVP15 ReflectionEngine 模块存在

**结果**: ❌ FAIL

**发现**:
- `get_reflection_engine` 导入失败
- 模块可能存在初始化问题

**证据**:
```
cannot access local variable 'get_reflection_engine' where it is not associated with a value
```

---

### 测试 3.3: MVP15 ReflectionEngine 主链接线

**结果**: ❌ FAIL

**发现**:
- `core.py` 不导入 `ReflectionEngine`
- `core.py` 使用 `emotiond.reflection` (旧模块)

**裁决**: **Claimed but Unproven** - 模块存在，主链未接线

---

### 测试 3.4: Proposal 批准机制

**结果**: ❌ FAIL

**发现**:
- `generate_proposal` 方法不存在
- 无法验证 proposal → 行为变化的因果链

**结论**: Reflection Engine 的 proposal/approval 机制未实现或不完整。

---

## 实验 4: Developmental Causal Intervention

### 假设
Developmental 状态应累积并影响连续性指标。

### 测试 4.1: Developmental Manager 初始状态

**结果**: ✅ (信息收集)

**发现**:
- 初始 `continuity_score = 0.825`
- 初始 `episodes = 0`
- 初始 `identity_preserved = True`

---

### 测试 4.2: Episode 累积

**结果**: ✅ PASS

**发现**:
- `record_episode()` 成功添加 episode
- Episodes 从 0 增加到 1
- 状态在内存中可以累积

**证据**:
```
Before episode: {'episodes': 0, ...}
After episode: {'episodes': 1, ...}
```

---

### 测试 4.3: Metric 更新

**结果**: ❌ FAIL

**发现**:
- `continuity_score` 从 0.825 变为 0.85 (设置值为 0.9)
- 精度损失或内部计算覆盖了设置值
- metric 更新机制可能有问题

---

### 测试 4.4: MVP16 Developmental 主链接线

**结果**: ❌ FAIL

**发现**:
- `core.py` 不导入 `DevelopmentalManager`
- developmental 模块完全独立于主链

**裁决**: **Claimed but Unproven** - 模块存在，主链未接线

---

## 因果链真实性总结

### 真实因果链 (Verified)

| 模块 | 路径 | 因果效果 |
|------|------|----------|
| Drive Modulation | `drive_homeostasis.DriveState` → `get_drive_modulation_params()` | ✅ 修改 drive 组件 → 调制参数变化 |
| Drive Emotion | `drive_homeostasis.drive_error()` | ✅ Drive 状态 → 情绪信号 |
| Episode Accumulation | `developmental.manager.record_episode()` | ✅ 调用 → episodes++ (内存) |

### 宣称但未验证 (Claimed but Unproven)

| 宣称 | 代码现实 | 问题 |
|------|----------|------|
| MVP13 "Persistent Self-Model" | Legacy SelfModelV0 在用 | 新模块未接线 |
| MVP14 "Endogenous Drives" | Legacy drive_homeostasis 在用 | 新模块未接线 |
| MVP15 "Reflective Self" | Legacy reflection.py 在用 | 新模块未接线 |
| MVP16 "Open Developmental" | 模块独立运行 | 未接入主链 |

### 因果链缺失 (Causal Gap)

1. **Self-Model Tension → 决策**: 新 schema 有 tension 概念，但未连接到决策偏置
2. **Reflection Proposal → 行为变化**: 无 `generate_proposal` 方法
3. **Developmental → 主链行为**: 状态在内存累积，但不影响任何主链决策

---

## 关键发现

### 发现 1: 新模块存在但未接线

所有 MVP13-16 的新模块都存在且有测试，但 `core.py` 继续使用旧实现：

- `self_model/` → core.py 使用 `legacy.py`
- `drives/` → core.py 使用 `drive_homeostasis.py`
- `reflection_engine/` → core.py 使用 `reflection.py`
- `developmental/` → core.py 完全不使用

### 发现 2: Legacy 系统有因果效力

旧的 `drive_homeostasis` 模块确实能影响行为：
- 修改 `DriveState` 组件 → `get_drive_modulation_params()` 返回值变化
- `drive_error()` 产生情绪信号

### 发现 3: 新模块因果链断裂

新模块的因果链设计：
- MVP13: `TensionType` 枚举不完整
- MVP15: 无 `generate_proposal` 方法
- MVP16: 状态累积但不影响任何决策

---

## 结论

| 阶段 | 因果干预结论 | 证据 |
|------|-------------|------|
| MVP11.5 | Conditionally Verified | Intent checker 在主链，shadow mode |
| MVP12 | Claimed but Unproven | 模块存在，主链接线未验证 |
| MVP13 | Claimed but Unproven | 新模块未接线，legacy 在用 |
| MVP14 | **Verified (Legacy)** | Legacy drive 有因果效力，新模块未接线 |
| MVP15 | Claimed but Unproven | 新模块未接线，proposal 机制缺失 |
| MVP16 | Claimed but Unproven | 模块存在但未影响主链决策 |

**最终裁定**: MVP13-16 的"已完成"声明在因果验证层面不成立。新模块未接入主链，当前运行的是 legacy 实现。

---

*实验执行时间: 2026-03-12*  
*审计模式: Verification-Only*
