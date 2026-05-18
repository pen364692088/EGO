# P2-A.1 Tool Preflight 集成

**日期**: 2026-03-13

---

## 1. Preflight 集成架构

```
step.description
      ↓
_default_executor_unified()
      ↓
run_preflight(tool_name, params)
      ↓
┌─────────────────────────────────────┐
│         Preflight Checks            │
│  - 参数合法性                        │
│  - 路径边界                          │
│  - 危险命令检测                      │
│  - 输入大小限制                      │
└─────────────────────────────────────┘
      ↓ (pass)           ↓ (fail)
tool_registry.execute()  return blocked_result
      ↓
UnifiedExecutionResult
```

---

## 2. 各工具 Preflight 集成

### 2.1 File 工具

```python
# 在 _default_executor_unified 中
if 'read' in step_desc or '读取' in step_desc:
    path = extract_path(step.description)
    
    # Preflight 检查
    preflight_result = run_preflight("file", {
        "operation": "read",
        "path": path
    })
    
    if not preflight_result.success:
        return preflight_result  # 返回 blocked/validation_error
    
    # 执行工具
    tool_result = tool_registry.execute("file", {...})
```

**检查项目**:
- ✅ 路径边界 (禁止 /etc, /root, /proc)
- ✅ 文件存在
- ✅ 输入大小限制

### 2.2 Shell 工具

```python
if 'run' in step_desc or 'execute' in step_desc:
    cmd = extract_command(step.description)
    
    # Preflight 检查
    preflight_result = run_preflight("shell", {"command": cmd})
    
    if not preflight_result.success:
        # 返回 unsafe/safety_block
        return UnifiedExecutionResult.blocked_result(
            summary="命令被安全检查拦截",
            failure_class=FailureClass.SAFETY_BLOCK,
            ...
        )
```

**检查项目**:
- ✅ 危险命令模式检测
- ✅ 超时配置
- ✅ 输出大小限制

### 2.3 Python 工具

```python
# Python 执行限制检查
preflight_result = run_preflight("python", {"code": code})
```

**检查项目**:
- ⏳ 危险导入检测
- ⏳ 代码长度限制
- ⏳ 执行超时

---

## 3. Preflight 返回结果

### 3.1 通过

```python
UnifiedExecutionResult.success_result(
    summary="Preflight checks passed",
    ...
)
```

### 3.2 阻止

```python
UnifiedExecutionResult.blocked_result(
    summary="Preflight check failed",
    failure_class=FailureClass.SAFETY_BLOCK,
    reason="危险命令被拦截",
    next_action="如需执行，请使用 /confirm 确认"
)
```

---

## 4. 验证测试

| 场景 | Preflight 结果 |
|------|---------------|
| 读取 README.md | ✅ 通过 |
| 读取 /etc/passwd | 🚫 路径边界阻止 |
| rm -rf / | 🚫 危险命令阻止 |
| wget ... \| sh | 🚫 下载执行阻止 |

---

## 5. 与 Semantic Router 协同

Preflight 和 Semantic Router 使用相同的高风险模式列表:

```python
# 共享模式
DANGEROUS_PATTERNS = [
    r"rm\s*-rf\s+/",
    r"mkfs",
    r"wget.*\|\s*sh",
    ...
]
```

**双重检查**:
1. Semantic Router - 自然语言意图检测
2. Preflight - 具体参数检查
