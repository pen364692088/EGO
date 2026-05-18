# P2-A.1 Router 诊断输出

**日期**: 2026-03-13

---

## 1. 增强的诊断输出

### 1.1 /report 输出字段

```
📊 *Task Report: task_xxx*

🎯 *Objective:* 任务目标
📌 *Status:* RUNNING/BLOCKED/FAILED
📅 *Created:* 2026-03-13 14:00
🚀 *Started:* 2026-03-13 14:00

📈 *Progress:* 1/3 steps (33%)

🔍 *Diagnostics:* (仅 BLOCKED/FAILED/PAUSED 状态)
❌ *Last Failure:* [timeout] API 调用超时
🚫 *Blocker:* 网络连接问题
💡 *Suggested Actions:*
   1. 检查网络连接
   2. 使用 /retry 重试
🔄 *Retry:* 使用 /retry 重试

*Steps:*
  ✅ 1. 读取配置文件
  ❌ 2. 调用 API * (当前失败)
  ⏳ 3. 处理结果
```

### 1.2 /resume 输出字段

```
▶️ *Task Resumed*

Task ID: `task_xxx`
Objective: 任务目标
Status: RUNNING

🔍 *Resume Context:*
- 上次卡在: 步骤 2 - 调用 API
- 失败原因: timeout
- 建议: 系统将自动重试

Use /run to continue execution.
```

---

## 2. 状态类自然语言回复

当用户发送"现在卡在哪了"、"任务怎么样"时:

```
📊 当前任务状态

🎯 目标: 读取 README.md
📌 状态: BLOCKED
📈 进度: 1/2 steps

🔍 诊断:
❌ 失败原因: [validation_error] 文件不存在
💡 建议: 检查文件路径是否正确
🔄 操作: 修正后使用 /retry
```

---

## 3. 诊断字段来源

| 字段 | 来源 |
|------|------|
| failure_class | UnifiedExecutionResult.failure_class |
| retry_hint | UnifiedExecutionResult.retry_hint |
| blocker | task.error / memory.failures |
| next_action | UnifiedExecutionResult.next_recommended_action |
| suggested_actions | memory.next_steps |

---

## 4. 实现位置

| 功能 | 文件 | 方法 |
|------|------|------|
| /report 诊断 | task_runtime.py | generate_report() |
| /resume 诊断 | command_router.py | _handle_resume() |
| 状态查询诊断 | command_router.py | _handle_continue_intent() |
