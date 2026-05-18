# P2-A 变更文件清单

**日期**: 2026-03-13

## 新增代码文件

| 文件 | 说明 |
|-----|------|
| `app/runtime/execution_result.py` | 统一执行结果模型 |
| `app/runtime/tool_doctor.py` | Preflight 和 Tool Doctor |

## 新增文档文件

| 文件 | 说明 |
|-----|------|
| `artifacts/p2_a_reliability/P2_A_EXECUTION_MODEL_SPEC.md` | 执行模型规范 |
| `artifacts/p2_a_reliability/P2_A_TOOL_PREFLIGHT_AND_DOCTOR.md` | Preflight 规范 |
| `artifacts/p2_a_reliability/P2_A_FAILURE_CLASSIFICATION.md` | 失败分类规范 |
| `artifacts/p2_a_reliability/P2_A_RETRY_POLICY.md` | 重试策略规范 |
| `artifacts/p2_a_reliability/P2_A_TASK_STATE_DURABILITY.md` | 状态持久化规范 |
| `artifacts/p2_a_reliability/P2_A_TOOL_GOVERNANCE_MATRIX.md` | 工具治理矩阵 |
| `artifacts/p2_a_reliability/P2_A_E2E_RELIABILITY_PROOF.md` | 稳定性验证 |

## 核心变更

### 1. UnifiedExecutionResult

统一所有执行操作的结果模型:
- 定义 `ExecutionStatus` 枚举 (success, blocked, failed, partial, unsafe, retryable)
- 定义 `FailureClass` 枚举 (11 种失败分类)
- 提供工厂方法 `success_result()`, `failure_result()`, `blocked_result()`
- 提供向后兼容 `to_legacy()` 方法

### 2. ToolPreflight

工具执行前检查:
- 参数校验
- 路径边界检查
- 命令危险度检查
- 输入大小检查
- 超时配置检查

### 3. ToolDoctor

工具诊断和建议:
- 运行 preflight 检查
- 返回 UnifiedExecutionResult
- 提供错误修复建议

### 4. classify_error()

异常自动分类函数，将 Python 异常映射到 FailureClass。

### 5. should_retry()

根据 FailureClass 返回 RetryHint，定义重试策略。

## 未修改文件

以下文件在 P2-A 中未修改（仅添加规范）:
- `app/runtime/task_runtime.py` - 可在后续集成统一结果模型
- `app/command_router.py` - 可在后续集成诊断输出
- `app/tools/*.py` - 可在后续集成 preflight
