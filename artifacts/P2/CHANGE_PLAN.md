# P2 CHANGE_PLAN

## 目标
把 Proto-Self 宿主持久化从单文件含混镜像，收口成分层、可解释、可迁移、可回放的 host-side store，同时保持当前主链接线不破。

## 已执行变更
1. 新增 [`proto_self_state_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_state_store.py)，定义四层宿主状态目录。
2. 将 [`proto_self_adapter.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py) 改为经由 store 加载/保存状态，并登记 session/thread 绑定。
3. 将 [`proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py) 的 ingress / external_result 事件补充 `conversation_context` 与 `runtime_summary.state_scope`。
4. 将 [`loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py) 的 `reset_session()` 接上 session reset 审计。
5. 将 [`proto_self_restore.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_restore.py) 切到新 store。
6. 新增 [`test_proto_self_state_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_proto_self_state_store.py)。

## 新目录语义
- `artifacts/proto_self_store/agent_global/proto_self_state.v1.json`
  - live 主体镜像
- `artifacts/proto_self_store/sessions/<session>/session.json`
  - host session reset / generation / latest event 元数据
- `artifacts/proto_self_store/threads/<thread>/thread.json`
  - host conversation/thread 绑定与最近事件索引
- `artifacts/proto_self_store/experiments/<run>/proto_self_state.v1.json`
  - replay / compare / experiment 的隔离副本
- `artifacts/proto_self_mirror/state.json`
  - compatibility-only mirror

## 边界约束
- OpenEmotion 继续拥有 `ProtoSelfState` 字段语义解释权。
- EgoCore 只拥有宿主状态边界、reset 语义、run 隔离和兼容迁移。
- trace 文件保持原状；本轮不统一 trace/evidence 总账本。

## 为什么不是“只换目录”
- 本轮不只是把 `state.json` 移动到新目录，而是把长期主体镜像、session reset 元数据、thread 索引、experiment 隔离副本拆成不同所有权层。
- `/new`、`reset_session` 的宿主影响面现在落在 session 层元数据，而不是继续隐式依赖“某个文件有没有被删”。
- replay/run 隔离现在有明确状态副本边界，不再默认复用 live agent-global mirror。

## 兼容策略
- 读取顺序：优先新 `agent_global` 路径，缺失时回落 legacy `state.json`
- 写入顺序：先写新路径，再双写 legacy `state.json`
- 旧脚本和现有主链因此仍可继续观察 `artifacts/proto_self_mirror/state.json`

## 回滚策略
- 如需快速回退，只需让 adapter 恢复直接读写 legacy `state.json`
- 新 store 目录不影响 OpenEmotion state schema，因此回退时无需迁移本体字段

## 本轮不扩展的点
- 不改变 OpenEmotion `ProtoSelfState` schema
- 不替换现有 trace 文件布局
- 不把 replay runner 全量迁移到 experiment/run 层
