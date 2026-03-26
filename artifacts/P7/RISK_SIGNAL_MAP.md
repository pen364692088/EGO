# P7 RISK_SIGNAL_MAP

## Canonical Source

| layer | file | role | status |
|---|---|---|---|
| generator | `EgoCore/app/risk_signal.py` | 唯一正式 risk scorer / field normalizer | formal |
| runtime emit | `EgoCore/app/runtime_v2/proto_self_runtime.py` | 用 canonical scorer 生成 `safety_context.risk_level` | consumer |
| runtime context | `EgoCore/app/runtime/context_assembler.py` | 用 canonical scorer 生成 runtime safety hint | consumer |
| routing guard | `EgoCore/app/runtime/semantic_router.py` | 用 canonical scorer 做高风险分流保护 | consumer |
| approval gate | `EgoCore/app/runtime/approval_policy.py` | 用 canonical scorer 做消息高风险确认 | consumer |
| event bridge | `EgoCore/app/openemotion_adapter/event_builder.py` | 用 canonical normalizer 发往 OpenEmotion | consumer |
| proto-self schema | `OpenEmotion/openemotion/proto_self/schemas.py` | 吸收 compat 输入并只保留 canonical `risk_level` | consumer |

## Canonical Field Contract

| item | canonical |
|---|---|
| field | `safety_context.risk_level` |
| values | `low`, `medium`, `high`, `critical` |
| producer type | string only |
| legacy alias input | `safety_context.risk` |
| numeric compat input | `risk_level` as `float/int` |
| compatibility owner | schema / adapter normalization |

## Rule Ownership

| rule type | owner | notes |
|---|---|---|
| message keyword / pattern / score | `EgoCore/app/risk_signal.py` | 唯一正式权威源 |
| message->approval decision | `app.risk_signal` + `approval_policy` consumer logic | `approval_policy` 不再维护第二套词表 |
| host->proto-self field mapping | `event_builder.py` + `schemas.py` | producer emits canonical strings; schema absorbs compat input |
| proto-self appraisal float mapping | `OpenEmotion/openemotion/proto_self/appraisal.py` | consumer-side value mapping，不是 host scorer authority |

## Risk Samples Matrix

| sample | canonical level | owner |
|---|---|---|
| `状态查询` | `low` | `app/risk_signal.py` |
| `修改配置文件` | `medium` | `app/risk_signal.py` |
| `git push origin main` | `high` | `app/risk_signal.py` |
| `删除临时文件` | `high` | `app/risk_signal.py` |
| `删除生产数据库` | `critical` | `app/risk_signal.py` |
| `rm -rf /tmp` | `critical` | `app/risk_signal.py` |
| `格式化磁盘` | `critical` | `app/risk_signal.py` |

## Compatibility-only Register

| item | current behavior | exit condition |
|---|---|---|
| `safety_context.risk` | schema/normalizer 吸收为 `risk_level` | 仓外输入方完成迁移后删除 |
| numeric `risk_level` | schema/normalizer 吸收为 canonical string | 旧 tests/scripts 改完并做一轮完整回归后删除 |
| OpenEmotion proto-self numeric risk tests | 继续保留以验证兼容输入 | compat 窗口关闭后删除或改写为 string |

## Out of Scope But Noted

| item | why not P7 canonical conflict |
|---|---|
| OpenEmotion EFE / candidate / mvp tests 中的 `risk` 数值 | 它们是模型内部代价或候选元数据，不是 host runtime risk signal authority |
| `approval_policy` 的高风险路径集合 | 这是路径边界策略，不是 message risk scorer 词表 |
