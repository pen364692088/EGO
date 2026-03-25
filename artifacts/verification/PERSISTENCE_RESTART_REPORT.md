# Persistence & Restart Report

> MVP11.5-16 独立真实性审计 | 持久化与重启实验

**模式**: Verification-Only / Audit Mode  
**日期**: 2026-03-12  
**方法**: 测试状态在 reset/重启 后是否保留

---

## 实验目标

验证以下持久化声明：

1. **Self-Model Revision History**: 修订历史是否保留？
2. **Drives State**: Drive 状态是否跨会话保留？
3. **Developmental Episodes/Transitions**: Episodes 和 transitions 是否持久化？
4. **MVP16 观测数据**: Daily check 读取的是真实积累状态还是默认值？

---

## 实验结果摘要

| 实验组 | 总测试 | 通过 | 失败 | 关键发现 |
|--------|--------|------|------|----------|
| Self-Model 持久化 | 4 | 2 | 2 | 有持久化 API，但 reset 清除状态 |
| Drives 持久化 | 2 | 1 | 1 | 无持久化机制 |
| Developmental 持久化 | 4 | 0 | 4 | **CRITICAL**: 状态在 reset 后丢失 |
| 跨会话状态 | 2 | 2 | 0 | Pydantic 序列化可行 |

**总计**: 12 测试, 5 通过, 7 失败  
**关键失败**: 4 (全部在 Developmental 持久化)

---

## 实验 1: Self-Model Persistence

### 测试 1.1: Legacy SelfModelV0 Reset 行为

**结果**: ✅ (预期行为)

**发现**:
- `reset_self_model_v0()` 创建新实例
- Legacy SelfModelV0 是纯内存实现
- Reset 后状态清空是预期行为

**持久化状态**: ❌ 无 (设计如此)

---

### 测试 1.2: MVP13 SelfModelManager Reset 行为

**结果**: ✅ (观察)

**发现**:
- `reset_self_model_manager()` 创建新实例
- 当前 phase 为 `None` (初始化状态)
- Reset 后回到默认状态

**持久化状态**: ❌ 无跨 reset 持久化

---

### 测试 1.3: MVP13 SelfModelPersistence API

**结果**: ✅ PASS

**发现**:
- `SelfModelPersistence` 类存在
- 有 `save` 和 `load` 方法
- 持久化 API 已实现

---

### 测试 1.4: Self-Model Persistence 主链使用

**结果**: ✅ PASS

**发现**:
- `core.py` 使用了 `SelfModelPersistence`
- 主链知道持久化 API

**裁决**: **Conditionally Verified** - 持久化机制存在，但实际使用情况需进一步验证

---

## 实验 2: Drives Persistence

### 测试 2.1: MVP14 DriveManager Reset 行为

**结果**: ✅ (观察)

**发现**:
- 初始 drives count = 7
- Reset 后 drives count = 7 (默认值恢复)
- Reset 创建新实例，状态丢失

**持久化状态**: ❌ 无跨 reset 持久化

---

### 测试 2.2: MVP14 DriveManager 持久化机制

**结果**: ❌ FAIL

**发现**:
- `DriveManager` 无 `save` 或 `load` 方法
- 无文件持久化机制
- 状态仅存在于内存

**裁决**: **Claimed but Unproven** - Drives 无持久化，重启后状态丢失

---

## 实验 3: Developmental Persistence (CRITICAL)

### 测试 3.1: Episode Persistence Across Reset

**结果**: ❌ FAIL **[CRITICAL]**

**发现**:
- Reset 前: 3 episodes, continuity=0.825
- Reset 后: 0 episodes, continuity=0.825

**证据**:
```
Before reset: 3 episodes, continuity=0.825
After reset: 0 episodes, continuity=0.825
```

**问题**: 
- Episodes 完全丢失
- continuity_score 保持默认值 (巧合等于默认)
- 无持久化保护

**结论**: **DevelopmentalManager 完全无持久化，reset 清除所有状态**

---

### 测试 3.2: DevelopmentalManager 持久化机制

**结果**: ❌ FAIL **[CRITICAL]**

**发现**:
- `DevelopmentalManager` 无 `save` 或 `load` 方法
- `DevelopmentalState` 无 `save` 或 `load` 方法
- 无任何文件持久化机制

**裁决**: **Refuted** - 无持久化机制存在

---

### 测试 3.3: Developmental 持久化文件

**结果**: ❌ FAIL **[CRITICAL]**

**检查路径**:
- `artifacts/developmental/state.json` - 不存在
- `state/developmental.json` - 不存在
- `data/developmental_state.json` - 不存在

**结论**: 无持久化文件存在

---

### 测试 3.4: MVP16 Daily Check Reset 行为分析

**结果**: ❌ FAIL **[CRITICAL]**

**发现**:
- `reset_developmental_manager()` 被调用 **3 次**
- 调用位置:
  1. `check_continuity()`
  2. `check_metrics()`
  3. `check_invariants()`

