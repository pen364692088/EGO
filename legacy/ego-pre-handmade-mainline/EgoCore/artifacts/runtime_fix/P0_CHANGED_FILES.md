# P0 Changed Files

## 改动文件列表

### 1. `app/telegram_bot.py`
**改动**: 添加 `run` 到命令注册列表

**目的**: 确保 `/run` 命令能被 Telegram bot 正确处理

**改动行数**: 1 行

```python
# Line 147-151
commands = [
    "start", "help", "new", "run", "status", "tasks", "resume",
    "pause", "retry", "abort", "report", "memory"
]
```

---

### 2. `app/command_router.py`
**改动**: 重写 `handle_natural_language()` 函数

**目的**: 防止自然语言消息默认创建任务

**改动行数**: +60 行

**关键变更**:
- 添加问候语检测逻辑
- 添加任务意图检测逻辑
- 不再直接调用 `_handle_new()`
- 返回分类响应（问候/状态/提示/聊天）

---

### 3. `app/runtime/task_runtime.py`
**改动**: 
1. 添加 event logger 和 checkpoint 接入
2. 修复 LLM 失败时的假成功问题

**目的**: 
1. 确保事件记录和 checkpoint 真正落盘
2. 失败时正确标记状态

**改动行数**: +55 行

**关键变更**:
- `create_task()`: 添加 TASK_CREATED 事件 + 初始 checkpoint
- `execute_next_step()`: 添加 STEP_STARTED/COMPLETED/FAILED 事件
- `_complete_task()`: 添加 TASK_COMPLETED 事件 + 最终 checkpoint
- `_default_executor()`: LLM 失败返回 `success=False`

---

### 4. `config/llm.yaml`
**改动**: 配置百度千帆为默认 LLM 提供商

**目的**: 使用用户指定的 LLM 服务

**改动行数**: 配置变更

---

## 总计

| 文件 | 新增行 | 删除行 |
|------|--------|--------|
| `telegram_bot.py` | 1 | 1 |
| `command_router.py` | 60 | 17 |
| `task_runtime.py` | 55 | 10 |
| `llm.yaml` | 配置变更 | - |
| **总计** | ~116 | ~28 |
