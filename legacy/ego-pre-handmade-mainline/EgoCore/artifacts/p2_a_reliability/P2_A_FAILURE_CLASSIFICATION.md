# P2-A T3: 统一失败归因与分级

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 失败分类体系

### 1.1 Transient (可重试)

| 分类 | 含义 | 自动重试 |
|------|------|---------|
| `TIMEOUT` | 操作超时 | ✅ |
| `ENVIRONMENT_ERROR` | 环境/网络问题 | ✅ |
| `MODEL_ERROR` | LLM/模型调用失败 | ✅ |

### 1.2 Persistent (需修复)

| 分类 | 含义 | 用户操作 |
|------|------|---------|
| `VALIDATION_ERROR` | 输入验证失败 | 修正输入 |
| `PERMISSION_ERROR` | 权限不足 | 检查权限 |
| `NOT_FOUND` | 资源不存在 | 检查路径 |
| `UNSUPPORTED` | 操作不支持 | 使用其他方式 |
| `TOOL_ERROR` | 工具执行失败 | 检查参数 |

### 1.3 Safety (安全拦截)

| 分类 | 含义 | 用户操作 |
|------|------|---------|
| `SAFETY_BLOCK` | 安全规则拦截 | 需要确认 |

### 1.4 Logic (任务问题)

| 分类 | 含义 | 用户操作 |
|------|------|---------|
| `TASK_LOGIC_ERROR` | 任务规划问题 | 重新规划 |

---

## 2. 失败归因流程

```
Exception 发生
      ↓
classify_error(error) → FailureClass
      ↓
should_retry(failure_class) → RetryHint
      ↓
UnifiedExecutionResult.failure_result(...)
      ↓
写入: task memory / event log / /report
```

---

## 3. 各分类的恢复建议

### 3.1 Transient 失败

```python
{
    "failure_class": "timeout",
    "user_message": "操作超时，正在自动重试...",
    "next_action": "系统将自动重试，无需操作",
    "retry_hint": {
        "retryable": true,
        "max_retries": 3,
        "current_retry": 1
    }
}
```

### 3.2 Persistent 失败

```python
{
    "failure_class": "validation_error",
    "user_message": "输入验证失败",
    "next_action": "请检查输入参数并重试",
    "retry_hint": {
        "retryable": false
    }
}
```

### 3.3 Safety 失败

```python
{
    "failure_class": "safety_block",
    "user_message": "危险操作被阻止",
    "next_action": "如需执行，请使用 /confirm 确认",
    "retry_hint": {
        "retryable": false
    }
}
```

---

## 4. 与现有系统集成

### 4.1 Task Memory

失败信息自动写入 task memory:

```python
task_memory.record_failure(
    task_id=task.id,
    failure=f"[{failure_class.value}] {summary}",
    step=current_step.description
)
```

### 4.2 /report

`/report` 显示失败归因:

```
❌ 失败原因: [timeout] API 调用超时
📊 失败分类: 瞬态失败 (可重试)
🔄 重试状态: 第 2/3 次重试
💡 建议: 系统将自动重试
```

### 4.3 /resume

`/resume` 根据失败类型给出恢复建议:

```python
if failure_class in RETRYABLE_CLASSES:
    suggestion = "建议: 使用 /retry 重试"
else:
    suggestion = "建议: 检查错误并修正后重试"
```

---

## 5. 验收标准

- [x] 定义 FailureClass 枚举
- [x] 实现 classify_error 函数
- [x] 实现 should_retry 函数
- [x] 失败信息写入 task memory
- [x] /report 显示失败归因
- [x] /resume 根据失败类型给建议
