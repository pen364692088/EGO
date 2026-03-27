# Blockers And Stop Reasons

## 本轮为什么必须停在“准入拒绝”

### 1. replay / audit insufficiency

- 观察窗口真实样本 `58`
- 完整样本 `35`
- 缺项样本 `23`

这不是小噪声，而是会直接削弱结论强度的正式 blocker。

### 2. identity continuity 覆盖不足

- 没有 `/new` / `restart` / `restore` 的直接真实样本
- 当前只能依赖 session/thread continuity 与 reset-preserve-agent-global 的状态证据
- 现有 `telegram_bot_api_e2e.py` 只能发送 `bot -> user` 消息，不能制造 `user -> bot` 的真实 ingress
- 当前仓库也明确不接入 `TDLib / Telethon`，因此缺少可自动生成真实入站样本的用户侧客户端

这不足以支撑 O1 的完整通过。

### 3. plasticity / reflection 仍偏弱

- `response_tendency` 确实有变化，但主要集中在短期局部上下文
- `reflection_note` 在窗口内完全同型，尚不足以证明 reflection 本体稳定写回

## 当前停止条件

在以下任一条件未补齐前，不应进入 Developmental Self：

1. `/new` / `restart` / `restore` 真实样本补齐
2. 观察窗口 evidence gap 显著下降
3. plasticity / reflection 拿到更直接、可重复的真实因果证据

## 允许继续前的最小动作

- 用 `EgoCore/scripts/start_egocore_windows_python.sh` 从 canonical Windows root 起 bot
- 由真实 Telegram 用户侧消息完成 `/new` / `restart` / `restore` 采样，不能再用 Bot API 自发消息替代
- 先把观测窗口延长到 `3-7` 天
- 再做定向真实样本采集
- 最后重新跑一次准入评审，而不是直接开做下一阶段能力
