# v7 Stage 1 - Deterministic Agency Kernel

## Goal

证明内部可行性状态加 outcome feedback 会稳定改变下一轮 option ranking。

## Non-goals

- 不实现 experience memory。
- 不实现 companion surface。
- 不接真实工具、GUI、Telegram 或 desktop。
- 不更新 formal state / evidence ledger。

## Constraints

- 边界约束：lab-only；所有 action 必须保持 `no_action_executed=true`。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：必须 deterministic replay。
- 发布约束：只能声明 deterministic lab proof。

## Problem framing

- 当前问题表述：v7 kernel 可能只是旧 pressure/learning 字段换名。
- 归一化后的问题表述：必须证明 outcome 改变 next-cycle ranking，且无 outcome 不乱变。
- 为什么这个 framing 更适合当前任务：这是主体动力学是否真实存在的最小反证点。

## Implementation method

- 强化 `agency_kernel.py` 的 `before -> outcome -> plasticity -> after` trace contract。
- 明确输出 ranking delta、pressure delta、prediction error、selected goal change。
- 保证 policy/plasticity 不能绕过 gate。

## Unknowns to eliminate

- 当前 trace 是否足够解释 ranking delta。
- negative outcome 是否稳定提升 repair/replan。
- positive verify outcome 是否稳定降低 verify pressure。

## Acceptance criteria

- [x] 失败 feedback 使 repair/replan 排名上升。
- [x] verify success 使 verify pressure 下降。
- [x] 同一输入重复运行得到相同 result 和 ranking delta。
- [x] no outcome 时 selected intention 不任意变化。
- [x] 所有 action 仍 `no_action_executed=true`。

## Disallowed premature claims

- 不得宣称主动性已进入 runtime。
- 不得宣称真实学习效果或 live user benefit。
- 不得宣称 consciousness / alive。

## Known risks / dependencies

- 风险：测试只验证字段变化，不验证策略竞争。
- 依赖：Stage 0 operator report 能解释 kernel trace。
- 外部 blocker：Stage 0 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/agency_kernel.py`
- `ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py`
- `docs/codex/tasks/v7-stage-0-operator-observability/STATUS.md`
