# v7 Stage 0 - Operator Observability

## Goal

让用户能用一个 lab-only operator report 看懂当前 agent 为什么这样选、哪里失败、下一步该测什么。

## Non-goals

- 不实现新的 agency kernel 行为。
- 不接 EgoCore / OpenEmotion / Telegram runtime。
- 不更新 `docs/PROGRAM_STATE_UNIFIED.yaml` 或 formal evidence ledger。
- 不写 temp/log/runtime JSONL，测试只允许使用 `tmp_path`。

## Constraints

- 边界约束：只读现有 `DecisionView`、`AgencyDecisionView`、`SelfMaintainingAgencyCycleResult`、`RootCauseTrace`。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：报告必须可由本地命令生成，不依赖 live Telegram。
- 发布约束：本任务只能声明 lab-only observability。

## Problem framing

- 当前问题表述：用户无法测试、无法知道总目标进度、无法定位失败根因。
- 归一化后的问题表述：先把决策链和失败归因外化为 operator-readable report。
- 为什么这个 framing 更适合当前任务：没有可观测面时，继续做 kernel / companion / skill 只会扩大黑盒。

## Implementation method

- 基于 `ego_desktop_lab/root_cause.py` 生成 root-cause ticket。
- 增加或扩展 lab-only operator report，展示 stage ladder、current gate、failure category、next minimal probe。
- 报告只读既有 result/view，禁止重新计算 selected option / gate / policy。

## Unknowns to eliminate

- 当前 shell/report 是否已有足够字段展示 boundary / viability / prediction / ranking / gate / plasticity。
- root-cause ticket 是否能覆盖 expression / runtime bridge / evidence claim mismatch 三类常见误判。
- 用户是否能用单条命令复现报告。

## Acceptance criteria

- [x] report 展示 boundary / viability / prediction / ranking / gate / plasticity / root cause。
- [x] 无足够 trace 时输出 `unknown`，不得硬猜。
- [x] expression failure、runtime bridge failure、evidence claim mismatch 能分开归因。
- [x] 报告包含 claim ceiling 和 no runtime influence。
- [x] 用户可以用一个命令生成报告。

## Disallowed premature claims

- 不得宣称 runtime efficacy。
- 不得宣称 live user benefit。
- 不得宣称 consciousness / alive / real autonomy。

## Known risks / dependencies

- 风险：报告层重新计算决策，制造第二套 truth source。
- 依赖：现有 `AgencyDecisionView` 和 `RootCauseTrace` 字段足够稳定。
- 外部 blocker：无。

## Authority refs

- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `ego_desktop_lab/README.md`
- `ego_desktop_lab/root_cause.py`
- `docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
