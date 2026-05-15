# v7 Stage 5 - Computer Skill Sandbox

## Goal

让 agent 开始学习任务/电脑操作技能，但只在 sandbox 中。

## Non-goals

- 不控制真实桌面。
- 不读写用户真实文件。
- 不发外部消息。
- 不接 OpenClaw / Telegram / EgoCore tool execution。

## Constraints

- 边界约束：只允许 observation / suggestion，不允许真实动作。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：sandbox task 必须 deterministic。
- 发布约束：只能声明 lab skill learning proxy。

## Problem framing

- 当前问题表述：想让 agent 学电脑操作，但真实桌面权限风险过高。
- 归一化后的问题表述：先在 scripted sandbox 中证明 skill attempt -> failure ticket -> experience update -> retry improvement。
- 为什么这个 framing 更适合当前任务：电脑技能需要先有安全训练场和失败归因。

## Implementation method

- 新增 lab-only skill task harness。
- 支持 scripted file/web/terminal toy tasks，但不触碰真实用户资源。
- 每个 skill 记录 attempt、observation、failure ticket、experience update。
- 所有危险动作走 gate block/ask。

## Unknowns to eliminate

- 第一版 sandbox task 类型。
- skill memory 是否复用 Stage 2 experience。
- 如何度量 success-rate improvement。

## Acceptance criteria

- [ ] 一个技能能通过多次反馈提升成功率或降低错误率。
- [ ] 失败能生成 root-cause ticket。
- [ ] skill memory 不污染 companion memory。
- [ ] 外部/文件危险动作被 gate block/ask。
- [ ] 所有 sandbox replay deterministic。

## Disallowed premature claims

- 不得宣称会操作用户电脑。
- 不得宣称真实 desktop automation。
- 不得宣称 live task benefit。

## Known risks / dependencies

- 风险：sandbox 变成真实工具旁路。
- 依赖：Stage 2 experience memory 和 Stage 3 option framework。
- 外部 blocker：Stage 4 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/root_cause.py`
- `docs/codex/tasks/v7-stage-2-experience-memory/STATUS.md`
- `docs/codex/tasks/v7-stage-4-relational-companion-layer/STATUS.md`