**证据** (来自 `tools/mvp16_daily_check.py`):
```python
def check_continuity() -> dict:
    reset_developmental_manager()  # ← 问题！
    manager = get_developmental_manager()
    # 读取的是刚 reset 后的默认状态

def check_metrics() -> dict:
    reset_developmental_manager()  # ← 问题！
    manager = get_developmental_manager()

def check_invariants() -> dict:
    reset_developmental_manager()  # ← 问题！
    manager = get_developmental_manager()
```

**严重性**: 这是 MVP16 审计的 **致命缺陷**

**影响**:
1. 每次检查都重置状态
2. 检查结果永远是默认值
3. 观测窗数据完全无意义
4. 无法验证任何长期连续性

**裁决**: **Refuted** - Daily Check 读取的是重置后的默认状态

---

## 实验 4: Cross-Session State (Simulated Restart)

### 测试 4.1: Self-Model 跨会话能力

**结果**: ✅ PASS

**发现**:
- `SelfModelState` 是 Pydantic 模型
- 有 `model_dump()` 方法可序列化
- 跨会话恢复理论可行

**注意**: 序列化可行 ≠ 实际持久化

---

### 测试 4.2: Developmental 跨会话能力

**结果**: ✅ PASS

**发现**:
- `DevelopmentalState` 是 Pydantic 模型
- 有 `model_dump()` 方法可序列化
- 跨会话恢复理论可行

**注意**: 序列化可行，但当前无代码实际调用

---

## 关键发现

### 发现 1: DevelopmentalManager 完全无持久化

| 功能 | 状态 |
|------|------|
| Episode 持久化 | ❌ 不存在 |
| Transition 持久化 | ❌ 不存在 |
| Metric 持久化 | ❌ 不存在 |
| 持久化 API | ❌ 不存在 |
| 持久化文件 | ❌ 不存在 |

**结论**: MVP16 的 "长期连续性" 完全无持久化支撑

---

### 发现 2: Daily Check 数据伪造

```python
# tools/mvp16_daily_check.py
def check_continuity() -> dict:
    reset_developmental_manager()  # ← 每次检查都重置
    manager = get_developmental_manager()  # ← 获取的是新实例
    summary = manager.get_summary()  # ← 返回默认值
```

**结果**:
- `continuity_score` 永远是 0.8 (默认值)
- `identity_stability` 永远是 1.0 (默认值)
- `governance_compliance` 永远是 1.0 (默认值)

**影响**:
- ROADMAP_STATE.json 中的 "observation PASS" 无意义
- 14 天观测窗无法验证任何真实连续性
- 所有 Day 1-14 报告都是默认值

---

### 发现 3: Drives 无持久化

- `DriveManager` 无任何持久化机制
- 重启后 drives 状态完全丢失
- 宣称的 "Endogenous Drives" 不具备跨会话连续性

---

### 发现 4: Self-Model 持久化条件验证

- `SelfModelPersistence` API 存在
- 主链知道此 API
- 但实际调用路径和持久化时机未验证

---

## 持久化状态总结

| 模块 | 持久化机制 | Reset 后状态 | 跨重启连续性 |
|------|-----------|-------------|-------------|
| Legacy SelfModelV0 | ❌ 无 | 丢失 | ❌ 无 |
| MVP13 SelfModelManager | ❌ 无 | 丢失 | ❌ 无 |
| MVP13 SelfModelPersistence | ✅ API 存在 | 未验证 | ⚠️ 部分 |
| MVP14 DriveManager | ❌ 无 | 丢失 | ❌ 无 |
| MVP16 DevelopmentalManager | ❌ 无 | 丢失 | ❌ 无 |

---

## 结论

### MVP16 持久化裁决

**裁决**: **Refuted**

**理由**:
1. DevelopmentalManager 无任何持久化机制
2. Daily Check 在每次检查时 reset 状态
3. 观测数据读取的是默认值，非真实积累状态
4. 无法验证任何长期连续性

**声明**: 

> **当前 MVP16 观测结果不能作为长期连续性已被验证的充分证据。**

---

### MVP14 持久化裁决

**裁决**: **Claimed but Unproven**

**理由**:
- DriveManager 无持久化机制
- 重启后状态丢失
- 宣称的 "Endogenous Drives" 不具备跨会话连续性

---

### MVP13 持久化裁决

**裁决**: **Conditionally Verified**

**理由**:
- 持久化 API 存在
- 主链知道持久化
- 但实际使用未充分验证

---

## 修复建议

### 立即修复 (P0)

1. **移除 Daily Check 中的 reset**:
```python
# 错误
def check_continuity() -> dict:
    reset_developmental_manager()  # ← 删除此行
    manager = get_developmental_manager()
```

2. **添加 Developmental 持久化**:
```python
class DevelopmentalManager:
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.state.model_dump(), f)
    
    def load(self, path: str):
        with open(path) as f:
            data = json.load(f)
            self.state = DevelopmentalState(**data)
```

3. **重新开始观测窗**: 修复后重新开始 14 天观测

---

*实验执行时间: 2026-03-12*  
*审计模式: Verification-Only*
