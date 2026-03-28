# Codex Assistant Memory

这套目录只服务 `Codex/Claude Code` 一类开发助手的会话衔接，不接入 `EgoCore/OpenEmotion` runtime。

## 分层

- `project_truth.jsonl`
  记录稳定项目真相。只允许保存已核验、且可回溯到仓库文件的事实。
- `user_preferences.jsonl`
  记录已明确确认的长期用户偏好。必须能回溯到真实用户确认。
- `tasks/`
  记录任务 handoff / closure。用于新会话快速恢复“当前任务”。
- `sessions/`
  记录同一任务内的 session capsule。只延长单任务会话寿命，不跨任务续命。

## 记忆晋升规则

- 允许晋升：
  - 稳定项目真相
  - 长期用户偏好
  - 当前任务 handoff / closure
- 禁止晋升：
  - 长聊天原文
  - 未验证结论
  - 临时猜测
  - 调试噪声 / 大段日志
  - 过期讨论

所有长期记录都必须带：

- `scope`
- `source_type`
- `source_ref`
- `last_verified_at`
- `owner`
- `expiry_or_revalidate_rule`

## 开发坑记录规则

- 只要在真实开发中遇到“后续 agent 很容易重复踩到”的可复现执行坑，就应在收口时判断是否晋升为长期记忆。
- 只有同时满足以下条件，才晋升到 `project_truth.jsonl` 与 `PROJECT_MEMORY.md`：
  - 已真实复现过
  - 解决方法已验证有效
  - 对后续开发、提交、验证或主链采样有持续价值
- 记录格式应至少包含：
  - 问题现象
  - 触发条件
  - 正确解决口径
  - 不该再重复尝试的错误做法
- 典型例子：
  - 某类 shell / runner / 路径口径在当前环境下不稳定
  - 某类锁文件、残留进程、工作区状态会阻断后续提交或采样
  - 某类“看似成功但实际上是假阳性”的验证陷阱

## 会话启动顺序

默认注入优先级：

1. 当前任务 handoff
2. `CODEX_MEMORY.md`
3. 上一任务 closure
4. 同任务 session capsule

## 当前验收状态

- 截至 `2026-03-28`，这套记忆层已经完成首轮真实新会话验收。
- 已验证行为：
  - 仅给 `CODEX_MEMORY.md` 时，可恢复稳定项目真相与长期偏好。
  - `TaskHandoffRecord` 会覆盖旧会话噪声，作为当前任务主权威。
  - 同任务 `SessionCapsule` 可被采用为连续性补充。
  - 异任务 `SessionCapsule` 会被明确拒绝，不污染当前任务判断。
- 当前边界：
  - 这是开发助手侧结构化记忆，不接入 `EgoCore/OpenEmotion` runtime。
  - 当前形态仍是手动喂入或脚本辅助启动，不是全自动注入。

## Git 策略

- `project_truth.jsonl`、`user_preferences.jsonl`、`CODEX_MEMORY.md`、说明文档和脚本应纳入版本控制。
- `tasks/active/*.json`、`tasks/archive/*.json`、`sessions/*.json` 默认只保留本地，不自动提交。
