# v7 Stage 3 - Behavior Option Framework

## Goal

让行为来自 registered option competition，而不是散落 if/else。

## Non-goals

- 不实现 LLM planner。
- 不实现真实工具执行。
- 不新增 runtime permission class。
- 不改 EgoCore/OpenEmotion。

## Constraints

- 边界约束：option 只表达 proposal，不执行动作。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：option registry 必须 deterministic。
- 发布约束：只能声明 lab-only option selection。

## Problem framing

- 当前问题表述：行为选项可能只是 intention 的包装。
- 归一化后的问题表述：建立可注册、可审计、可 gate 的 option contract。
- 为什么这个 framing 更适合当前任务：主动行为必须来自可竞争 option，而不是单条规则。

## Implementation method

- 扩展 `behavior_options.py`。
- 固定三类：`primitive`、`skill_option`、`plan_option`。
- 每个 option 必须有 affordance、expected effect、risk、cost、permission class、rollback note。
- kernel 只选择 registered options。

## Unknowns to eliminate

- 当前 `BehaviorOption` 是否已有足够字段。
- registry 应是静态表还是 builder contract。
- operator report 是否能展示 option contract。

## Acceptance criteria

- [ ] 未注册 option 不可被选择。
- [ ] 同一 option contract 可被 operator report 显示。
- [ ] high risk option 必须被 gate block/ask。
- [ ] proposal-only option 不执行外部动作。
- [ ] option selection deterministic。

## Disallowed premature claims

- 不得宣称 planning agent 已完成。
- 不得宣称 tool-use autonomy。
- 不得宣称 real action capability。

## Known risks / dependencies

- 风险：registry 与 intention specs 分叉。
- 依赖：Stage 2 experience bias contract。
- 外部 blocker：Stage 2 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/behavior_options.py`
- `ego_desktop_lab/policy.py`
- `docs/codex/tasks/v7-stage-2-experience-memory/STATUS.md`
