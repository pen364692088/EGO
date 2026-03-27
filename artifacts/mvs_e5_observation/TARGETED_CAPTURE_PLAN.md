# Targeted Capture Plan

## 主线目标

下一轮真实样本采集只做三件事：

1. 补 O1 关键场景真实样本
2. 压 remaining evidence gap
3. 定向补 plasticity / reflection 因果样本

## O1 关键场景

前置约束：

- `telegram_bot_api_e2e.py` 只会产生 `bot -> user` 消息，不能作为 O1 直接样本来源
- O1 / plasticity / reflection 的真实样本，必须由真实 Telegram 用户侧消息触发
- 启动建议统一使用 `EgoCore/scripts/start_egocore_windows_python.sh`，确保从 canonical Windows root 起 bot

### 场景 1: `/new`

步骤：

1. 先在同一 Telegram 会话里发送一个普通问题
2. 发送 `/new`
3. 再发送一个需要 continuity 判断的问题

验收：

- `/new` 本身产生直接真实样本
- reset 审计记录命令名为 `/new`
- `/new` 前后 continuity 不再只靠 `session.json` / `thread.json` 间接推断

### 场景 2: restart

步骤：

1. 在 bot 运行中发送一条普通问题
2. 重启 EgoCore 进程
3. 再发送 continuity 检查消息

验收：

- restart 前后两侧都有真实 Telegram 样本
- restart 后第一条消息形成完整 evidence bundle
- continuity 结论来自真实消息链，而不是只看 state manifest

### 场景 3: restore

步骤：

1. 在已有 agent-global 状态下启动新进程
2. 发送 restore 相关 probing 问题
3. 观察 restore 后第一条真实消息的 tendency / context

验收：

- restore 后第一条消息形成完整样本
- 能从真实样本直接比对 restore 前后行为，不只靠 restore audit 文件

## Plasticity / Reflection 因果链

### 场景 4: failure -> repair -> re-decision

建议提示链：

1. 请求读取一个不存在的文件
2. 紧接着请求读取一个存在的文件
3. 再问“下一步该怎么做 / 你现在更倾向什么策略”

验收：

- blocked 样本存在
- retry-success 样本存在，且观察 `repair_closure`
- 第三步不是一般聊天噪声，而是可用于读取 `response_tendency` / `policy_hint` / `reflection_note`

### 场景 5: repeated failure with follow-up

建议提示链：

1. 制造一次工具 blocked
2. 再制造一次相似 blocked
3. 发送“那你现在会怎么调整计划”

验收：

- 能观察 repeated failure 是否改变后续 tendency
- 不能只留下 blocked 两次而没有后续 re-decision 样本

## 采样纪律

- 禁止继续堆大量一般问候样本
- 每条真实样本都要看是否进入了完整 evidence bundle
- 发现缺项时先修 collector 时序，再继续采
- 不允许为了补证把 family / repair / reflection 语义偷回 EgoCore
