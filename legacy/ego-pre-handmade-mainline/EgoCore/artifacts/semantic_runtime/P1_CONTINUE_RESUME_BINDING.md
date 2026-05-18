# P1 Continue/Resume Binding

## Continue 类消息支持的说法

### 继续执行
- 继续
- 接着做
- 接着
- 继续做
- 继续执行
- 做完它
- 完成它

### 追问进展
- 还有呢
- 还有什么
- 接下来

### 任务询问
- 上个任务
- 上一个任务
- 刚才的任务
- 之前的任务
- 怎么样了
- 进展如何
- 完成了没

### 恢复操作
- 恢复
- resume

---

## 如何绑定 Active Task

### 绑定优先级

1. **当前活动任务** (running/blocked/paused)
   - 通过 `get_active_task()` 获取
   - 直接绑定并继续执行

2. **最近未完成任务**
   - 从任务列表中查找
   - 状态为 running/blocked/paused/planning
   - 按创建时间倒序选择第一个

3. **无可用任务**
   - 返回提示信息
   - 不创建新任务

---

## 绑定失败时的处理

当没有可继续的任务时：

```
📋 当前没有可继续的任务。

你可以直接告诉我你需要做什么，例如：
• 帮我检查项目问题
• 分析代码结构
```

**关键原则**:
- 不创建名为"继续"的新任务
- 不返回通用帮助模板
- 明确告知用户没有可继续的任务

---

## 与 /resume 共用逻辑

### 共享代码路径

```
用户输入"继续" 或 "/resume"
         ↓
  SemanticRouter.classify()
         ↓
  Intent = CONTINUE_TASK 或 COMMAND/resume
         ↓
  _handle_continue_intent() 或 _handle_resume()
         ↓
  共享同一套恢复逻辑:
  - get_active_task()
  - resume_task() if paused
  - execute_next_step()
```

### 关键差异

| 场景 | 自然语言"继续" | 命令 "/resume" |
|------|---------------|----------------|
| 触发 | 语义分类 | 命令解析 |
| 参数 | 无 | 可指定 task_id |
| 错误提示 | 友好建议 | 技术信息 |

---

## 实现细节

### 恢复逻辑

```python
def bind_and_continue(task):
    if task.status == "paused":
        resume_task(task.id)
    elif task.status == "blocked":
        retry_step(task.id)
    elif task.status == "running":
        execute_next_step(task.id)
    elif task.status in ["planning", "created"]:
        start_task(task.id)
        execute_next_step(task.id)
```

### 上下文恢复

从 checkpoint 和 memory 中恢复：
- 任务目标
- 已完成步骤
- 当前步骤描述
- 执行历史
