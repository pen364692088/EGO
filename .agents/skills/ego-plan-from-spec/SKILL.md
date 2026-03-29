---
name: "ego-plan-from-spec"
description: "Use when a task is complex, cross-module, ambiguous, expected to take more than about one hour, or needs phased delivery before coding, including repo design tasks and early layer3 dual-repo planning. Do not use when the change is a small scoped edit, a clear single-file bugfix, a review-only task, or the user already gave a precise milestone or step file and explicitly wants code changes now. Boundary: this skill plans and scopes the work; if a single prompt mixes plan and implement but the milestone is not yet locked, this skill should win and define the slice before coding."
---

# Ego Plan From Spec

先读：

1. `AGENTS.md`
2. `PROJECT_MEMORY.md`
3. `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
4. 当前任务相关的 spec / plan / acceptance / review / status
5. 触及目录对应的 `README.md` 或 owner 文档

必要时参考：

- `.agents/references/engineering-evidence-model.md`
- `.agents/references/task-state-and-handoff.md`

## Workflow

1. 锁定真实目标、非目标、authority source、成功判据。
2. 划清影响面：入口、owner、主链、受影响目录、外部依赖、回退点。
3. 标出关键风险：
   - 边界漂移
   - 双重真相源
   - contract/schema 失配
   - 主链未接入却被误报完成
4. 产出 milestones。每个 milestone 必须写：
   - 目标
   - 非目标
   - 受影响文件/目录
   - 验证命令
   - 完成标准
   - 回退点
5. 先指出最小决策点和最便宜的反证，不要直接默认大改。

## Output

默认输出一份简短、可执行的计划，至少包含：

- 当前任务类型
- real goal
- success criteria
- authority source
- milestones
- 每个 milestone 的验证命令与完成标准
- 当前 blocker / unknown
- 下一步最小闭环动作

## Boundary

- 默认不直接改代码。
- 如果用户已经明确要求“先规划再立即实现”，可以在计划后进入实现，但要先把当前 milestone 锁死。
- 不把计划写成大而空的愿景文档；必须服务当前任务。
