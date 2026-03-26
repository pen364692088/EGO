# P4 REPLAY_INPUT_RULES

## 唯一规则
1. Proto-Self replay 的主输入必须来自 `ledger.json.openemotion.trace_payload`。
2. replay 关联键必须以 `event_id` 为主，必要时补 `session_id / thread_id / turn_id / update_id`。
3. `normalized_event` 是 replay 上下文输入，不得替代 `trace_payload` 成为主体结论来源。
4. `openemotion_result` 可作为验收对照输出，不得代替 `trace_payload` 反推旧轮内部状态。
5. `response_plan / outbox_record` 只用于 host-side 验收与审计，不参与 Proto-Self 内部 replay 结论。
6. `ProtoSelfTraceBridge` 产出的 jsonl 仅在没有 collector/ledger 时作为兼容 fallback 输入。

## 当前落地
- 主引用位置：[`EgoCore/app/telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L394)
- runtime 优先入账本：[`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L132)
- OpenEmotion trace 权威定义：[`OpenEmotion/openemotion/proto_self/trace_types.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py#L19)

## E2 / E3 / E4 / E5 统一视图
- E2 simulated：`ledger.json` 结构与 E4 相同，`evidence_level=E2`
- E3 integration：`ledger.json` 结构与 E4 相同，`evidence_level=E3`
- E4 real_channel：`ledger.json` 结构与 E2/E3 相同，`evidence_level=E4`
- E5 observation：仍应沿用同一 `ledger.json` 视图，只是新增跨样本聚合和观察期报告，不得重新发明第二账本

## 报告来源规则
- 单样本摘要：从 `ledger.json` 派生
- 样本级验收报告：以 `ledger.json` 为主，`replay.json / tape.json` 为兼容引用
- 观察期 / 准入报告：聚合多个 `ledger.json`，不直接以 bridge jsonl 为正式输入
