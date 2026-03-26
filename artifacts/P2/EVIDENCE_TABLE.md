# P2 EVIDENCE_TABLE

| evidence_id | level | type | source | claim | limit |
|---|---|---|---|---|---|
| P2-E-001 | E1 | code | [`OpenEmotion/openemotion/proto_self/state.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/state.py#L241) | `ProtoSelfState` 是 OpenEmotion 定义的主体状态根；字段语义权威不在 EgoCore | 只证明本体结构定义，不证明宿主如何正确持久化 |
| P2-E-002 | E1 | code | [`OpenEmotion/openemotion/proto_self/trace_types.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py#L19) | `trace_payload` 是单事件 replay 载荷，不是宿主总状态账本 | 不证明 live replay runner 已接到新 store |
| P2-E-003 | E2 | artifact | [`artifacts/proto_self_mirror/state.json`](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/proto_self_mirror/state.json#L1) | 现有 `state.json` 同时含 `identity/self_model/drives/cycle_store/episodic_trace`，真实职责是 agent-global 镜像 | 不能单独推出 session/thread 语义已清楚 |
| P2-E-004 | E1 | code | [`EgoCore/app/interaction/session_context_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/interaction/session_context_store.py#L15) | `SessionContextStore` 只是内存最近对话上下文，不是 Proto-Self 持久化层 | 只证明一条旁路上下文，不代表所有 session 元数据 |
| P2-E-005 | E1 | code | [`EgoCore/app/telegram_bot.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py#L254) | `/new` 和 `/reset` 走 `RuntimeV2Loop.reset_session()`，现有主链并不会清 Proto-Self mirror | 不证明 reset 审计以前有显式记录 |
| P2-E-006 | E1 | code | [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L116) | `reset_session()` 现在显式写 session reset 审计，且不触碰 agent-global | 不证明所有渠道入口都已接这条语义 |
| P2-E-007 | E1 | code | [`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L28) | ingress / external_result 事件现在显式携带 `session_id/thread_id/turn_id/state_scope` | 当前 thread 仍退化为 session_id |
| P2-E-008 | E1 | code | [`EgoCore/app/openemotion_adapter/proto_self_state_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_state_store.py#L41) | 宿主 store 已分出 `agent_global/session/thread/experiment` 四层，并保留 legacy 双写 | 只证明存储壳已落地，不证明 legacy 已可删除 |
| P2-E-009 | E2 | test | [`EgoCore/tests/test_proto_self_state_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_proto_self_state_store.py#L17) | 已验证 legacy 读取迁移、session reset 不污染 agent-global、experiment/run 隔离 | 只覆盖 store 最小语义，未覆盖全量 replay runner |
| P2-E-010 | E2 | test run | `cmd.exe /c "py -3 -m pytest tests\\test_proto_self_state_store.py -q"` | 新增 P2 测试 `3 passed` | 环境只证明最小集，不代表全仓全量稳定 |
| P2-E-011 | E2 | test run | `cmd.exe /c "py -3 -m pytest tests\\test_telegram_session_commands.py::test_new_command_resets_runtime_v2_session -q"` | `/new` 主链接线在本轮后仍通过 | 不证明 `/status` 或其他 Telegram 文案断言稳定 |
| P2-E-012 | E2 | test run | `cmd.exe /c "py -3 -m pytest tests\\test_runtime_v2_ws1_turn_isolation.py -q"` | `reset_session` 相关 WS-1 测试 `10 passed`，说明本轮未打破 turn isolation 主逻辑 | 不证明所有 runtime_v2 回归都通过 |
