# P2 TASK_REPORT

## 任务名称
P2：主体状态持久化重构

## 任务类型
状态架构 / 持久化边界收口 / 主体连续性治理

## 目标与成功判据
- 把当前语义模糊的单文件 `state.json` 收口为分层宿主持久化方案
- 明确 `agent-global / session / thread / experiment(run)` 四层边界
- 明确 `/new`、`reset_session`、`replay`、`real_telegram` 对各层状态的影响面
- 保持 OpenEmotion 为主体本体权威源，EgoCore 只做 host-side mirror / cache / orchestration
- 兼容旧 `artifacts/proto_self_mirror/state.json`，不破坏当前主链基础接线

## 当前层级
架构层 / 状态主权层 / 宿主持久化壳层

## 当前确定项
- OpenEmotion `ProtoSelfState` 才是主体本体状态根，字段语义权威仍在 OpenEmotion。
- 当前宿主真实运行的 `artifacts/proto_self_mirror/state.json` 已同时承载 `identity/self_model/drives/cycle_store/episodic_trace`，实际语义是 agent-global 主体镜像，不是 session reset 文件。
- `RuntimeV2Loop.reset_session()` 只清宿主内存 session state；`TelegramBot` 的 `/new`、`/reset` 也只走这一层。
- OpenEmotion 的 `trace_payload` 仅保证 trace-driven replay 的单事件载荷，不等于宿主总状态账本。

## 关键未知
- 当前 Telegram 主链里 thread 层没有独立实体，现阶段只能先以 `session_key` 退化映射 thread。
- EgoCore 里还没有正式接入 Proto-Self replay run store；本轮只能先把 experiment/run 隔离能力落在 store 壳上。
- 真实 `real_telegram` 下未来是否要把 `thread_id` 从 `session_id` 拆开，仍取决于后续渠道语义而非本轮先验。

## 唯一主执行链
1. 审计当前 `state.json / mirror / trace / replay / reset` 的真实职责
2. 明确 agent-global / session / thread / experiment(run) 的状态归属
3. 落地分层 `ProtoSelfStateStore`
4. 保留旧 `state.json` 兼容读取与双写
5. 把 `/new` / `reset_session` 的影响显式记录到 session 层
6. 补迁移、reset、experiment 隔离测试
7. 产出 P2 证据与迁移文档

## 不做项
- 不做 P3 的 Proto-Self 契约单一化
- 不做 P4 的 trace / evidence / replay 总账本统一
- 不做 README 总口径修改
- 不做 OpenEmotion schema 总升级
- 不把 EgoCore 提升为主体本体真相源

## 审计结论
- 旧方案的问题不是“目录名太扁”，而是 `state.json` 同时被当成长期主体态、最近回合痕迹和宿主观测入口，层级语义没有被声明。
- `/new` 与 `reset_session` 过去一直只清宿主 session 内存，不清 Proto-Self mirror；这意味着现有行为天然更接近“保留 agent-global，重置 session”，只是之前没有被制度化。
- OpenEmotion 已明确 `ProtoSelfState` 和 `trace_payload` 的边界：前者是主体状态根，后者是 replay 所需的单事件轨迹；因此宿主侧应该存放 mirror / cache / reset 审计 / run 隔离，而不是重新定义 identity/self-model 语义。

