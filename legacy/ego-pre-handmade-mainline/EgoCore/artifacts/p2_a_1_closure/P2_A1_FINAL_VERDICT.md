# P2-A.1 最终裁决 (真正收口)

**裁决日期**: 2026-03-13  
**裁决人**: Moonlight

---

## 验收清单

| # | 任务 | 状态 | 真实证据 |
|---|------|------|---------|
| T1 | 替换 task_runtime 主结果模型 | ✅ | execute_next_step_unified() 返回 UnifiedExecutionResult |
| T2 | tool_doctor/preflight 接入 tools | ✅ | shell_tool.py, file_tool.py 调用 run_preflight() |
| T3 | 统一失败分类驱动 task state | ✅ | 失败后 status 由 failure_class 决定 |
| T4 | 增强诊断输出 | ✅ | UnifiedExecutionResult 包含所有诊断字段 |
| T5 | 清理旧链路入口 | ✅ | ExecutionResult 成为向后兼容包装器 |
| T6 | failure/retry/blocker 写入 memory | ✅ | _save_task_memory() 保存失败上下文 |
| T7 | 真实主链接线回归 | ✅ | 7/7 E2E 测试通过 |

---

## 核心验证结果 (E2E 真实测试)

| 测试 | 结果 | 证据 |
|------|------|------|
| file_tool_preflight_pass | ✅ | README.md 读取成功 |
| file_tool_preflight_block | ✅ | /etc/passwd 被 preflight 拦截 |
| shell_tool_preflight_pass | ✅ | echo test 执行成功 |
| shell_tool_preflight_block | ✅ | rm -rf / 被 preflight 拦截 |
| task_runtime_unified_result | ✅ | 返回 UnifiedExecutionResult 类型 |
| failure_class_retry_hint | ✅ | timeout 可重试, safety_block 不可重试 |
| diagnostic_output_complete | ✅ | 包含 status, failure_class, user_message, next_action, retry_hint |

---

## 真正的代码修改

### 1. task_runtime.py

```python
# 新增方法 - 返回 UnifiedExecutionResult
def execute_next_step_unified(self, task_id: str) -> tuple[Task, UnifiedExecutionResult]:
    # 执行步骤
    result = self._execute_step_unified(current_step)
    
    # 根据失败分类决定状态
    if result.failure_class == FailureClass.SAFETY_BLOCK:
        task.status = TaskStatus.BLOCKED
    elif result.is_retryable:
        task.status = TaskStatus.BLOCKED  # 可重试
    else:
        task.status = TaskStatus.FAILED
```

### 2. shell_tool.py

```python
def execute(self, params: Dict[str, Any]) -> ToolResult:
    # P2-A.1: Preflight check via tool_doctor
    from app.runtime.tool_doctor import run_preflight
    preflight_result = run_preflight("shell", params)
    if not preflight_result.success:
        return ToolResult.denied_result(preflight_result.user_safe_message)
    # ... 继续执行
```

### 3. file_tool.py

```python
def execute(self, params: Dict[str, Any]) -> ToolResult:
    # P2-A.1: Preflight check via tool_doctor
    from app.runtime.tool_doctor import run_preflight
    preflight_result = run_preflight("file", params)
    if not preflight_result.success:
        return ToolResult.denied_result(preflight_result.user_safe_message)
    # ... 继续执行
```

---

## 与之前版本的区别

| 修改点 | 之前 (虚假) | 现在 (真实) |
|-------|-----------|-----------|
| task_runtime 返回类型 | ExecutionResult | UnifiedExecutionResult |
| shell_tool preflight | 无 | run_preflight() 在 execute() 开头 |
| file_tool preflight | 无 | run_preflight() 在 execute() 开头 |
| 失败状态流转 | 统一 BLOCKED | 根据 failure_class 决定 |
| 诊断字段 | 部分 | 完整 (status, failure_class, retry_hint, next_action) |

---

## 当前限制 (属于 P2-B)

- 自动重试运行时集成
- Python 工具 preflight 增强
- Heartbeat/cron 自动恢复
- 多 Agent 编排

---

## 裁决结论

# ✅ P2-A.1 主链接线已真正收口，可进入 P2-B

**理由**:
1. task_runtime.py 真正返回 UnifiedExecutionResult
2. shell_tool.py 真正调用 preflight
3. file_tool.py 真正调用 preflight
4. 7/7 E2E 测试通过
5. 旧链路不再吞错或伪装成功
