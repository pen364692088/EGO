# MVP14 Post-Normalization Diff Report

> 归一化后 Legacy vs New 差异分析
> 时间：2026-03-13
> 样本数：200

---

## 1. 归一化措施

### 1.1 默认值调整

| 字段映射 | Legacy | 调整前 New | 调整后 New |
|----------|--------|------------|------------|
| energy→stability | 0.75 | 0.40 | **0.75** |
| uncertainty→coherence | 0.25 | 0.30 | **0.25** |
| social→completion | 0.50 | 0.50 | 0.50 |
| safety→verification | 0.75 | 0.30 | **0.75** |
| fatigue→repair | 0.15 | 0.20 | **0.15** |

**修改文件**: `emotiond/drives/manager.py` - `_initialize_default_drives()`

---

## 2. 归一化后差异统计

### 2.1 字段差异

| 字段映射 | 差异率 (>0.1) | 平均差异 | 状态 |
|----------|---------------|----------|------|
| energy→stability | 0.00% | 0.000 | ✅ OK |
| uncertainty→coherence | 0.00% | 0.000 | ✅ OK |
| social→completion | 0.00% | 0.000 | ✅ OK |
| safety→verification | 0.00% | 0.000 | ✅ OK |
| fatigue→repair | 0.00% | 0.000 | ✅ OK |

**结论**: 所有字段完全一致

---

## 3. 决策偏移指标

### 3.1 归一化前 vs 后对比

| 指标 | 归一化前 | 归一化后 | 改善 |
|------|----------|----------|------|
| 排序变化率 | 100% | **0%** | -100% |
| Top-1 一致率 | 0% | **100%** | +100% |
| 高风险字段平均差异 | 0.40 | **0.00** | -0.40 |

### 3.2 达标情况

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 排序变化率 | <10% | 0% | ✅ PASS |
| Top-1 一致率 | >90% | 100% | ✅ PASS |
| 高风险字段差异 | <0.05 | 0.00 | ✅ PASS |

---

## 4. 排序验证

### 4.1 Legacy 排序 (降序)

```
1. energy (0.75)
2. safety (0.75)
3. social (0.50)
4. uncertainty (0.25)
5. fatigue (0.15)
```

### 4.2 New 排序 (降序, 仅比较共同字段)

```
1. stability (0.75) ← energy
2. verification (0.75) ← safety
3. completion (0.50) ← social
4. coherence (0.25) ← uncertainty
5. repair (0.15) ← fatigue
```

**结论**: 排序完全一致

---

## 5. 结论

### 5.1 归一化效果

✅ **完全成功**

- 所有字段差异为 0
- 排序变化率从 100% 降至 0%
- Top-1 一致率从 0% 升至 100%
- 高风险字段差异从 0.40 降至 0.00

### 5.2 切流判定

**状态**: ✅ **CUTOVER READY**

所有指标达到切流阈值：
- 排序变化率: 0% < 10% ✅
- Top-1 一致率: 100% > 90% ✅
- 高风险差异: 0.00 < 0.05 ✅

---

## 6. 样本详情

| 参数 | 值 |
|------|-----|
| 样本数 | 200 |
| 数据文件 | `artifacts/mvp14/runtime_diff_stats.json` |
| 分析脚本 | `tools/mvp14_runtime_diff_stats.py` |

---

*生成时间: 2026-03-13*
