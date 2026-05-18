# Shim Delete Readiness Check

> 审计时间: 2026-03-19
> 审计者: CEO agent
> 状态: 审计完成，等待观察期通过

---

## 审计结论

**所有 8 个 shim 均不在正式主链上** ✅

**删除风险评估**: 低

---

## Shim 清单与状态

| ID | 名称 | 类型 | 静态引用 | 运行时引用 | 删除就绪 |
|----|------|------|----------|------------|----------|
| SHIM-001 | identity_invariants.schema.json | schema mirror | ❌ | ❌ | ✅ |
| SHIM-002 | self_model.schema.json | schema mirror | ❌ | ❌ | ✅ |
| SHIM-003 | long_term_self_summary.schema.json | schema mirror | ❌ | ❌ | ✅ |
| SHIM-004 | summary_generator.py | 本体逻辑 | ❌ | ❌ | ✅ |
| SHIM-005 | plan_adapter.py | 旧主链组件 | ❌ | ❌ | ✅ |
| SHIM-006 | injection_gate.py | 旧主链组件 | ❌ | ❌ | ✅ |
| SHIM-007 | reply_injection.py | 旧主链组件 | ❌ | ❌ | ✅ |
| SHIM-008 | injection_metrics.py | 旧主链组件 | ❌ | ❌ | ✅ |

---

## 审计证据

| 文档 | 路径 | 状态 |
|------|------|------|
| runtime_trace.md | artifacts/shim_audit/ | ✅ 已完成 |
| import_graph.md | artifacts/shim_audit/ | ✅ 已完成 |

---

## 删除前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| W3 真相源对齐 | ✅ | ledger_version: 14, 8 shims |
| 静态引用检查 | ✅ | 无代码依赖 |
| 运行时路径检查 | ✅ | 不在主链上 |
| C3 观察期通过 | ⏳ | Day 01 完成，Day 02-07 待观察 |
| Fallback 行为确认 | ✅ | 不依赖 plan-injection |
| 删除前 tag | ⏳ | 等待观察期通过后创建 |

---

## 删除执行计划 (v1.1.0)

### 阶段 1: Schema 删除

```bash
rm EgoCore/contracts/identity_invariants.schema.json
rm EgoCore/contracts/self_model.schema.json
rm EgoCore/contracts/long_term_self_summary.schema.json
```

### 阶段 2: plan-injection 清理

```bash
rm EgoCore/app/integrations/openemotion/plan_adapter.py
rm EgoCore/app/integrations/openemotion/injection_gate.py
rm EgoCore/app/integrations/openemotion/reply_injection.py
rm EgoCore/app/integrations/openemotion/injection_metrics.py
```

### 阶段 3: summary_generator 重构

```bash
# 重构为 summary_loader.py
# 改为调用 OpenEmotion 正式模块
```

### 阶段 4: 验证

```bash
# 运行回归测试
python -m pytest tests/ -v

# Telegram 真实回归
# 观察主链稳定性
```

---

## 当前状态

**W2 Shim 审计: 完成** ✅

**等待**: C3 观察期通过后执行删除
