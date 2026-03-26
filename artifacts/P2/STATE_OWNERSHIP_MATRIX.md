# P2 STATE_OWNERSHIP_MATRIX

## 状态归属总表

| layer | canonical payload | authority owner | host artifact | who mutates | `/new` | `reset_session` | `replay` | `real_telegram` |
|---|---|---|---|---|---|---|---|---|
| agent-global | `ProtoSelfState` (`identity/self_model/drives/cycle_store/episodic_trace`) | OpenEmotion | `artifacts/proto_self_store/agent_global/proto_self_state.v1.json` | Proto-Self kernel 处理 live 事件后由 EgoCore 镜像保存 | preserve | preserve | fork as base, do not mutate live by default | mutate live mirror |
| session | host runtime generation / reset audit / latest event pointer | EgoCore | `artifacts/proto_self_store/sessions/<session>/session.json` | `RuntimeV2Loop.reset_session()` / live event binding | reset | reset | separate run session if needed | update |
| thread (conversation) | conversation/thread pointer, latest session/event index | EgoCore | `artifacts/proto_self_store/threads/<thread>/thread.json` | live event binding | preserve | preserve | read-only input unless replay defines its own thread scope | update |
| experiment(run) | isolated `ProtoSelfState` copy for replay/compare/experiment | EgoCore host orchestration | `artifacts/proto_self_store/experiments/<run>/proto_self_state.v1.json` | replay / experiment runner | no effect | no effect | mutate isolated copy only | no effect unless explicitly launched as run |
| compatibility mirror | legacy copy of agent-global mirror | none, compatibility-only | `artifacts/proto_self_mirror/state.json` | adapter dual-write | preserve | preserve | should not be live replay write target | updated only as compatibility shadow |

## 现状与判定
- `agent-global` 不是 EgoCore 发明的新主体结构；它只是 OpenEmotion `ProtoSelfState` 的宿主镜像。
- `session` 与 `thread` 都是宿主 runtime/conversation 元数据层，不能承载 identity/self-model 真值。
- `experiment(run)` 是为了 replay 隔离，不是第二个 live 主体。
- `compatibility mirror` 明确降级为过渡方案，不再承担“所有层状态”的名义。

## 当前命令/入口影响面

| trigger | agent-global | session | thread | experiment(run) | notes |
|---|---|---|---|---|---|
| `/new` | preserve | clear/reset + generation++ | preserve | no-op | 当前 Telegram 通过 `RuntimeV2Loop.reset_session()` 实现 |
| `reset_session(session_id)` | preserve | clear/reset + generation++ | preserve | no-op | 宿主 API，语义与 `/new` 同层 |
| `replay` | use as baseline only | optional new replay session | optional replay-local thread mapping | create/fork and mutate isolated copy | 不能直接回写 live agent-global |
| `real_telegram` live turn | update via kernel result mirror | update latest event / reset history untouched | update latest event pointer | no-op | 当前 `thread_id` 暂退化为 `session_id` |

## 真实职责审计结论
- 当前 live `state.json` 已经证明它承载的是 agent-global 跨 turn 镜像，不是 session 文件。
- `SessionContextStore` 只保存内存对话上下文，不是主体持久化层。
- trace 记录的是每事件 replay 载荷，不是 session/thread/agent-global 生命周期存储。

## 过渡项
- Telegram thread 目前未独立建模，暂用 `session_key` 作为 `thread_id`
- legacy `state.json` 仍保留双写，待后续 runner/script 完成切换后再退出
