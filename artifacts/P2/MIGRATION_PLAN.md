# P2 MIGRATION_PLAN

## 迁移目标
把单一 `artifacts/proto_self_mirror/state.json` 迁移为分层宿主 store，但不破坏现有 live 入口、脚本和最小回归。

## 迁移原则
- 先兼容读取，再新路径落盘，再保留 legacy 双写
- 不迁移 OpenEmotion 本体 schema，只迁移宿主存储边界
- 不让 replay/experiment 继续污染 live agent-global

## 分阶段策略

### Phase 1
兼容接入，已完成
- 新增 `artifacts/proto_self_store/agent_global/proto_self_state.v1.json`
- adapter 优先读新路径，缺失时读 legacy `state.json`
- adapter 保存时同时写新路径和 legacy `state.json`

### Phase 2
宿主层分流，已完成最小版本
- live 事件写 `sessions/<session>/session.json`
- live 事件写 `threads/<thread>/thread.json`
- `/new` / `reset_session` 把 reset 审计写到 session 层
- replay/run 可 fork `experiments/<run>/proto_self_state.v1.json`

### Phase 3
后续执行，不在本轮
- 把现有 replay runner 正式接到 `experiments/<run>` 层
- 逐步让脚本和状态检查工具从 legacy `state.json` 切到新路径
- 在 P3/P4 之后判断何时去掉 legacy 双写

## 旧状态迁移规则
- 输入文件：`artifacts/proto_self_mirror/state.json`
- 目标文件：`artifacts/proto_self_store/agent_global/proto_self_state.v1.json`
- 迁移方式：首次读取 fallback，不做 destructive move
- 成功条件：读取结果与旧文件内容等价，随后新旧双写保持同步

## 新状态初始化规则
- `session`
  - 首次 live event 或首次 reset 时创建
- `thread`
  - 首次 live event 时创建
- `experiment(run)`
  - replay / compare / experiment fork 时创建

## `/new` 与 reset 迁移口径
- 不再通过“删除 `state.json`”表达新会话
- 统一表达为：session 层 reset，agent-global preserve
- 如未来需要“清空主体镜像”，那应是显式新命令，不应偷复用 `/new`

## 回滚方案
- 回滚代码到直接读写 legacy `artifacts/proto_self_mirror/state.json`
- 新 `artifacts/proto_self_store` 可保留为旁路 artifact，不影响旧路径恢复

## 风险点
- 旧脚本可能仍假设 `state.json` 是唯一来源
- thread 现阶段仍退化为 `session_id`
- replay 尚未全部接线到 experiment 层，短期内仍要靠治理约束避免误写 live mirror
