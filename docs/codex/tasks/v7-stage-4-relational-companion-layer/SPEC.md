# v7 Stage 4 - Relational Companion Layer

## Goal

实现高拟人陪伴的机制基础，但不靠 persona prompt 或 consciousness claim。

## Non-goals

- 不直接生成 runtime-visible Telegram reply。
- 不声明 alive / consciousness。
- 不实现依赖诱导或情绪操控。
- 不写 OpenEmotion state。

## Constraints

- 边界约束：输出 companion surface plan，不是 final runtime reply。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：安全 phrase / claim ceiling 必须可测试。
- 发布约束：只能声明 lab-only relational planning。

## Problem framing

- 当前问题表述：拟人度高可能被误做成 prompt/persona。
- 归一化后的问题表述：拟人互动来自关系状态、偏好、节奏、修复信号和安全表达边界。
- 为什么这个 framing 更适合当前任务：产品体验必须和 truthfulness/safety 分离。

## Implementation method

- 新增 lab-only relational state。
- 记录 user preference、interaction rhythm、trust/repair signals、conversation continuity。
- 输出 companion surface plan。
- 不自然/模板化归类到 root-cause `expression_surface`。

## Unknowns to eliminate

- 第一版 relational signals 取哪些字段。
- companion surface plan 如何接 operator report。
- 哪些 wording 必须被 safety gate 拦截。

## Acceptance criteria

- [ ] 用户偏好改变后续表达策略。
- [ ] 关系修复信号提升 repair/clarify option。
- [ ] 输出不包含 alive/consciousness claim。
- [ ] 不诱导依赖、不操控情绪、不伪装真实人类关系。
- [ ] operator report 显示 relational reason。

## Disallowed premature claims

- 不得宣称 AI 伴侣已上线。
- 不得宣称真实情感或主观体验。
- 不得宣称 live user benefit。

## Known risks / dependencies

- 风险：把 relational layer 写成 persona prompt。
- 依赖：Stage 3 option framework。
- 外部 blocker：Stage 3 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/root_cause.py`
- `ego_desktop_lab/behavior_options.py`
- `docs/codex/tasks/v7-stage-3-behavior-option-framework/STATUS.md`
