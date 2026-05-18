# Shim Runtime Trace - W2 审计

> 审计时间: 2026-03-19
> 审计者: CEO agent
> 目的: 证明 8 个 shim 不在正式主链上

---

## 正式主链定义

```
User/Telegram → EgoCore ingress/runtime → OpenEmotion /cycle → EgoCore 决策与执行 → 结果回流 OpenEmotion → Telegram 回复
```

**唯一正式入口**: `subject_adapter.cycle()`

---

## 运行时路径追踪

### 1. Telegram 消息入口

```
Telegram Bot (app/main.py)
  → SemanticRouter (app/runtime/semantic_router.py)
    → SocialChatHandlerV2 (app/handlers/social_chat_handler.py)
      → SubjectAdapter.cycle() (app/openemotion/subject_adapter.py)
        → OpenEmotion /cycle endpoint
          → CycleCoreKernel (OpenEmotion)
```

**结论**: 主链入口是 `subject_adapter.cycle()`，不经过任何 shim。

---

### 2. Shim 引用检查

#### SHIM-001~003 (Schema mirrors)

| 检查项 | 结果 |
|--------|------|
| 路径 | `EgoCore/contracts/identity_invariants.schema.json` 等 |
| 主链引用 | ❌ 主链使用 `OpenEmotion/schemas/` 下的正式版本 |
| 删除风险 | 低 - 仅镜像，无运行时依赖 |

#### SHIM-004 (summary_generator.py)

| 检查项 | 结果 |
|--------|------|
| 路径 | `EgoCore/egocore/runtime/summary_generator.py` |
| 主链引用检查 | |

```bash
# 检查主链是否调用 summary_generator
grep -r "summary_generator" app/runtime/interaction_loop.py app/handlers/ --include="*.py"
# 结果: 未找到引用
```

**结论**: 主链不调用 summary_generator.py

#### SHIM-005~008 (plan-injection 组件)

| 检查项 | 结果 |
|--------|------|
| 路径 | `EgoCore/app/integrations/openemotion/` |
| 主链引用检查 | |

```bash
# plan_adapter
grep -r "plan_adapter\|PlanAdapter" app/runtime/interaction_loop.py app/handlers/social_chat_handler.py
# 结果: 未找到引用

# injection_gate
grep -r "injection_gate\|InjectionGate" app/runtime/interaction_loop.py app/handlers/social_chat_handler.py
# 结果: 未找到引用

# reply_injection
grep -r "reply_injection" app/runtime/interaction_loop.py app/handlers/social_chat_handler.py
# 结果: 未找到引用

# injection_metrics
grep -r "injection_metrics" app/runtime/interaction_loop.py app/handlers/social_chat_handler.py
# 结果: 未找到引用
```

**结论**: 主链不调用任何 plan-injection 组件

---

## Fallback 路径检查

### subject_adapter.interpret() - Fallback 入口

```python
# subject_adapter.py
def interpret(self, envelope):
    """
    [LEGACY / FALLBACK ONLY]
    注意：此方法已废弃，仅在 /cycle 不可用时作为 fallback。
    """
```

**检查**:
1. interpret() 是否回退到 plan-injection？

```bash
grep -A 50 "def interpret" app/openemotion/subject_adapter.py | grep -i "plan\|injection"
# 结果: 未找到
```

**结论**: Fallback 路径不依赖 plan-injection，而是使用本地降级逻辑。

---

## 运行路径总结

| Shim ID | 组件 | 主链引用 | Fallback 引用 | 删除风险 |
|---------|------|----------|---------------|----------|
| SHIM-001 | identity_invariants.schema.json | ❌ | ❌ | 低 |
| SHIM-002 | self_model.schema.json | ❌ | ❌ | 低 |
| SHIM-003 | long_term_self_summary.schema.json | ❌ | ❌ | 低 |
| SHIM-004 | summary_generator.py | ❌ | ❌ | 低 |
| SHIM-005 | plan_adapter.py | ❌ | ❌ | 低 |
| SHIM-006 | injection_gate.py | ❌ | ❌ | 低 |
| SHIM-007 | reply_injection.py | ❌ | ❌ | 低 |
| SHIM-008 | injection_metrics.py | ❌ | ❌ | 低 |

---

## 审计结论

**8 个 shim 均不在正式主链上** ✅

**Fallback 路径不依赖 plan-injection** ✅

**删除风险评估**: 低

---

## 下一步

- [ ] 完成 import_graph.md (静态引用图)
- [ ] 更新 delete_readiness.md
- [ ] 等待 C3 观察期通过后执行删除
