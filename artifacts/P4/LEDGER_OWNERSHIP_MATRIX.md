# P4 LEDGER_OWNERSHIP_MATRIX

| area | primary authority | host role | compatibility mirror | notes |
|---|---|---|---|---|
| Proto-Self `trace_payload` 语义 | OpenEmotion [`trace_types.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py#L19) | 纳入 `ledger.json` 的 `openemotion.trace_payload` | `openemotion_trace.json`, `logs/proto_self_trace.jsonl` fallback | replay 不允许用 host 重新发明 trace 语义 |
| 统一样本账本 | EgoCore [`telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L345) | 生成 `ledger.json` | `sample.json` | `ledger.json` 是本轮主账本 |
| 输入事件 | EgoCore runtime canonical event | 写入 `ledger.json.inputs.normalized_event` | `normalized_event.json` | 受 P3 canonical 契约约束 |
| OpenEmotion 结构化输出 | OpenEmotion kernel output | 写入 `ledger.json.openemotion.result` | `openemotion_result.json` | host 不改写主体语义 |
| Host response plan | EgoCore runtime | 写入 `ledger.json.host.response_plan` | `response_plan.json` | 只表示 host-side orchestration |
| Outbox record | 渠道发送记录 | 写入 `ledger.json.host.outbox_record` | `outbox_record.json` | 不参与 Proto-Self replay 语义 |
| 审计索引 | EgoCore | `ledger.json.ids / host.timeline / tape / replay` | `timeline.json`, `tape.json`, `replay.json` | 只做索引与报告输入 |
| `ProtoSelfTraceBridge` | 无主权，仅兼容导出 | fallback 写 jsonl | `logs/proto_self_trace.jsonl` | 禁止再成为第二真相源 |

## 结论
- 主账本：`artifacts/.../sample_xxx/ledger.json`
- 主体本体权威输入：`ledger.json.openemotion.trace_payload`
- 兼容镜像：`sample.json / replay.json / tape.json / openemotion_trace.json / summary.md`
- 历史兼容 fallback：`logs/proto_self_trace.jsonl`
