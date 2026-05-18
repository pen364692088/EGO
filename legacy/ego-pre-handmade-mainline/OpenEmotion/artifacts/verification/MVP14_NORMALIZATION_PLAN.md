# MVP14 Normalization Plan

> 目标：添加归一化层降低 Legacy vs New 决策偏移
> 时间：2026-03-13

---

## 1. 问题分析

### 1.1 当前差异

| 字段映射 | Legacy 默认值 | New 默认值 | 差异 |
|----------|---------------|------------|------|
| energy→stability | 0.75 | 0.40 | 0.35 |
| safety→verification | 0.75 | 0.30 | 0.45 |

### 1.2 影响

- **排序变化率**: 100%
- **决策偏移**: 完全不同的优先级导向
- **风险评估**: 高风险

---

## 2. 归一化策略

### 2.1 方案 A: 调整 New 默认值 (推荐)

**目标**: 让 New 默认值匹配 Legacy 语义

```python
# Before (New API defaults)
stability: 0.40
verification: 0.30

# After (normalized to match legacy)
stability: 0.75  # matches energy
verification: 0.75  # matches safety
```

**优点**:
- 最小改动
- 直接解决差异
- 无需复杂映射

**缺点**:
- 可能影响新 API 的其他使用者

### 2.2 方案 B: 添加转换层

在 adapter 中添加语义转换：

```python
class NormalizationLayer:
    def legacy_to_new(self, legacy_value: float, field: str) -> float:
        if field == "energy":
            # energy 是消耗性指标，stability 是稳定性指标
            # 转换: 高 energy = 高 stability
            return legacy_value
        elif field == "safety":
            # safety 和 verification 语义相近
            return legacy_value
        ...
```

**优点**:
- 不修改底层
- 可精细控制

**缺点**:
- 增加复杂度
- 维护负担

### 2.3 选中方案: 方案 A (调整默认值)

**原因**:
1. 最简单直接
2. 差异源于初始化，非语义冲突
3. 新 API 尚未有其他使用者

---

## 3. 实现计划

### 3.1 修改位置

**文件**: `emotiond/drives/manager.py`

```python
def _initialize_default_drives(self) -> None:
    default_drives = [
        # Before: (DriveType.STABILITY, 0.4, "...")
        # After:
        (DriveType.STABILITY, 0.75, "System stability maintenance"),  # match legacy energy
        (DriveType.COHERENCE, 0.25, "Internal consistency maintenance"),  # match legacy uncertainty (inverted)
        (DriveType.COMPLETION, 0.5, "Goal completion pressure"),  # match legacy social
        # Before: (DriveType.VERIFICATION, 0.3, "...")
        # After:
        (DriveType.VERIFICATION, 0.75, "State verification drive"),  # match legacy safety
        (DriveType.REPAIR, 0.15, "Self-repair drive"),  # match legacy fatigue
        ...
    ]
```

### 3.2 新增指标

```python
class DiffMetrics:
    # 原有指标
    field_diff_rates: Dict[str, float]
    avg_field_diffs: Dict[str, float]
    
    # 新增指标
    rank_change_rate: float  # 排序变化率
    top1_agreement_rate: float  # top-1 一致率
    high_risk_avg_diff: float  # 高风险字段平均差异
```

---

## 4. 目标阈值

| 指标 | 当前值 | 目标值 | 切流阈值 |
|------|--------|--------|----------|
| 排序变化率 | 100% | <20% | <10% |
| top-1 一致率 | 0% | >80% | >90% |
| 高风险字段平均差异 | 0.40 | <0.10 | <0.05 |

---

## 5. 验证步骤

1. 修改默认值
2. 运行 200+ 样本 diff 分析
3. 检查指标是否达标
4. 如果未达标，迭代调整

---

## 6. 回滚方案

```bash
# 回滚默认值修改
git checkout HEAD~1 -- emotiond/drives/manager.py

# 禁用归一化
export ENABLE_MVP14_NORMALIZATION=false
```

---

*创建时间: 2026-03-13*
