# P2-A.1 Runtime 集成

**日期**: 2026-03-13

---

## 1. 统一结果模型集成

### 1.1 导入

```python
from app.runtime.execution_result import (
    UnifiedExecutionResult, ExecutionStatus, FailureClass,
    ExecutionEvidence, RetryHint, classify_error, should_retry
)
from app.runtime.tool_doctor import run_preflight, get_doctor
```

### 1.2 ExecutionResult 重构

`ExecutionResult` 现在是 `UnifiedExecutionResult` 的向后兼容包装器:

```python
class ExecutionResult:
    """Legacy wrapper for UnifiedExecutionResult."""
    
    @classmethod
    def from_unified(cls, result: UnifiedExecutionResult) -> "ExecutionResult"
    
    def to_unified(self) -> UnifiedExecutionResult
```

---

## 2. 执行路径

### 2.1 _execute_step

```python
def _execute_step(self, step: TaskStep) -> ExecutionResult:
    # 执行统一结果模型
    unified_result = self._default_executor_unified(step)
    # 转换为向后兼容格式
    return ExecutionResult.from_unified(unified_result)
```

### 2.2 _default_executor_unified

新方法，使用 preflight 和统一结果模型:

```python
def _default_executor_unified(self, step: TaskStep) -> UnifiedExecutionResult:
    # 1. Preflight 检查
    preflight_result = run_preflight(tool_name, params)
    if not preflight_result.success:
        return preflight_result  # 返回 blocked/unsafe
    
    # 2. 执行工具
    tool_result = tool_registry.execute(tool_name, params)
    
    # 3. 返回统一结果
    if tool_result.success:
        return UnifiedExecutionResult.success_result(...)
    else:
        return UnifiedExecutionResult.failure_result(...)
```

---

## 3. Preflight 集成

| 操作 | Preflight 检查 |
|-----|---------------|
| file:read | 路径边界、文件存在 |
| file:list | 目录存在 |
| shell:* | 危险命令检测 |

---

## 4. 失败分类

执行失败自动分类:

```python
failure_class = classify_error(exception)
retry_hint = should_retry(failure_class)
```

---

## 5. 向后兼容

现有代码继续工作:

```python
# 旧代码
result = ExecutionResult(success=True, output="...")

# 转换
unified = result.to_unified()
legacy = ExecutionResult.from_unified(unified)
```
