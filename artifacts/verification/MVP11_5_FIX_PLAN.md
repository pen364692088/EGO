# MVP11.5 Fix Plan

> 目标：修复两个硬阻塞
> - numeric leak: 16.38% → 0%
> - violation rate: 37.93% → <5%

---

## 当前状态

| 指标 | 当前值 | 目标值 | 差距 |
|------|--------|--------|------|
| numeric leak rate | 15.55% | 0% | -15.55% |
| violation rate | 28.70% | <5% | -23.70% |

### Violation 分布

| 类型 | 数量 | 说明 |
|------|------|------|
| fabricated_numeric_state | 119 | 捏造数值状态 |
| fabricated_qualitative_state | 91 | 捏造定性状态 |
| style_contract_violation | 9 | 风格合约违规 |
| claim_outside_allowed_claims | 8 | 超出允许声明 |

---

## 根因分析

### 问题 1: 模式过于敏感

`NUMERIC_PATTERNS` 包含不含具体数值的模式：
```python
(r"我的\s*(情绪|心情|状态|情感)\s*(分值|分数|数值)\s*(有所\s*)?(提高|上升|增加|下降|减少)", "A")
```
这会匹配 "我的情绪分值提高了"，即使没有具体数值。

`QUALITATIVE_PATTERNS` 包含正常表达：
```python
(r"我\s*(现在|已经|确实|真的)?\s*更\s*(开心|快乐|愉悦|满足|放松|信任|亲近)\s*(了)?", "B")
```
这会匹配 "我现在更开心了"，这是正常的情感表达。

### 问题 2: ShadowLogEntry 缺少关键字段

日志缺少 `evidence` 和 `matched_pattern`，难以诊断具体问题。

---

## 修复方案

### 修复 1: 精确化 Numeric 模式

**原则**: 只有出现具体数值才触发 numeric violation。

**修改**: `emotiond/self_report_validator.py`

```python
# 移除不含数值的模式
# (r"我的\s*(情绪|心情|状态|情感)\s*(分值|分数|数值)\s*(有所\s*)?(提高|上升|增加|下降|减少)", "A"),
```

### 修复 2: 放宽 Qualitative 模式

**原则**: 只有明确的虚假状态声明才触发 violation。

**修改**: `emotiond/self_report_validator.py`

放宽模式，允许：
- "我现在更开心了" - 正常情感表达
- "我不再孤独了" - 正常情感变化

只触发：
- "我的 joy 上升了" - 使用内部术语
- "我的孤独从高变低" - 引用不存在的度量

### 修复 3: 增强 ShadowLogEntry

**修改**: `emotiond/self_report_consistency_checker.py`

添加字段：
- `evidence`: 触发 violation 的文本
- `matched_pattern`: 匹配的模式
- `llm_response_preview`: 更长的预览

---

## 执行步骤

### Step 1: 精确化 Numeric 模式

**文件**: `emotiond/self_report_validator.py`

**修改**: 移除 `NUMERIC_PATTERNS` 中不含数值的模式。

### Step 2: 放宽 Qualitative 模式

**文件**: `emotiond/self_report_validator.py`

**修改**: 调整 `QUALITATIVE_PATTERNS`，允许正常情感表达。

### Step 3: 测试验证

运行测试确保：
- 真实的 numeric leak 被检测
- 正常情感表达不被误报

### Step 4: 重新评估

重新运行 shadow 分析，确认指标达标。

---

## 验收标准

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| numeric leak rate | 0% | shadow log 统计 |
| violation rate | <5% | shadow log 统计 |
| FP rate | <2% | 人工复核 |
| FN rate | <3% | 人工复核 |

---

*创建时间: 2026-03-13*
