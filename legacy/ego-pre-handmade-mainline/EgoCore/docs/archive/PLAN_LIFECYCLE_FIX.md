# Plan Lifecycle Management 修复说明

## 本轮修复范围

本轮只修宿主层 plan lifecycle management：

- plan_steps consume
- task completion boundary
- new request vs follow-up classifier
- active_target rebinding

## 已实现规则

### R1. plan_steps 消费制
- 每次成功执行当前 step 后，从 `plan_steps` 正式出队
- 执行器只消费剩余步骤，不重复消费历史步骤

### R2. task completion boundary
- 当 `plan_steps == []` 时，当前 task 自动关闭
- 默认清空：`active_task_id / task_plan / targets / completed_steps`
- 仅保留 artifact context / last observation 供 follow-up 使用

### R3. new request vs follow-up classifier
- 明确路径 => `new_task`
- 相对表达（再大一点 / 看一下 / 继续等）=> `follow_up`
- 有剩余 plan_steps 的 active task => `follow_up`
- 其他情况 => `new_task`

### R4. active_target rebinding
- 消息中出现明确路径时，强制覆盖 `active_target` 和 `active_artifact_path`
- 新任务默认不开旧 plan

## 预期效果

- 旧 plan 不会重复套用
- completed task 不会被普通新请求继续执行
- 明确路径会强制重绑 target
- relative follow-up 仅继承 artifact context，不继承已消费完的旧 steps
