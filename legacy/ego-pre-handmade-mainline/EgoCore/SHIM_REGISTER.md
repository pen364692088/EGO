# SHIM_REGISTER.md

> 注册日期: 2026-03-16
> 最后更新: 2026-04-27
> 目的: 登记所有过渡期 shim 实现

---

## 注册原则

1. 任何主体本体逻辑如果在 EgoCore 中存在，必须登记为 shim
2. 每个 shim 必须有明确迁移计划和到期版本
3. 迁移完成后必须删除 shim
4. 正式主链只使用 `/cycle`，其他路径都是 shim 或 fallback

---

## 当前 Shim 清单

### SHIM-001: identity_invariants.schema.json

| 字段 | 值 |
|------|-----|
| 名称 | identity_invariants.schema.json |
| 路径 | EgoCore/contracts/identity_invariants.schema.json |
| 类型 | shim (schema mirror) |
| 正式归属 | OpenEmotion/schemas/identity_invariants.schema.json |
| 为什么存在 | P1-A 开发时 OpenEmotion 尚未有正式 identity 模块 |
| 到期版本 | v1.1.0 |
| 迁移计划 | OpenEmotion 已有正式 schema，下版本删除 EgoCore 版本 |
| 删除动作 | 删除 EgoCore/contracts/identity_invariants.schema.json |

---

### SHIM-002: self_model.schema.json

| 字段 | 值 |
|------|-----|
| 名称 | self_model.schema.json |
| 路径 | EgoCore/contracts/self_model.schema.json |
| 类型 | shim (schema mirror) |
| 正式归属 | OpenEmotion/schemas/self_model.schema.json |
| 为什么存在 | P1-B 开发时 OpenEmotion 尚未有正式 self_model 模块 |
| 到期版本 | v1.1.0 |
| 迁移计划 | OpenEmotion 已有正式 schema，下版本删除 EgoCore 版本 |
| 删除动作 | 删除 EgoCore/contracts/self_model.schema.json |

---

### SHIM-003: long_term_self_summary.schema.json

| 字段 | 值 |
|------|-----|
| 名称 | long_term_self_summary.schema.json |
| 路径 | EgoCore/contracts/long_term_self_summary.schema.json |
| 类型 | shim (schema mirror) |
| 正式归属 | OpenEmotion/schemas/long_term_self_summary.schema.json |
| 为什么存在 | P1-C1 开发时 OpenEmotion 尚未有正式 summary 模块 |
| 到期版本 | v1.1.0 |
| 迁移计划 | OpenEmotion 已有正式 schema，下版本删除 EgoCore 版本 |
| 删除动作 | 删除 EgoCore/contracts/long_term_self_summary.schema.json |

---

### SHIM-004: summary_generator.py

| 字段 | 值 |
|------|-----|
| 名称 | summary_generator.py |
| 路径 | EgoCore/egocore/runtime/summary_generator.py |
| 类型 | shim (本体逻辑) |
| 正式归属 | OpenEmotion/openemotion/identity/long_term_self_summary.py |
| 为什么存在 | P1-C1 开发时 OpenEmotion 尚未有正式 summary 生成模块 |
| 到期版本 | v1.1.0 |
| 迁移计划 | OpenEmotion 已有正式生成函数，EgoCore 改为调用 OpenEmotion |
| 删除动作 | 重构 summary_generator.py 为 summary_loader.py |

---

### SHIM-005: plan_adapter.py (NEW - 2026-03-19)

| 字段 | 值 |
|------|-----|
| 名称 | plan_adapter.py |
| 路径 | EgoCore/app/integrations/openemotion/plan_adapter.py |
| 类型 | shim (旧主链组件) |
| 正式归属 | **废弃** - 不迁移，直接删除 |
| 为什么存在 | 旧 `/plan` 主链遗留，现已被 `/cycle` 替代 |
| 到期版本 | v1.1.0 |
| 迁移计划 | 不迁移，v1.1.0 直接删除 |
| 删除动作 | 删除 plan_adapter.py，确保无引用 |

---

### SHIM-006: injection_gate.py (NEW - 2026-03-19)

| 字段 | 值 |
|------|-----|
| 名称 | injection_gate.py |
| 路径 | EgoCore/app/integrations/openemotion/injection_gate.py |
| 类型 | shim (旧主链组件) |
| 正式归属 | **废弃** - 不迁移，直接删除 |
| 为什么存在 | 旧 `/plan` 主链遗留，现已被 `/cycle` 替代 |
| 到期版本 | v1.1.0 |
| 迁移计划 | 不迁移，v1.1.0 直接删除 |
| 删除动作 | 删除 injection_gate.py，确保无引用 |

---

### SHIM-007: reply_injection.py (NEW - 2026-03-19)

