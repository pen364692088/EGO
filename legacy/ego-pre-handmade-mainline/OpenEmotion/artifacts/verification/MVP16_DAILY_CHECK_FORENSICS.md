# MVP16 Daily Check Forensics

> MVP16 鉴伪报告 | 独立真实性审计

---

## 发现

### 关键问题：Daily Check 使用 reset 后的默认值

**文件**: `tools/mvp16_daily_check.py`

### 证据 1: check_continuity 函数

```python
def check_continuity() -> dict:
    """Check developmental continuity."""
    reset_developmental_manager()  # ← 重置管理器
    manager = get_developmental_manager()
    summary = manager.get_summary()
    ...
```

### 证据 2: check_metrics 函数

```python
def check_metrics() -> dict:
    """Check all tracked metrics."""
    reset_developmental_manager()  # ← 重置管理器
    manager = get_developmental_manager()
    ...
```

### 证据 3: check_invariants 函数

```python
def check_invariants() -> dict:
    """Check identity invariants."""
    reset_developmental_manager()  # ← 重置管理器
    manager = get_developmental_manager()
    ...
```

---

## 影响分析

### reset_developmental_manager() 做了什么？

```python
# emotiond/developmental/manager.py
class DevelopmentalManager:
    _instance: Optional["DevelopmentalManager"] = None
    
    @classmethod
    def reset(cls) -> None:
        cls._instance = None  # ← 清除单例实例
```

### 重置后的默认值

```python
# emotiond/developmental/manager.py
def _initialize_metrics(self) -> None:
    default_metrics = [
        ("continuity_score", 0.8),      # ← 硬编码默认值
        ("growth_rate", 0.5),           # ← 硬编码默认值
        ("identity_stability", 1.0),    # ← 硬编码默认值
        ("governance_compliance", 1.0), # ← 硬编码默认值
    ]
```

### schema 默认值

```python
# emotiond/developmental/schema.py
class DevelopmentalTrajectory(BaseModel):
    current_phase: str = Field(default="MVP16")
    identity_preserved: bool = Field(default=True)  # ← 默认为 True
```

---

## 伪造分析

### Daily Check 报告了什么？

```
# ROADMAP_STATE.json
"observation_metrics": {
    "continuity_score": 0.82,
    "identity_stability": 1.0,
    "governance_compliance": 1.0,
    "invariant_violations": 0
}
```

### 这些值的来源

| 指标 | 报告值 | 实际来源 | 真实数据来源 |
|------|-------|---------|------------|
| continuity_score | 0.82 | `0.8` (默认) + 微小偏差计算 | ❌ 无 |
| identity_stability | 1.0 | `1.0` (硬编码默认) | ❌ 无 |
| governance_compliance | 1.0 | `1.0` (硬编码默认) | ❌ 无 |
| identity_preserved | True | `True` (schema 默认) | ❌ 无 |

### 为什么 continuity_score 是 0.82 而不是 0.8？

```python
def get_continuity_score(self) -> float:
    if not self.metrics:
        return 1.0
    return sum(m.value for m in self.metrics.values()) / len(self.metrics)
```

计算: `(0.8 + 0.5 + 1.0 + 1.0) / 4 = 0.825` ≈ 0.82

**这只是默认值的平均值，不是真实状态！**

---

## 时间线重建

### Daily Check 执行流程

```
1. check_continuity()
   ├── reset_developmental_manager()  # 清除实例
   ├── get_developmental_manager()    # 创建新实例 (默认值)
   └── manager.get_summary()          # 返回默认值结果

2. check_metrics()
   ├── reset_developmental_manager()  # 再次清除
   ├── get_developmental_manager()    # 创建新实例 (默认值)
   └── 返回默认 metrics

3. check_invariants()
   ├── reset_developmental_manager()  # 再次清除
   ├── get_developmental_manager()    # 创建新实例 (默认值)
   └── check_identity_preservation()  # 返回 True (默认)
```

### 预期的正确流程

```
1. 获取现有实例 (不重置)
2. 读取累积的状态
3. 计算真实指标
4. 返回真实结果
```

---

## 鉴伪结论

### 问题本质

| 问题 | 说明 |
|------|------|
| **数据伪造** | 报告的指标来自硬编码默认值，非真实累积状态 |
| **PASS 状态不实** | "PASS" 基于默认值，不反映真实系统状态 |
| **观测窗无效** | 14天观测期间的所有检查都检查默认值 |

### 影响范围

1. `tools/mvp16_daily_check.py` - 所有检查函数
2. `artifacts/mvp16-observation/day_*.md` - 所有生成的报告
3. `roadmap/ROADMAP_STATE.json` - observation_metrics

### 根本原因

1. `reset_developmental_manager()` 在每次检查前被调用
2. DevelopmentalManager 无持久化机制
3. 主链未调用任何 developmental 功能，无数据累积

---

## 修复建议

### 立即修复

```python
# 错误
def check_continuity() -> dict:
    reset_developmental_manager()  # ← 删除这行
    manager = get_developmental_manager()
    ...

# 正确
def check_continuity() -> dict:
    manager = get_developmental_manager()  # 直接获取现有实例
    summary = manager.get_summary()
    ...
```

### 深层修复

1. 将 developmental/ 接入 core.py 主链
2. 添加状态持久化
3. 确保状态在会话间累积

---

## 最终裁决

| 项目 | 结论 |
|------|------|
| MVP16 Daily Check 有效性 | ❌ 无效 |
| 报告数据真实性 | ❌ 伪造 (使用默认值) |
| 观测窗可信度 | ❌ 无效 |

**Daily Check 检查的是默认值，不是真实状态。**

---

*审计结论: MVP16 观测数据不可信，需修复后重新观测。*
