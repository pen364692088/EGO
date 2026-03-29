---
name: "ego-review-against-acceptance"
description: "Use when reviewing a diff, uncommitted changes, or a completed task against acceptance criteria, review rules, done definitions, verify task docs, release gates, or admission reviews. Do not use when the work still needs initial planning, first-pass implementation, or general context restoration. Boundary: this skill evaluates completion strength and missing proof; if a single prompt mixes continue/resume with verify, rejudge, release, or done-claim language, this skill should win over ego-resume-context."
---

# Ego Review Against Acceptance

先读：

1. `AGENTS.md`
2. 当前 acceptance / task status / review 文档
3. 相关 spec / plan
4. 变更 diff 或目标文件

必要时参考：

- `.agents/references/engineering-evidence-model.md`
- `.agents/references/task-state-and-handoff.md`

## Workflow

1. 先对照 acceptance，不先写概览。
2. findings-first 检查：
   - 是否命中当前范围
   - 是否留了匹配的验证
   - 是否有主链证据缺口
   - 是否有边界破坏、双重真相源、伪完成口径
   - 是否混入 scope 外改动
3. 区分：
   - 已证实
   - 条件成立但未证实
   - 明确未完成
4. 给出完成口径：
   - `可宣称完成`
   - `条件性完成`
   - `不可宣称完成`
5. 明确还差什么和下一步最小闭环动作。

## Output

优先输出 findings，按严重度排序。之后再给：

- completion class
- residual risks
- next action

## Boundary

- 默认不做首次实现。
- 若 review 发现 blocker，可以回修，但要先明确 blocker 再改。