## 本次改动
- 新增 [`proto_self_state_store.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_state_store.py)，引入分层宿主 store：
  - `agent_global/proto_self_state.v1.json`
  - `sessions/<session>/session.json`
  - `threads/<thread>/thread.json`
  - `experiments/<run>/proto_self_state.v1.json`
- `ProtoSelfAdapter` 改为通过 store 读写状态，并在 live 事件后登记 session/thread 绑定；旧 `artifacts/proto_self_mirror/state.json` 保留为 compatibility-only mirror。
- `RuntimeV2ProtoSelfRuntime` 现在把 `session_id / thread_id / turn_id / state_scope` 显式写入 Proto-Self ingress 与 external_result 事件。
- `RuntimeV2Loop.reset_session()` 现在会把 reset 语义写入 session 层元数据，但不会触碰 agent-global 主体镜像。
- `ProtoSelfRestore` 改为从新 store 的 agent-global 层恢复，兼容旧 mirror 回退。
- 新增 `test_proto_self_state_store.py`，验证 legacy 迁移、session reset 不污染 agent-global、experiment/run 隔离。

## 新状态语义
- `agent-global`
  - 内容：OpenEmotion `ProtoSelfState` 的宿主镜像/缓存
  - 归属：OpenEmotion 语义权威，EgoCore 仅做镜像
  - 被谁修改：Proto-Self kernel 事件处理后的 mirror 保存
- `session`
  - 内容：宿主会话元数据、generation、reset 审计、最近事件指针
  - 归属：EgoCore host runtime
  - 被谁修改：`/new`、`reset_session`、live event binding
- `thread`
  - 内容：会话线程绑定和最近事件索引
  - 归属：EgoCore host conversation scope
  - 被谁修改：live ingress / external_result 写入
- `experiment(run)`
  - 内容：从 agent-global fork 出来的 replay / compare / experiment 隔离副本
  - 归属：EgoCore host run scope
  - 被谁修改：replay / experiment runner

## `/new` / `reset_session` / `replay` / `real_telegram` 语义结论
- `/new`
  - 影响 `session`：清当前 runtime session，上调 `generation_id`
  - 不影响 `agent-global`
  - 不删除 `thread` 历史索引
  - 不进入 `experiment`
- `reset_session`
  - 语义与 `/new` 同层；当前只是宿主 runtime reset API
- `replay`
  - 应从 `agent-global` 或指定基线 fork 到 `experiment(run)` 层
  - 不应直接回写 live `agent-global`
  - 依赖 trace，但不等于 trace 文件本身
- `real_telegram`
  - 走 live 主链，更新 `agent-global` mirror
  - 同时更新对应 `session` 与 `thread` 元数据
  - 当前实现里 `thread_id` 先退化为 `session_id`

## 验证结果
- `python3 -m py_compile ...`：通过
- `cmd.exe /c "py -3 -m pytest tests\\test_proto_self_state_store.py -q"`：`3 passed`
- `cmd.exe /c "py -3 -m pytest tests\\test_telegram_session_commands.py::test_new_command_resets_runtime_v2_session -q"`：`1 passed`
- `cmd.exe /c "py -3 -m pytest tests\\test_runtime_v2_ws1_turn_isolation.py -q"`：`10 passed`
- 额外观察到现有回归 `tests/test_telegram_session_commands.py::test_status_command_returns_runtime_style_card` 失败，原因是 Telegram 输出已转义而断言仍按未转义文本比对；该失败与 P2 状态持久化修改无直接耦合，故仅登记为现存非 P2 归因样本

## 风险与剩余过渡项
- 旧 `artifacts/proto_self_mirror/state.json` 仍保留双写，这是本轮为保持主链不破的过渡方案。
- `thread_id=session_id` 是当前 Telegram 主链下的保守映射，不代表最终 conversation/thread 建模已完成。
- experiment/run 隔离能力已进入 store，但尚未把现有 replay runner 全量切到这一层；这属于后续接线问题，不在本轮展开。

## 本次结论能证明什么
- 能证明当前 `state.json` 已被从“唯一含混真相源”降级为 compatibility-only mirror
- 能证明宿主持久化已经明确拆成 `agent-global / session / thread / experiment(run)` 四层
- 能证明 `/new` 与 `reset_session` 当前只影响 session 层，而不会误清 agent-global 主体镜像
- 能证明 replay/experiment 已具备隔离状态副本的最小宿主承载方案

## 本次结论不能证明什么
- 不能证明长期连续身份已经成立
- 不能证明 replay 主链已经全部切换到 experiment 层
- 不能证明 Telegram 渠道最终 thread 语义已经完成
- 不能证明 trace / evidence / replay 已形成统一账本

## 哪些状态仍是过渡方案
- `artifacts/proto_self_mirror/state.json` 的兼容双写
- `thread_id = session_id` 的退化映射
- `ProtoSelfRestore` 当前默认回到 agent-global 层，而非更细粒度的 run/thread 恢复

## 离 P3 还差什么
- 还需要把 Proto-Self ingress / external_result / restore / replay 的契约字段统一成单一正式口径
- 还需要决定 thread 与 conversation 的正式契约标识，而不是继续沿用宿主 session 退化映射
- 还需要把 experiment/run store 与 replay 执行入口真正接线
