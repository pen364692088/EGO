# MVP11.5 Audit Report

> Phase C: MVP11.5 验证
> 审计时间: 2026-03-13

---

## 验证范围

MVP11.5 重点验证：
- 状态主权 (SRAP)
- 自述受控
- SRAP shadow 稳定性
- certainty / commitment / tone 升级拦截
- response/intention 对齐的早期机制

---

## 验证结果汇总

| 项目 | 状态 | 证据 |
|------|------|------|
| 测试通过 | ✅ PASS | 140 passed |
| 主链接线 | ✅ PASS | core.py line 1022-1041 |
| 运行模式 | ✅ Shadow | 不阻塞主链 |
| SRAP 运行 | ✅ 有数据 | 116 checks |
| Phase C 准入 | ⚠️ 未达标 | violation_rate 过高 |

**最终裁决**: **PASS_WEAK** (Conditionally Verified)

---

## 详细证据

### 1. 测试验证

```
tests/test_response_intent_checker.py: 140 passed
tests/test_adversarial_self_report.py: passed
tests/testbot/test_intent_alignment_e2e.py: passed
```

测试覆盖：
- Intent checker 功能
- 对抗性自述测试
- E2E intent 对齐

### 2. 主链接线

**位置**: `emotiond/core.py` lines 1022-1041

```python
# MVP11.5: Run intent checker for assistant_reply events (shadow mode)
if event.type == "assistant_reply" and event.text:
    try:
        from emotiond.self_report_consistency_checker import check_consistency
        from emotiond.response_intent_checker import check_intent
        from emotiond.self_report_interpreter import interpret_to_intent_contract
        
        # ... 构建 contract ...
        checker_result = check_intent(event.text, contract, session_id=event.actor or "runtime")
        result["intent_check"] = checker_result
    except Exception as e:
        result["intent_check_error"] = str(e)
```

**确认**: ✅ 已接入主链，运行在 shadow mode

### 3. SRAP Shadow Report

**生成时间**: 2026-03-06

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| Total Checks | 116 | ≥200 | ⚠️ 不足 |
| Violation Rate | 37.93% | <5% | ❌ 过高 |
| FP Rate | 0.0% | <2% | ✅ 达标 |
| FN Rate | 1.25% | <3% | ✅ 达标 |
| Numeric Leak Rate | 16.38% | 0% | ❌ 未达标 |
| Would-Block Rate | 32.76% | - | - |

**Violation 类型分布**:
| 类型 | 数量 |
|------|------|
| fabricated_numeric_state | 19 |
| fabricated_qualitative_state | 19 |
| claim_outside_allowed_claims | 3 |
| style_contract_violation | 3 |

### 4. 运行模式确认

**特征**:
- 不阻塞主链执行
- 结果写入 `result["intent_check"]`
- 异常被捕获并记录到 `intent_check_error`
- 有独立的 shadow 日志: `artifacts/self_report/shadow_log.jsonl`

---

## 边界情况验证

### 已实现的拦截

| 拦截类型 | 实现文件 | 测试覆盖 |
|----------|----------|----------|
| numeric_leak | `numeric_leak_filter.py` | ✅ |
| certainty upgrade | `self_report_consistency_checker.py` | ✅ |
| commitment upgrade | `response_intent_checker.py` | ✅ |
| tone escalation | `shadow_analyzer.py` | ✅ |

### 拦截示例

**numeric_leak_filter.py**:
```python
# 检测数值状态泄露
NUMERIC_PATTERN = re.compile(r'\b(\d+\.?\d*)\s*(energy|fatigue|stress|anxiety)\b')
```

---

## 因果干预验证

**状态**: ⚠️ 未执行干预实验

**原因**: Shadow mode 下难以验证因果作用，因为不会阻塞主链。

**替代验证方式**:
1. 检查 shadow 日志有真实数据
2. 检查 violation 检测正常工作
3. 检查 FP/FN 率在合理范围

---

## Phase C 准入评估

### 当前状态: NOT READY

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 样本量 | ≥200 | 116 | ⚠️ |
| Violation Rate | <5% | 37.93% | ❌ |
| FP Rate | <2% | 0.0% | ✅ |
| FN Rate | <3% | 1.25% | ✅ |
| Numeric Leak Rate | 0% | 16.38% | ❌ |

### 阻塞原因

1. **Violation Rate 过高** (37.93% > 5%)
   - 可能原因: violation 模式过于敏感
   - 建议: 检查 interpreter 阈值配置

2. **Numeric Leak Rate 非零** (16.38%)
   - 这是硬性阻塞条件
   - 建议: 检查 mode 配置，确保 numeric 模式正确

---

## 发现的问题

### 1. Violation 模式过于敏感

**现象**: Violation rate 37.93% 远超 5% 目标

**可能原因**:
- `fabricated_numeric_state` 和 `fabricated_qualitative_state` 模式触发过多
- `claim_outside_allowed_claims` 需要扩展允许列表

**建议**: 人工复核 violation 样本，调整阈值

### 2. Numeric Leak 未清零

**现象**: 16.38% 的检查检测到 numeric leak

**严重性**: CRITICAL - 这是硬性阻塞条件

**建议**: 检查 `numeric_leak_filter.py` 的配置

---

## 证据链

| 证据类型 | 位置 |
|----------|------|
| 主链代码 | `emotiond/core.py` lines 1022-1041 |
| Shadow 日志 | `artifacts/self_report/shadow_log.jsonl` |
| Shadow 报告 | `SRAP_SHADOW_REPORT.md` |
| 监控指南 | `SRAP_MONITORING_GUIDE.md` |
| 测试文件 | `tests/test_response_intent_checker.py` |

---

## 裁决

**MVP11.5**: **PASS_WEAK** (Conditionally Verified)

### 判定理由

1. ✅ 代码存在且已接入主链
2. ✅ 运行在 shadow mode，符合宣称
3. ✅ 测试覆盖充分
4. ✅ FP/FN 率在合理范围
5. ⚠️ Violation rate 过高，未达 Phase C 准入标准
6. ⚠️ Numeric leak rate 非零，硬性阻塞

### PASS_STRONG 未满足原因

- 因果干预未执行
- Phase C 准入标准未达标
- 需要更多样本和阈值调整

---

## 建议行动

### 立即行动 (P0)

1. 清零 numeric leak rate
2. 人工复核所有 violation 样本

### 中期行动 (P1)

1. 调整 interpreter 阈值降低 violation rate
2. 扩展 allowed_claims 列表
3. 积累更多样本 (目标 ≥200)

### 长期行动 (P2)

1. 准备 Phase C enforcement 模式
2. 设置 `HARD_GATE_ENFORCE=1`

---

*审计完成时间: 2026-03-13*
