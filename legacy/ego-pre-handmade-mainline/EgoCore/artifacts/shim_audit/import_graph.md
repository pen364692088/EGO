# Shim Import Graph - W2 审计

> 审计时间: 2026-03-19
> 审计者: CEO agent

---

## 静态引用检查

### 检查方法

```bash
# 对每个 shim 组件执行
grep -r "component_name" app/ --include="*.py" | grep -v "__pycache__" | grep "import\|from"
```

---

## SHIM-001~003: Schema Mirrors

### identity_invariants.schema.json

```bash
grep -r "identity_invariants.schema" app/ --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

### self_model.schema.json

```bash
grep -r "self_model.schema" app/ --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

### long_term_self_summary.schema.json

```bash
grep -r "long_term_self_summary.schema" app/ --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

---

## SHIM-004: summary_generator.py

```bash
grep -r "summary_generator" app/ --include="*.py"
# 结果: 无引用
```

**状态**: 可安全重构/删除 ✅

---

## SHIM-005~008: plan-injection 组件

### plan_adapter.py

```bash
grep -r "plan_adapter\|PlanAdapter" app/runtime app/handlers --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

### injection_gate.py

```bash
grep -r "injection_gate\|InjectionGate" app/runtime app/handlers --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

### reply_injection.py

```bash
grep -r "reply_injection" app/runtime app/handlers --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

### injection_metrics.py

```bash
grep -r "injection_metrics" app/runtime app/handlers --include="*.py"
# 结果: 无引用
```

**状态**: 可安全删除 ✅

---

## 引用图总结

```
正式主链:
  Telegram → semantic_router → social_chat_handler → subject_adapter.cycle() → OpenEmotion /cycle

Shim 引用:
  (无 - 所有 shim 均未被正式主链引用)
```

---

## 删除就绪状态

| Shim ID | 静态引用 | 运行时引用 | 删除就绪 |
|---------|----------|------------|----------|
| SHIM-001 | ❌ | ❌ | ✅ |
| SHIM-002 | ❌ | ❌ | ✅ |
| SHIM-003 | ❌ | ❌ | ✅ |
| SHIM-004 | ❌ | ❌ | ✅ |
| SHIM-005 | ❌ | ❌ | ✅ |
| SHIM-006 | ❌ | ❌ | ✅ |
| SHIM-007 | ❌ | ❌ | ✅ |
| SHIM-008 | ❌ | ❌ | ✅ |

---

## 结论

**所有 8 个 shim 静态引用检查通过** ✅

**无代码依赖阻止删除** ✅

---

## 前置条件检查

- [x] 静态引用检查通过
- [x] 运行时路径检查通过
- [ ] C3 观察期通过
- [ ] fallback 行为确认
- [ ] 创建删除前 tag
