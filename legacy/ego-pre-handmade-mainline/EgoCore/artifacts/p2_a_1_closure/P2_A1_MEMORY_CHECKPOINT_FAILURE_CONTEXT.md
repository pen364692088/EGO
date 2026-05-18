# P2-A.1 Memory/Checkpoint 失败上下文

**日期**: 2026-03-13

---

## 1. 失败信息写入流程

```
Step 执行失败
      ↓
UnifiedExecutionResult.failure_result()
      ↓
_save_task_memory()
      ↓
┌─────────────────────────────────────┐
│  Task Memory 写入:                  │
│  - failure_class                    │
│  - summary                          │
│  - retry_hint                       │
│  - blocker                          │
│  - next_steps                       │
└─────────────────────────────────────┘
      ↓
Checkpoint 保存
      ↓
Event Log 记录
```

---

## 2. Task Memory 失败字段

### 2.1 写入内容

```python
task_memory.save_task_memory(
    task_id=task.id,
    objective=task.objective,
    status=task.status.value,
    progress="1/3 steps (33%) - Step 2 failed",
    next_steps=["重试 API 调用", "处理结果"],
    failures=["[timeout] API 调用超时"],
    decisions=[],
    completed_steps=["读取配置文件"],
    current_step="调用 API",
    context={
        "failure_class": "timeout",
        "retryable": True,
        "retry_count": 1
    }
)
```

### 2.2 读取恢复上下文

```python
resume_ctx = task_memory.build_resume_context(task_id)

# 返回:
{
    "has_memory": True,
    "objective": "任务目标",
    "status": "blocked",
    "failures": ["[timeout] API 调用超时"],
    "next_steps": ["重试 API 调用", "处理结果"],
    "context": {
        "failure_class": "timeout",
        "retryable": True
    }
}
```

---

## 3. Checkpoint 失败上下文

### 3.1 写入内容

```python
checkpoint_manager.create_checkpoint(task, {
    "failed_step": step.id,
    "failure_class": "timeout",
    "error": "API 调用超时",
    "retry_hint": {
        "retryable": True,
        "current_retry": 1,
        "max_retries": 3
    }
})
```

### 3.2 恢复时读取

```python
checkpoint = checkpoint_manager.get_latest_checkpoint(task_id)

# 恢复逻辑
if checkpoint.get("failure_class") == "timeout":
    if checkpoint.get("retry_hint", {}).get("retryable"):
        # 自动重试或建议重试
        pass
```

---

## 4. /resume 恢复语义

### 4.1 旧行为 (不推荐)

```python
# 只是恢复到 running
task.status = TaskStatus.RUNNING
```

### 4.2 新行为 (推荐)

```python
# 1. 读取失败上下文
resume_ctx = task_memory.build_resume_context(task_id)

# 2. 根据 failure_class 决定恢复策略
if resume_ctx.get("context", {}).get("retryable"):
    # 可重试失败
    message = f"上次失败: {failures[-1]}\n建议: 使用 /retry 重试"
else:
    # 需要人工干预
    message = f"上次失败: {failures[-1]}\n建议: {next_steps[0]}"

# 3. 返回恢复诊断
return CommandResult(
    message=f"▶️ *Task Resumed*\n\n{message}",
    data={
        "failure_class": resume_ctx.get("context", {}).get("failure_class"),
        "retryable": resume_ctx.get("context", {}).get("retryable")
    }
)
```

---

## 5. 证据保留规则

### 5.1 不覆盖原始错误

```python
# 错误追加而非覆盖
task.memory["preserved_errors"] = task.memory.get("preserved_errors", [])
task.memory["preserved_errors"].append({
    "step": step.description,
    "failure_class": failure_class.value,
    "error": error,
    "timestamp": datetime.now().isoformat()
})
```

### 5.2 重试记录

```python
# 记录重试历史
task.memory["retry_history"] = task.memory.get("retry_history", [])
task.memory["retry_history"].append({
    "attempt": current_retry,
    "result": "success" if success else "failed",
    "timestamp": datetime.now().isoformat()
})
```

---

## 6. 验收标准

| 场景 | 期望行为 |
|------|---------|
| 失败后 /report | 显示 failure_class, blocker, next_steps |
| 失败后 /resume | 显示恢复上下文和建议 |
| 重启后恢复 | 能读取失败语义 |
| 多次重试 | 保留所有失败证据 |
