# MVP13 Audit Report

> Phase E: MVP13 验证
> 审计时间: 2026-03-13

---

## 验证范围

MVP13 核心验证点：
- Persistent Self-Model 是否真的形成跨时间连续性
- identity invariants
- self-history
- self-change tracking
- self-model 对未来行为是否有因果影响

---

## 验证结果汇总

| 项目 | 状态 | 证据 |
|------|------|------|
| 测试通过 | ✅ PASS | 58 passed |
| 模块存在 | ✅ PASS | emotiond/self_model/ |
| 新 Schema | ✅ 存在 | SelfModelState, IdentityCore |
| 持久化 API | ✅ 存在 | SelfModelPersistence |
| 主链使用 | ⚠️ PARTIAL | 使用 legacy API |
| 新 API 接线 | ❌ FAIL | SelfModelManager 未使用 |
| 因果干预 | ❌ N/A | 无法验证新 API 因果效力 |

**最终裁决**: **PARTIAL**

---

## 详细证据

### 1. 模块结构

```
emotiond/self_model/
├── __init__.py        # 模块导出 (legacy + MVP13)
├── legacy.py          # 旧 SelfModel API (55KB, 主链使用)
├── schema.py          # MVP13 新 Schema (SelfModelState, IdentityCore)
├── persistence.py     # 持久化层
├── updates.py         # 更新规则
└── integration.py     # SelfModelManager (集成层)
```

### 2. 测试验证

```
tests/mvp13/: 58 passed
```

测试覆盖：
- `test_self_model_infra.py` - 基础设施测试
- `test_integration.py` - 集成测试
- `test_e2e_gate_b.py` - E2E Gate B 测试

测试验证了：
- 持久化跨会话
- 结构完整性
- 可回放性
- 身份连续性
- 漂移治理

### 3. 主链使用分析

**core.py 导入**:
```python
from emotiond.self_model import (
    get_self_model,
    build_self_model_v0,
    render_self_report,
    get_self_model_v0,
    reset_self_model_v0
)
```

**实际调用**:
```python
# core.py line 951
self_model_v0 = get_self_model_v0(target)
self_model_v0_result = self_model_v0.apply_event(event_dict, ctx)
```

**结论**: ✅ 使用 legacy API (`SelfModelV0`)，❌ 未使用新 MVP13 API (`SelfModelManager`)

### 4. 新 API 未接线

**SelfModelManager 可用方法**:
| 方法 | 功能 | 主链调用 |
|------|------|---------|
| `get_identity_summary()` | 身份摘要 | ❌ |
| `get_behavioral_profile()` | 行为画像 | ❌ |
| `get_capability()` | 能力查询 | ❌ |
| `get_tension_bias()` | 张力偏好 | ❌ |
| `update_behavior()` | 行为更新 | ❌ |
| `update_capability()` | 能力更新 | ❌ |
| `update_tension()` | 张力更新 | ❌ |
| `check_health()` | 健康检查 | ❌ |

### 5. 持久化验证

**持久化 API 存在**:
```python
class SelfModelPersistence:
    def save(self, state: SelfModelState) -> bool
    def load(self) -> Optional[SelfModelState]
    def exists(self) -> bool
```

**实际使用**: ⚠️ 通过 `SelfModelManager` 调用，但 `SelfModelManager` 未被主链使用。

**Legacy 持久化**: ❓ 未验证 legacy `SelfModelV0` 是否有持久化

---

## 因果干预验证

**实验设计**: 修改 SelfModel，重跑同类场景，观察行为差异。

**状态**: ❌ 无法执行

**原因**: 新 MVP13 API (`SelfModelManager`) 未接入主链，无法验证其对行为的影响。

**替代验证**: Legacy `SelfModelV0` 可能对行为有影响，但这不是 MVP13 宣称的功能。

---

## TensionType 枚举问题

**之前报告**: TensionType 缺少 `VALUE_CONFLICT`

**当前状态**: TensionType 包含 5 种类型：
- `SPEED_VS_RELIABILITY`
- `AUTONOMY_VS_GOVERNANCE`
- `PERSISTENCE_VS_FLEXIBILITY`
- `HONESTY_VS_HARMONY`
- `GROWTH_VS_STABILITY`

**结论**: 枚举定义完整，`VALUE_CONFLICT` 可能是测试代码中的错误引用。

---

## 身份连续性验证

### 设计目标

MVP13 宣称的身份连续性：
- 跨会话持久化
- 身份不变量保护
- 变更可审计

### 实际状态

| 功能 | 实现 | 主链使用 |
|------|------|---------|
| 身份持久化 | ✅ SelfModelPersistence | ❌ |
| 不变量检查 | ✅ verify_identity_integrity() | ❌ |
| 变更审计 | ✅ revision_history | ❌ |
| 跨会话 | ⚠️ API 存在 | ❌ |

**结论**: 功能实现但未生效。

---

## 发现的问题

### 1. 新 API 未接线 (CRITICAL)

**现象**: `SelfModelManager` 未在主链使用。

**影响**:
- 宣称的"Persistent Self-Model"未生效
- 所有 MVP13 新功能无法影响系统行为
- 持久化机制未真正使用

### 2. Legacy 依赖

**现象**: 主链继续使用 `SelfModelV0` (legacy)。

**风险**:
- 旧实现可能有不同行为
- 新功能测试通过但实际不生效
- 维护负担（同时维护两套 API）

### 3. 测试与主链不一致

**现象**: 测试验证 `SelfModelManager`，主链使用 `SelfModelV0`。

**风险**: 测试通过不代表功能生效。

---

## 判定理由

### PARTIAL 判定

1. ✅ 代码存在且结构合理
2. ✅ 测试覆盖充分
3. ✅ 持久化 API 存在
4. ⚠️ Legacy API 被主链使用
5. ❌ 新 MVP13 API 未接线
6. ❌ 无法验证新 API 的因果效力

### 为什么不是 PASS_WEAK

PASS_WEAK 要求"机制存在且可运行"。MVP13 新机制存在但未运行（未接线），这是更严重的问题。

---

## 建议行动

### 立即行动 (P0)

1. 在 `core.py` 中集成 `SelfModelManager`
2. 替换 `get_self_model_v0()` 调用为 `get_self_model_manager()`

### 中期行动 (P1)

1. 添加集成测试验证主链调用
2. 实现因果干预验证

### 长期行动 (P2)

1. 统一 API，废弃 legacy
2. 添加跨会话连续性验证

---

## 裁决

**MVP13**: **PARTIAL**

- 机制存在: ✅
- 可运行: ✅ (测试通过)
- 起作用: ⚠️ (仅 legacy)
- 可证明起作用: ❌ (新 API 未接线)

---

*审计完成时间: 2026-03-13*
