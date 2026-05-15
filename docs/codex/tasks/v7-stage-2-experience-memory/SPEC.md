# v7 Stage 2 - Experience Memory

## Goal

把记忆从记录历史升级成可影响未来行为的经验。

## Non-goals

- 不写 OpenEmotion memory。
- 不接 runtime persistence。
- 不实现 broad long-term user memory。
- 不绕过 gate 改变 action permission。

## Constraints

- 边界约束：lab-only memory，默认 in-memory 或测试 `tmp_path`。
- 仓库/子仓约束：只允许改 `ego_desktop_lab` 与本任务目录。
- 环境约束：所有经验更新必须 replayable。
- 发布约束：只能声明 lab experience-memory behavior。

## Problem framing

- 当前问题表述：agent 有 outcome，但未必形成可复用经验。
- 归一化后的问题表述：把 outcome/root-cause ticket 转成可检索、可降权、可反证的 `ExperienceCard`。
- 为什么这个 framing 更适合当前任务：学习能力的最小证据不是记住文本，而是相似场景倾向改变。

## Implementation method

- 新增 lab-only `experience_memory.py`。
- 定义 `ExperienceCard`: context, action, outcome, lesson, confidence, applicability, decay。
- 从 outcome/root-cause ticket 生成 experience。
- policy 可读取 experience bias，但不能绕过 gate。

## Unknowns to eliminate

- 相似性第一版采用 deterministic / embedding-free signature。
- 冲突经验按同 context + strategy 的正负 valence 标为 `needs_review`，本轮不施加 bias。
- experience bias 接入 kernel 的现有 `initial_pressure_bias` 和 prediction confidence overlay，不写回 `StrategyMemoryBank`。

## Acceptance criteria

- [x] 正反馈提升相似 option score。
- [x] 负反馈降低失败 strategy。
- [x] 无关经验不影响 ranking。
- [x] 冲突经验降权或标为 `needs_review`。
- [x] experience 更新可 deterministic replay。
- [x] gate status 不因 experience 改变为越权 allow。
- [x] operator 可用临时 JSON case 验证新场景，不需要改 repo fixture。
- [x] operator report 直接展示 before/after behavior、rank、priority delta、gate 和 `no_action_executed`。
- [x] operator JSON case loader 兼容 PowerShell UTF-8 BOM。
- [x] operator 可用 Markdown 聊天语料 case 验证中文/英文反馈，不需要手写 JSON。

## Disallowed premature claims

- 不得宣称长期人格记忆已实现。
- 不得宣称跨 session runtime 学习已实现。
- 不得宣称用户受益或真实电脑技能学习。

## Known risks / dependencies

- 风险：experience memory 变成第二套 StrategyMemory。
- 依赖：Stage 1 的 cycle trace contract。
- 外部 blocker：Stage 1 未通过前不得激活。

## Authority refs

- `ego_desktop_lab/strategy_memory.py`
- `ego_desktop_lab/root_cause.py`
- `docs/codex/tasks/v7-stage-1-deterministic-agency-kernel/STATUS.md`