| 字段 | 值 |
|------|-----|
| 名称 | reply_injection.py |
| 路径 | EgoCore/app/integrations/openemotion/reply_injection.py |
| 类型 | shim (旧主链组件) |
| 正式归属 | **废弃** - 不迁移，直接删除 |
| 为什么存在 | 旧 `/plan` 主链遗留，现已被 `/cycle` 替代 |
| 到期版本 | v1.1.0 |
| 迁移计划 | 不迁移，v1.1.0 直接删除 |
| 删除动作 | 删除 reply_injection.py，确保无引用 |

---

### SHIM-008: injection_metrics.py (NEW - 2026-03-19)

| 字段 | 值 |
|------|-----|
| 名称 | injection_metrics.py |
| 路径 | EgoCore/app/integrations/openemotion/injection_metrics.py |
| 类型 | shim (旧主链组件) |
| 正式归属 | **废弃** - 不迁移，直接删除 |
| 为什么存在 | 旧 `/plan` 主链遗留，现已被 `/cycle` 替代 |
| 到期版本 | v1.1.0 |
| 迁移计划 | 不迁移，v1.1.0 直接删除 |
| 删除动作 | 删除 injection_metrics.py，确保无引用 |

---

### SHIM-009: telegram proactive visible-text send-admission quarantine (NEW - 2026-04-27)

| 字段 | 值 |
|------|-----|
| 名称 | proactive visible-text send-admission gate |
| 路径 | EgoCore/app/telegram_bot.py::drain_pending_proactive_outbox_to_telegram |
| 类型 | quarantine shim (host transport send-admission) |
| 正式归属 | EgoCore host-owned transport governance；主动可见文本 authority source 为 `runtime_v2.subject_system_v1_delivery_bridge` |
| 为什么存在 | legacy proactive outbox / pending followup 仍可能把非 current-lane 文本送到 Telegram transport；本 gate 在发送前 fail-closed quarantine，避免 legacy / unknown source 继续成为主动可见文本来源 |
| 到期版本 | v1.1.0-quarantine-closeout |
| 迁移计划 | current-lane `subject_system_v1_delivery_bridge` 成为唯一 proactive outbox 生产者后，删除 legacy scheduler 可发送路径，并把 transport gate 收敛为普通 contract assertion 或移除 |
| 删除前提 | 1) legacy `runtime_v2.initiative_arbiter` / unknown proactive outbox 不能再进入 sendable queue；2) pending/outbox replay 样本均带 current-lane delivery record；3) focused tests 与 live recheck 均证明非 current-lane source 不再到达 transport send path |
| 删除动作 | 删除 `drain_pending_proactive_outbox_to_telegram` 内 quarantine admission shim，并保留/迁移必要的普通 contract regression tests |

---

## 非 Shim 保留项

以下实现保留在 EgoCore，不是 shim：

| 名称 | 路径 | 类型 |
|------|------|------|
| subject_adapter.py | app/openemotion/ | 正式主链组件 (cycle 入口) |
| identity_guard.py | egocore/runtime/ | host-side loader |
| self_model_manager.py | egocore/runtime/ | host-side loader |
| self_restorer.py | egocore/runtime/ | restore orchestration |
| context_injector.py | egocore/runtime/ | context injection |
| adapter.py | app/integrations/openemotion/ | adapter (保留，用于其他目的) |
| client.py | app/integrations/openemotion/ | HTTP client (保留，用于 /cycle) |
| fallback.py | app/integrations/openemotion/ | fallback 处理 (保留) |
| event_mirror.py | app/integrations/openemotion/ | 事件镜像 (保留) |
| types.py | app/integrations/openemotion/ | 类型定义 (保留) |
| manager.py | app/integrations/openemotion/ | 管理器 (保留) |

---

## 正式主链定义

```
User/Telegram → EgoCore ingress/runtime → OpenEmotion /cycle → EgoCore 决策与执行 → 结果回流 OpenEmotion → Telegram 回复
```

**唯一正式主体入口**: `subject_adapter.cycle()`

**Fallback 入口**: `subject_adapter.interpret()` (仅在 OpenEmotion 不可用时)

**禁止**: 任何与 `/cycle` 平级的主体决策源

---

## 统计

- 总 shim 数: 9
- 需删除 shim: 8 (全部在 v1.1.0 删除)
- transport quarantine shim: 1 (SHIM-009，待 legacy proactive sendable path 清退后删除)
- 保留非 shim: 11

---

## v1.1.0 行动项

v1.1.0 必须完成：

1. 删除 SHIM-001~004 (schema 文件)
2. 重构 SHIM-004 (summary_generator.py)
3. 删除 SHIM-005~008 (plan-injection 相关)
4. 清理 integrations/openemotion/ 目录
5. 确保所有主链只使用 `/cycle`

---

## 参考

- DUAL_REPO_MAINLINE.md (正式主链定义)
- PROGRAM_STATE_UNIFIED.yaml (权威状态)
