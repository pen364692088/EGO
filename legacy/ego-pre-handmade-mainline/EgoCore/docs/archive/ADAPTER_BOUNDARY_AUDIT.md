# Adapter Boundary Audit Report

> 日期: 2026-03-16
> 审计对象: `egocore/adapters/openemotion_adapter.py`

---

## 1. 审计结论

**状态: CONDITIONAL PASS**

Adapter 的核心职责是正确的（转换、传递、隔离、降级），但 MockBackend 存在越界风险。

---

## 2. Adapter 允许做的事 ✅

| 职责 | 实现状态 | 说明 |
|------|---------|------|
| Schema 验证 | ✅ 已实现 | `_parse_and_validate_input` |
| 字段转换 | ✅ 已实现 | `EventInput.from_dict`, `OpenEmotionOutput.to_dict` |
| 版本检查 | ⚠️ 需集成 | 已创建 `contract_guard.py`，需接入 |
| 运行时包装 | ✅ 已实现 | `OpenEmotionAdapter.process_event` |
| 错误分级 | ✅ 已实现 | `ValidationError`, `ConnectionError`, `TimeoutError` |
| 统计追踪 | ✅ 已实现 | `get_stats`, `reset_stats` |
| 降级输出 | ✅ 已实现 | `_create_error_output` |

---

## 3. Adapter 禁止做的事 ❌

| 禁止行为 | 检查结果 | 说明 |
|---------|---------|------|
| Appraisal 推断 | ⚠️ 风险 | MockBackend._default_response 生成 appraisal_state_delta |
| Identity 改写 | ✅ 无违规 | adapter 不修改 identity |
| Memory consolidation | ✅ 无违规 | adapter 不处理 memory |
| Reflection 生成 | ✅ 无违规 | adapter 不生成 reflection |
| 主体结论替代 | ✅ 无违规 | adapter 不替代 OpenEmotion 决策 |

---

## 4. MockBackend 边界问题分析

### 4.1 问题代码

```python
# openemotion_adapter.py:207-234
def _default_response(self, event: EventInput) -> OpenEmotionOutput:
    """默认响应生成器"""
    # ⚠️ 问题：基于事件类型推断 appraisal
    valence = 0.0
    if event.event_type == "user_message":
        valence = 0.2
    elif event.event_type == "task_completed":
        valence = 0.5
    elif event.event_type == "task_failed":
        valence = -0.3

    return OpenEmotionOutput(
        # ...
        appraisal_state_delta={...},  # ⚠️ 主体层决策
        policy_hint={...},            # ⚠️ 主体层决策
        response_tendency={...},      # ⚠️ 主体层决策
    )
```

### 4.2 风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| Mock 数据冒充主体决策 | 中 | 测试时可能误认为这是真实行为 |
| 边界模糊 | 低 | 已明确这是 Mock，不是生产逻辑 |
| 维护负担 | 低 | MockBackend 是临时的测试替身 |

### 4.3 解决方案

**方案 A（已采用）：外部注入响应生成器**

```python
# 允许外部提供响应生成器
backend = MockBackend(response_generator=custom_generator)
```

这允许测试代码控制 mock 响应，adapter 不再自己生成主体层决策。

**方案 B：简化 Mock 响应**

```python
def _default_response(self, event: EventInput) -> OpenEmotionOutput:
    # 只返回最小必要字段，不生成主体层决策
    return OpenEmotionOutput(
        output_id=f"out_mock_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.utcnow().isoformat() + "Z",
        event_id_ref=event.event_id,
        confidence_metadata={"overall_confidence": 0.0, "mock": True},
    )
```

---

## 5. 边界断言测试

创建 `test_adapter_boundary.py` 验证 adapter 不越界。

---

## 6. 结论与建议

### 6.1 当前结论

- **Adapter 核心职责正确**：转换、传递、隔离、降级
- **MockBackend 存在边界风险**：但已通过外部注入方式缓解
- **建议监控**：定期审计新增逻辑

### 6.2 强制判定

若 adapter 中存在以下行为，本审计直接判定失败：

- [ ] 替 OpenEmotion 生成主体解释
- [ ] 替 OpenEmotion 生成关系解释
- [ ] 替 OpenEmotion 生成策略候选
- [ ] 在非 mock 模式下生成 appraisal/policy_hint

当前状态：**PASS**

---

## 7. 后续审计频率

- 每次新增 adapter 逻辑时
- 每次修改 MockBackend 时
- 每次接入新 OpenEmotion 版本时
