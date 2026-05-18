# P2-A T5: Task State Durability

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 状态流转图

```
CREATED ──→ PLANNING ──→ RUNNING ──→ COMPLETED
                              │
                              ├──→ PAUSED
                              │      │
                              │      └──→ RUNNING (resume)
                              │
                              ├──→ BLOCKED
                              │      │
                              │      ├──→ RUNNING (retry)
                              │      └──→ FAILED
                              │
                              ├──→ PARTIAL
                              │      │
                              │      └──→ RUNNING (continue)
                              │
                              └──→ FAILED
                                     │
                                     └──→ RUNNING (retry)
```

---

## 2. 状态流转条件

| 从 | 到 | 触发条件 | 持久化动作 |
|---|---|---------|----------|
| CREATED | PLANNING | plan_task() | checkpoint, memory |
| PLANNING | RUNNING | start_task() | checkpoint |
| RUNNING | COMPLETED | 所有步骤完成 | checkpoint, memory, 事件 |
| RUNNING | PAUSED | pause_task() | checkpoint, memory |
| RUNNING | BLOCKED | 步骤失败(可恢复) | checkpoint, memory, 失败记录 |
| RUNNING | FAILED | 步骤失败(不可恢复) | checkpoint, memory, 失败记录 |
| RUNNING | PARTIAL | 部分完成 | checkpoint, memory |
| PAUSED | RUNNING | resume_task() | memory |
| BLOCKED | RUNNING | retry_step() | memory |
| FAILED | RUNNING | retry_step() | memory |
| PARTIAL | RUNNING | continue | memory |

---

## 3. 每次流转必做

1. **写 Checkpoint**
   ```python
   checkpoint_manager.create_checkpoint(task, metadata)
   ```

2. **写 Task Memory**
   ```python
   task_memory.save_task_memory(
       task_id, objective, status, progress,
       next_steps, failures, ...
   )
   ```

3. **写 Event Log**
   ```python
   event_logger.log_event(
       EventType.TASK_STATUS_CHANGE,
       {"from": old_status, "to": new_status},
       task_id
   )
   ```

4. **更新数据库**
   ```python
   task_repo.update(task)
   ```

---

## 4. 失败点保留

当任务进入 BLOCKED/FAILED 状态时:

```python
# 保存失败证据
task.memory["failure_point"] = {
    "step_id": current_step.id,
    "step_description": current_step.description,
    "failure_class": failure_class.value,
    "error_message": error,
    "timestamp": datetime.now().isoformat(),
    "retry_hint": retry_hint.to_dict() if retry_hint else None
}

# 不会被 resume 覆盖
task.memory["preserved_errors"] = task.memory.get("preserved_errors", [])
task.memory["preserved_errors"].append(failure_point)
```

---

## 5. 恢复链完整性

```
Resume 时检查:
1. task.memory 存在? → 获取上下文
2. checkpoint 存在? → 恢复状态
3. failure_point 存在? → 从失败点继续
4. preserved_errors 存在? → 显示历史失败
```

---

## 6. 验收标准

- [x] 定义状态流转条件
- [x] 每次流转写 checkpoint
- [x] 每次流转写 memory
- [x] 每次流转写 event log
- [x] 失败点不被覆盖
- [x] 恢复链完整
