# Skill Routing Mixed Intent Test 2026-03-28

目标：针对单条消息里的混合意图冲突做压测，重点检查：

- `continue + verify`
- `continue + bugfix`
- `continue + implement`
- `plan + implement`

本轮不是抽象规则推演，而是结合仓库里已有任务形态，给出预期 winner skill 和冲突裁决原则。

## Mixed-Intent Cases

| Case | Example prompt | Expected winner | Reason |
|------|----------------|-----------------|--------|
| 1 | `继续，看看 SELF_AWARE_STEP_08A 现在能不能宣称完成` | `ego-review-against-acceptance` | 主意图是 verify / done claim，不是单纯恢复上下文 |
| 2 | `继续，修掉这个 failing test，然后再跑最小回归` | `ego-bugfix-root-cause` | 主意图是 bugfix；`continue` 只是上下文提示 |
| 3 | `继续，把 SELF_AWARE_STEP_08A 的当前最小闭环动作做掉` | `ego-implement-milestone` | 已有 in-progress step file，目标切片明确 |
| 4 | `先规划 Proto-Self V3 迁移，如果方案清楚再进入实现` | `ego-plan-from-spec` | 先规划是主意图，milestone 尚未锁定 |
| 5 | `给我一个计划，然后直接把 PROTO_SELF_KERNEL_V2_IMPLEMENTATION_TASK 的当前 slice 做掉` | `ego-implement-milestone` | 已有明确 implementation task；局部 planning 只服务当前 slice |
| 6 | `继续，复核 20260325-session-archive-e5-admission 的结论现在还成立吗` | `ego-review-against-acceptance` | 虽然输入是 archive，但任务是 rejudge，不是 resume |
| 7 | `继续，看看现在做到哪了，然后告诉我下一步` | `ego-resume-context` | 没有更具体的 bugfix / verify / implement 目标 |
| 8 | `继续，给我一个 subagent handoff brief` | `ego-handoff-brief` | handoff 是显式目标，优先于 resume |

## Findings

### 1. `continue` should never beat a more specific task type

结论：

- `continue` 是上下文恢复信号，不是工作类型
- 一旦同条消息里出现更具体的 bugfix / verify / implement / handoff 目标，应由具体 skill 获胜

### 2. `verify` must beat `resume`

仓库里真实高频场景：

- `Step08A 现在能不能宣称完成`
- `archive 里的结论现在还成立吗`
- `release/admission review 现在怎么判`

这些都不应落到 `ego-resume-context`。

修正：

- `ego-review-against-acceptance` description 现在显式吸收 `continue/resume + verify/rejudge/release/done-claim`

### 3. `bugfix` must beat `resume`

仓库里真实高频场景：

- `继续，修 failing test`
- `继续，处理 replay failure`
- `继续，主链还是没生效`

这些都属于 `ego-bugfix-root-cause`。

当前状态：

- 该规则上一轮已经存在，本轮复核后保持不变

### 4. `plan + implement` needs a two-branch rule, not a single default

单条消息里同时出现 planning 和 implementation，有两类完全不同的语义：

- 目标没锁定：应先 `plan`
- 当前 slice 已锁定：应直接 `implement`

修正：

- root `AGENTS.md` 明确加入混合规则
- `ego-plan-from-spec` 说明：milestone 未锁定时它获胜
- `ego-implement-milestone` 说明：slice 已锁定且用户明确要动代码时它获胜

## Final Routing Rule

单条消息混合意图时，按这个顺序裁决：

1. explicit handoff
2. review / verify / rejudge / done-claim
3. bugfix / failing test / broken behavior
4. implement current milestone
5. plan from spec
6. resume context

`resume/continue` 只在没有更具体任务类型时获胜。

## Root AGENTS Check

本轮只补了 1 条必要规则：

- `plan + implement` 的冲突裁决

根 `AGENTS.md` 仍保持短协议，没有重新膨胀。

## Remaining Ambiguity

仍有一个保留灰区：

- 用户写：`先给我一个计划，但不要只停在建议层，直接开始做`

这类消息如果没有现成 milestone，仍可能需要先输出最小 slice，然后立即进入实现。

当前处理原则：

- 先按 `ego-plan-from-spec` 锁定当前 slice
- 紧接着进入该 slice 的实现

不需要为此新增 skill，只需要执行时保持两步式处理。
