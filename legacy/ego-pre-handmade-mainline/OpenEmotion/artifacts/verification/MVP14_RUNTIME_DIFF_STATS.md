# MVP14 Runtime Diff Statistics Report

> 基于真实运行数据的 Legacy vs New 差异分析
> 时间：2026-03-13
> 样本数：50

---

## 1. 执行摘要

| 指标 | 结果 | 状态 |
|------|------|------|
| 总样本数 | 50 | - |
| 高差异字段数 | 2/5 | ⚠️ |
| 平均排序变化率 | 100% | ⚠️ HIGH |
| 最大差异字段 | safety→verification | 0.45 |

---

## 2. 字段差异详情

### 2.1 差异率 (>0.1 阈值)

| 字段映射 | 差异率 | 平均差异 | 状态 |
|----------|--------|----------|------|
| energy→stability | 100.00% | 0.350 | ⚠️ HIGH |
| uncertainty→coherence | 0.00% | 0.050 | ✅ OK |
| social→completion | 0.00% | 0.000 | ✅ OK |
| safety→verification | 100.00% | 0.450 | ⚠️ HIGH |
| fatigue→repair | 0.00% | 0.050 | ✅ OK |

### 2.2 分析

**高差异字段**:
1. **energy→stability** (差异 0.35)
   - Legacy energy 默认值: 0.75
   - New stability 默认值: 0.40
   - 差异原因: 语义不同 + 初始值不同

2. **safety→verification** (差异 0.45)
   - Legacy safety 默认值: 0.75
   - New verification 默认值: 0.30
   - 差异原因: 语义不同 + 初始值不同

**低差异字段**:
- uncertainty→coherence: 语义相近，差异小
- social→completion: 语义相近
- fatigue→repair: 语义相近

---

## 3. 排序影响分析

### 3.1 排序变化率: 100%

**原因**: 高差异字段导致优先级完全不同。

**Legacy 排序 (按值降序)**:
```
1. energy (0.75)
2. safety (0.75)
3. social (0.50)
4. uncertainty (0.25)
5. fatigue (0.15)
```

**New 排序 (按值降序)**:
```
1. completion (0.50)
2. stability (0.40)
3. coherence (0.30)
4. verification (0.30)
5. repair (0.20)
```

**影响**:
- Legacy: energy 和 safety 最高优先
- New: completion 和 stability 最高优先
- 完全不同的行为导向

---

## 4. Top Diff Patterns

| Pattern | 出现次数 | 出现率 |
|---------|----------|--------|
| safety→verification: 0.450 | 50 | 100% |

**解读**: safety→verification 是最显著的差异模式，在所有样本中都出现。

---

## 5. Plan 影响

### 5.1 对 Plan 生成的影响

由于排序变化 100%，plan 生成可能受影响：

| 方面 | Legacy | New | 差异 |
|------|--------|-----|------|
| 优先恢复 | energy, safety | completion, stability | 完全不同 |
| 风险规避 | 基于 energy | 基于 stability | 不同 |
| 行动建议 | 恢复能量 | 完成目标 | 不同 |

### 5.2 风险评估

| 风险级别 | 描述 | 评估 |
|----------|------|------|
| 接受 | uncertainty→coherence 差异 0.05 | ✅ 可接受 |
| 接受 | fatigue→repair 差异 0.05 | ✅ 可接受 |
| 需关注 | energy→stability 差异 0.35 | ⚠️ 需适配 |
| 高风险 | safety→verification 差异 0.45 | ❌ 需修复 |

---

## 6. 建议行动

### 6.1 立即行动

1. **归一化映射**
   - 调整 New 默认值以匹配 Legacy
   - 或创建语义转换层

2. **字段对齐**
   - 考虑将 stability 默认值调整为 0.75
   - 考虑将 verification 默认值调整为 0.75

### 6.2 中期行动

1. **添加对比日志**
   - 在运行时记录两种实现的差异
   - 设置告警阈值

2. **A/B 测试**
   - 对比两种实现的行为效果
   - 收集用户反馈

---

## 7. 结论

### 状态: ⚠️ 需要适配

**发现**:
- 2/5 字段差异 >0.1
- 排序变化率 100%
- 主要问题：语义映射 + 默认值差异

**建议**:
- 保持 dual-run 模式
- 添加归一化层
- 逐步对齐默认值

---

## 8. 回滚建议

当前状态不建议切换到 New API，原因：
1. 排序变化率 100% 会导致行为完全不同
2. 高差异字段影响核心决策

**建议**:
- 继续收集数据
- 实现归一化层后再评估

---

*生成时间: 2026-03-13*
*样本数: 50*
*脚本: tools/mvp14_runtime_diff_stats.py*
