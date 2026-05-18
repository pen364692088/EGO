# P2-A T1: 统一执行结果模型规范

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 概述

所有执行操作（task step、tool 调用、resume/retry）现在使用统一的 `UnifiedExecutionResult` 模型，确保：

- 一致的状态表示
- 可追溯的失败归因
- 用户友好的消息
- 明确的重试建议

---

## 2. 执行状态 (ExecutionStatus)

| 状态 | 含义 | 终止性 |
|------|------|--------|
| `SUCCESS` | 执行成功 | 是 |
| `BLOCKED` | 被前置条件阻止 | 是 |
| `FAILED` | 终端失败 | 是 |
| `PARTIAL` | 部分完成 | 否 |
| `UNSAFE` | 安全边界违规 | 是 |
| `RETRYABLE` | 可重试的临时失败 | 否 |

---

## 3. 失败分类 (FailureClass)

| 分类 | 含义 | 默认重试 |
|------|------|---------|
| `TOOL_ERROR` | 工具执行失败 | 否 |
| `MODEL_ERROR` | LLM/模型失败 | 是 |
| `ENVIRONMENT_ERROR` | 外部环境问题 | 是 |
| `VALIDATION_ERROR` | 输入验证失败 | 否 |
| `SAFETY_BLOCK` | 安全规则拦截 | 否 |
| `TIMEOUT` | 操作超时 | 是 |
| `PERMISSION_ERROR` | 权限不足 | 否 |
| `NOT_FOUND` | 资源不存在 | 否 |
| `UNSUPPORTED` | 操作不支持 | 否 |
| `TASK_LOGIC_ERROR` | 任务规划问题 | 否 |
| `UNKNOWN` | 未分类失败 | 否 |

---

## 4. 结果对象结构

```python
@dataclass
class UnifiedExecutionResult:
    # 核心状态
    status: ExecutionStatus
    summary: str
    
    # 失败详情
    failure_class: Optional[FailureClass]
    
    # 证据
    evidence: ExecutionEvidence
    
    # 用户消息
    user_safe_message: str
    next_recommended_action: Optional[str]
    
    # 重试信息
    retry_hint: Optional[RetryHint]
    
    # 输出
    output: Optional[str]
```

---

## 5. 使用示例

### 5.1 成功结果

```python
result = UnifiedExecutionResult.success_result(
    summary="文件读取成功",
    output=file_content,
    evidence=ExecutionEvidence(
        operation="file.read",
        tool_name="file"
    )
)
```

### 5.2 可重试失败

```python
result = UnifiedExecutionResult.failure_result(
    summary="API 调用超时",
    failure_class=FailureClass.TIMEOUT,
    user_safe_message="操作超时，正在重试...",
    retry_hint=RetryHint(
        retryable=True,
        max_retries=3,
        current_retry=1
    )
)
```

### 5.3 安全阻止

```python
result = UnifiedExecutionResult.blocked_result(
    summary="危险命令被阻止",
    failure_class=FailureClass.SAFETY_BLOCK,
    reason="rm -rf 命令需要确认",
    next_action="如需执行，请使用 /confirm 确认"
)
```

---

## 6. 向后兼容

`UnifiedExecutionResult` 提供 `to_legacy()` 方法返回 `(success, output, error)` 元组，与现有代码兼容。

---

## 7. 集成点

以下组件必须使用统一结果模型：

1. `TaskRuntime.execute_next_step()` - 步骤执行
2. `Tool.execute()` - 工具调用
3. `TaskRuntime.resume_task()` - 任务恢复
4. `TaskRuntime.retry_step()` - 步骤重试

---

## 8. 验收标准

- [x] 定义统一状态枚举
- [x] 定义失败分类枚举
- [x] 实现 UnifiedExecutionResult 类
- [x] 提供 factory 方法 (success_result, failure_result, blocked_result)
- [x] 提供向后兼容接口
- [x] 实现 classify_error 辅助函数
- [x] 实现 should_retry 辅助函数
