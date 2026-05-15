# v7 Stage 7 - Permissioned Runtime Action

## Goal

在前面全部稳定后，才允许最小真实动作能力的 permissioned spec。

## Non-goals

- 第一版不实现真实动作执行。
- 不默认开启 runtime action。
- 不绕过 user approval。
- 不扩大 Telegram/external-send 权限。

## Constraints

- 边界约束：host approval、allowlist、audit、rollback、kill switch 必须先于任何 action。
- 仓库/子仓约束：默认只写 spec/tests；真实 EgoCore 接入需另开 future task。
- 环境约束：第一版用 mocked permission contract。
- 发布约束：只能声明 permission contract readiness。

## Problem framing

- 当前问题表述：最终想让 agent 主动做事和操作电脑。
- 归一化后的问题表述：真实动作前必须先有可审计、可撤销、可拒绝的 permissioned action contract。
- 为什么这个 framing 更适合当前任务：没有 permission contract 的 autonomy 是安全风险，不是产品能力。

## Implementation method

- 设计 permissioned action spec，默认不执行真实动作。
- 每个 action 必须有 allowlist、user approval、audit、rollback、kill switch。
- 初始只允许 suggestion-to-action handoff。
- action outcome 回流 experience memory。

## Unknowns to eliminate

- 第一批可允许 action 类型。
- approval/audit schema 是否复用 EgoCore host gate。
- 如何从 shadow-only 回退。

## Acceptance criteria

- [ ] 未授权动作全部 block。
- [ ] ask/allow/block 可审计。
- [ ] action outcome 可回流 experience memory。
- [ ] 任意失败可回退到 shadow-only。
- [ ] 默认不执行真实动作。

## Disallowed premature claims

- 不得宣称 real autonomy。
- 不得宣称 desktop control enabled。
- 不得宣称 live user benefit。

## Known risks / dependencies

- 风险：spec 被误解为 runtime enablement。
- 依赖：Stage 6 shadow bridge。
- 外部 blocker：Stage 6 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/FUTURE_RUNTIME_SHADOW_TAP.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `docs/codex/tasks/v7-stage-6-runtime-shadow-bridge/STATUS.md`
