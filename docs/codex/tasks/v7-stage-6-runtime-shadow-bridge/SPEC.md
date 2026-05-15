# v7 Stage 6 - Runtime Shadow Bridge

## Goal

让 lab 观察 EgoCore/OpenEmotion/Telegram 事件，但不影响 runtime。

## Non-goals

- 不改变 EgoCore reply。
- 不写 OpenEmotion state。
- 不发 Telegram。
- 不把 shadow output 写入 formal evidence ledger。

## Constraints

- 边界约束：shadow/event tap only。
- 仓库/子仓约束：第一版优先改 `ego_desktop_lab`，如需 runtime fixture 只能用 copied event summary。
- 环境约束：必须用 mocked/copied events 测试。
- 发布约束：只能声明 shadow diagnostics。

## Problem framing

- 当前问题表述：lab 和旧 runtime 脱节，可能再次闭门造车。
- 归一化后的问题表述：先观察 runtime event summary，并输出 shadow DecisionView/root-cause report，不写回。
- 为什么这个 framing 更适合当前任务：shadow bridge 是避免第二套 authority 的唯一安全接入方式。

## Implementation method

- 实现 shadow/event tap spec。
- 输入 copied event summary。
- 输出 shadow `AgencyDecisionView` + root-cause report。
- mismatch 分类为 runtime_bridge / expression_surface / evidence_claim_mismatch。

## Unknowns to eliminate

- copied event summary 最小字段。
- lab decision 与 runtime decision 的比较口径。
- shadow artifact 是否需要落盘，默认不落盘。

## Acceptance criteria

- [ ] shadow report 可比较 runtime decision 与 lab decision。
- [ ] mismatch 可归类为 runtime_bridge / expression_surface / evidence_claim_mismatch。
- [ ] 无 writeback、无 delivery、无 transport mutation。
- [ ] formal evidence 不因 shadow 自动升级。
- [ ] mocked runtime event tests deterministic。

## Disallowed premature claims

- 不得宣称 runtime integration。
- 不得宣称 live efficacy。
- 不得宣称 formal mainline promotion。

## Known risks / dependencies

- 风险：shadow output 被误当 runtime authority。
- 依赖：Stage 5 skill sandbox 和 root-cause/operator report。
- 外部 blocker：Stage 5 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/FUTURE_RUNTIME_SHADOW_TAP.md`
- `ego_desktop_lab/root_cause.py`
- `docs/codex/tasks/v7-stage-5-computer-skill-sandbox/STATUS.md`
