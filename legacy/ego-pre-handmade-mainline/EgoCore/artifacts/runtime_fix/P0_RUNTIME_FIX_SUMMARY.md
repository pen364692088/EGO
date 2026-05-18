# P0 Runtime Fix Summary

## 执行摘要

**状态**: P0 已闭环 ✅

---

## 根因与修复

### 根因 1: `/run` 命令未注册
**问题**: Telegram bot 命令列表中缺少 `run`，导致 `/run` 命令无法被处理。

**修复**: 在 `telegram_bot.py` 的命令列表中添加 `"run"`。

```python
# 修复前
commands = ["start", "help", "new", "status", "tasks", "resume", "pause", "retry", "abort", "report", "memory"]

# 修复后
commands = ["start", "help", "new", "run", "status", "tasks", "resume", "pause", "retry", "abort", "report", "memory"]
```

---

### 根因 2: 自然语言默认创建任务
**问题**: `handle_natural_language()` 会将任何自然语言消息当作任务创建请求，调用 `_handle_new()`。

**修复**: 重写 `handle_natural_language()` 函数，采用分类策略：
- 问候语 → 返回帮助信息
- 状态询问 → 返回当前任务状态
- 任务意图 → 提示使用 `/new`
- 其他 → 返回普通聊天回复

**关键代码变更**:
```python
# 修复前
return router._handle_new(new_ctx)  # 直接创建任务

# 修复后
if is_greeting:
    return CommandResult(message="👋 你好！我是 EgoCore 任务助手...")
    
if looks_like_task:
    return CommandResult(message="💡 这看起来像是一个任务请求。请使用 /new 创建任务...")
```

---

### 根因 3: 失败伪装成功
**问题**: 当 LLM 不可用时，执行器返回 `success=True` 并带有占位文本。

**修复**: LLM 失败时返回 `success=False`，状态正确标记为 `BLOCKED`。

```python
# 修复前
except Exception as llm_err:
    return ExecutionResult(
        success=True,
        output=f"步骤完成: {step.description}\n(注: LLM暂不可用)"
    )

# 修复后
except Exception as llm_err:
    return ExecutionResult(
        success=False,
        error=f"LLM 执行失败: {str(llm_err)[:100]}"
    )
```

---

### 根因 4: Event/Checkpoint 未接入主链
**问题**: 虽然模块存在，但主执行流程没有调用。

**修复**: 在关键节点添加调用：
- `create_task()` → 记录 TASK_CREATED 事件 + 创建 checkpoint
- `execute_next_step()` → 记录 STEP_STARTED/COMPLETED/FAILED 事件 + 保存 checkpoint
- `_complete_task()` → 记录 TASK_COMPLETED 事件 + 最终 checkpoint

---

## 验证结果

| 测试项 | 结果 |
|--------|------|
| T1: 命令注册 | ✅ `run` 已注册 |
| T2: 自然语言不创建任务 | ✅ "在吗" 不创建任务 |
| T3: /run 真执行 | ✅ 可执行步骤 |
| T4: 失败不伪装成功 | ✅ 返回 `success=False` |
| T5: 事件日志接入 | ✅ 有事件记录 |

---

## 结论

**P0 已闭环，可进入下一阶段**
