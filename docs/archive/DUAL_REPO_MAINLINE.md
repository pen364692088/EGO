# DUAL_REPO_MAINLINE.md - 双仓正式主链定义

> **权威源**: `docs/PROGRAM_STATE_UNIFIED.yaml`
> **版本**: v1.0
> **更新时间**: 2026-03-19

---

## 正式主链定义

**唯一正式主体主链**：

```
User/Telegram → EgoCore ingress/runtime → OpenEmotion /cycle → EgoCore 决策与执行 → 结果回流 OpenEmotion → Telegram 回复
```

### 主链组件

| 组件 | 位置 | 角色 | 状态 |
|------|------|------|------|
| Telegram Bot | EgoCore | 用户入口 | ✅ 生效 |
| semantic_router | EgoCore | 意图分类 | ✅ 生效 |
| subject_adapter.cycle() | EgoCore | 主体适配入口 | ✅ 生效 |
| /cycle endpoint | OpenEmotion (emotiond) | 主体处理核心 | ✅ 生效 |
| CycleCoreKernel | OpenEmotion | 循环主体核 | ✅ 生效 |
| openemotion_adapter | EgoCore | 边界适配层 | ✅ 生效 |
| response renderer | EgoCore | 响应渲染 | ✅ 生效 |

---

## 禁止的并行主链

以下路径**不得**作为正式主体主链存在：

| 路径 | 状态 | 说明 |
|------|------|------|
| `/plan` 相关链路 | ⚠️ 已降级 | 登记为 shim，到期版本 v1.1.0 |
| `interpret()` 直接调用 | ⚠️ Fallback only | 仅在 OpenEmotion 不可用时降级使用 |
| legacy/openclaw | ⚠️ 已冻结 | 不作为正式主链路径 |

---

## 边界责任

### OpenEmotion 负责

- identity invariants（身份不变量）
- self-model（自我模型）
- long-term self summary（长期自我摘要）
- event / narrative / policy memory（三层记忆）
- appraisal / reflection（评价与反思）
- cycle processing（循环处理）

### EgoCore 负责

- 用户入口（Telegram Bot）
- 运行时（runtime）
- 任务系统（task runtime）
- 工具执行（tool system）
- 恢复 orchestration
- adapter / audit / trace

**规则**：
- 允许 mirror / cache / shim
- 不允许双主
- 主体本体逻辑最终解释权在 OpenEmotion

---

## 验证状态

### 已验证 (verified_e2e)

| 能力 | 证据 |
|------|------|
| CYCLE_CORE_V1 | OpenEmotion/artifacts/eval/ws_c1_verification_20260319.md |
| WS_C1 | 6/6 验收点通过，Telegram E2E 真实触发 |
| SelfModelAdapter | OpenEmotion/docs/E2E_SELF_MODEL_ADAPTER_REPORT.md |
| CLOSED_LOOP_E2E_V3 | EgoCore/docs/DUAL_REPO_CLOSED_LOOP_E2E_V3_REPORT.md |

### Shadow Running

| 能力 | 说明 |
|------|------|
| MVP14 (Drives) | Gate A/B passed |
| MVP15 (Reflection) | Persistence integrity verified |

### 代码存在（未验证）

| 能力 | 说明 |
|------|------|
| long-term self summary | 未 E2E 验证 |
| Self Restorer | 未 E2E 验证 |

---

## Shim 注册

详见 `EgoCore/SHIM_REGISTER.md`。

当前 shim：
1. SHIM-001: identity_invariants.schema.json → 到期 v1.1.0
2. SHIM-002: self_model.schema.json → 到期 v1.1.0
3. SHIM-003: long_term_self_summary.schema.json → 到期 v1.1.0
4. SHIM-004: summary_generator.py → 到期 v1.1.0

---

## 状态标签定义

| 标签 | 含义 |
|------|------|
| `verified_e2e` | Telegram 真实触发验证通过 |
| `verified_local` | 本地测试通过，未 Telegram E2E |
| `verified_contract` | Schema/契约验证通过 |
| `code_exists` | 代码存在，未验证 |
| `shadow_running` | 生产环境 shadow 模式运行中 |
| `in_progress` | 开发中 |
| `blocked` | 阻塞中 |

---

## 更新规则

1. **唯一真相源**: `docs/PROGRAM_STATE_UNIFIED.yaml`
2. **README 必须同步**: README 状态必须与 PROGRAM_STATE 一致
3. **禁止漂移**: 发现 README 与 PROGRAM_STATE 冲突，立即修复
4. **证据优先**: 任何状态变更必须有可追溯的证据

---

## 参考

- PROGRAM_STATE_UNIFIED.yaml (EgoCore/docs/, OpenEmotion/docs/)
- SHIM_REGISTER.md (EgoCore/)
- EgoCore_OpenEmotion_Boundary_Constitution_v1.md (OpenEmotion/POLICIES/)
