---
name: "ego-implement-milestone"
description: "Use when a milestone is already defined by a spec, plan, acceptance checklist, step file, or implementation task document and the job is to implement that scoped slice now, including published or in-progress layer2/layer3 task cards. Do not use when requirements are still ambiguous, planning is still needed, the task is review-only, or the user mainly wants context recovery before deciding whether to code. Boundary: this skill implements the current milestone only and must not expand scope on its own; if a single prompt mixes plan and implement but the implementation target is already fixed and the user explicitly wants code changes now, this skill should win."
---

# Ego Implement Milestone

先读：

1. `AGENTS.md`
2. 当前 milestone 对应的 spec / plan / acceptance / status
3. `PROJECT_MEMORY.md`
4. 相关目录的 README / owner 文档

必要时参考：

- `.agents/references/engineering-evidence-model.md`
- `.agents/references/task-state-and-handoff.md`

## Workflow

1. 明确当前只实现哪个 milestone，以及哪些内容不在 scope 内。
2. 确认 authority source、入口、主链位置、完成标准。
3. 若适用，先补或更新测试 / 最小复现；若不适用，要明确说明为什么。
4. 只做当前 milestone 的最小必要改动。
5. 运行该 milestone 的最小验证：
   - 语法 / 导入
   - 定向测试
   - 相关脚本或主链入口验证
6. 更新任务状态文件或状态报告。
7. 最后按 acceptance 做一次自检，确认哪些已证明、哪些未证明。

## Output

交付时至少说明：

- 当前 milestone
- 改了什么
- 跑了什么验证
- 是否达到 acceptance
- 还差什么
- 下一步最小闭环动作

## Boundary

- 不顺手推进下一个 milestone。
- 不把实现完成误报成主链闭环。
- 若发现当前 milestone 前提不成立，停下来并回到 planning。
