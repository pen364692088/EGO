# P3 SCHEMA_DIFF

## 输入契约差异

| area | before | after | owner |
|---|---|---|---|
| safety risk field | `risk` 与 `risk_level` 并存 | `risk_level` 是唯一 canonical 字段 | OpenEmotion schema |
| compatibility absorption | runtime、event builder 都可能主动双写 | 只允许 `normalize_safety_context()` / `kernel_event_from_payload()` 吸收 legacy `risk` | OpenEmotion schema + EgoCore adapter |
| runtime ingress event | 宿主手拼并输出双字段 | 宿主只输出 canonical `risk_level` | EgoCore runtime |
| event builder | 输出 `risk` + `risk_level` | 只输出 `risk_level` | EgoCore builder |

## 输出契约差异

| area | before | after | owner |
|---|---|---|---|
| adapter output | `proto_self_adapter` 手写 partial dict，只选部分字段 | adapter 直接返回 `serialize_kernel_output(result)` 的 canonical output shape | OpenEmotion schema / EgoCore adapter |
| output authority | 实际存在 schema + adapter 双实现 | `KernelOutput.to_dict()` 成为正式输出形状 | OpenEmotion schema |

## Canonical 字段全集

### KernelEvent
- `schema_version`
- `event_id`
- `timestamp`
- `actor`
- `source`
- `event_type`
- `user_intent`
- `raw_text`
- `conversation_context`
- `task_context`
- `runtime_summary`
- `safety_context.risk_level`
- `external_result`

### KernelOutput
- `schema_version`
- `event_id`
- `identity_state_delta`
- `self_model_delta`
- `memory_update`
- `relationship_update`
- `appraisal_state_delta`
- `reflection_note`
- `policy_hint`
- `response_tendency`
- `confidence_meta`
- `trace_payload`

## 已废弃但仍兼容的字段

| field | status | compatibility entry | planned removal |
|---|---|---|---|
| `safety_context.risk` | deprecated input alias | `normalize_safety_context()` | 后续观察期稳定后移除 |

## 单点兼容规则
- 允许兼容的位置：
  - [`schemas.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/schemas.py)
  - [`proto_self_adapter.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py)
- 不再允许兼容的位置：
  - [`proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py)
  - [`event_builder.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/event_builder.py)

## 本次不处理
- 非 Proto-Self 主链的旧 `egocore.adapters.openemotion_adapter` 体系
- trace / evidence / replay 总账本字段统一
