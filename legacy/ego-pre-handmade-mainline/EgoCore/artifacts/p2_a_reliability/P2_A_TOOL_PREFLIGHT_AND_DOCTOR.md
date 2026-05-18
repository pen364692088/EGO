# P2-A T2: Tool Preflight & Doctor 机制

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 概述

Preflight 机制在工具执行**前**进行检查，避免无效或危险操作进入执行阶段。

Tool Doctor 提供运行时诊断和建议。

---

## 2. Preflight 检查类型

| 检查类型 | 说明 | 严重级别 |
|---------|------|---------|
| `PARAMETER_VALIDATION` | 参数有效性 | error |
| `PATH_BOUNDARY` | 路径边界检查 | critical |
| `WORKING_DIRECTORY` | 工作目录检查 | error |
| `TIMEOUT_CONFIG` | 超时配置检查 | warning |
| `COMMAND_DANGER` | 命令危险度检查 | critical |
| `PYTHON_RESTRICTION` | Python 限制检查 | warning |
| `INPUT_SIZE` | 输入大小检查 | error |
| `OUTPUT_SIZE` | 输出大小检查 | warning |
| `DEPENDENCY_AVAILABILITY` | 依赖可用性检查 | error |
| `PERMISSION` | 权限检查 | error |

---

## 3. 工具特定检查

### 3.1 File 工具

- 路径边界检查（禁止访问 /etc, /root, /proc 等）
- 写权限检查（写操作前检查父目录权限）
- 文件存在检查（读操作前检查文件是否存在）
- 输入大小限制（最大 10MB）

### 3.2 Shell 工具

- 命令危险度检查（检测 rm -rf /, fork bomb 等）
- 工作目录检查（目录存在且可访问）
- 超时配置检查（最大 5 分钟）

### 3.3 Python 工具

- 危险导入检查（os.system, subprocess 等）
- 危险函数检查（eval, exec, compile 等）
- 文件操作检查（建议使用 file 工具）

---

## 4. 危险命令模式

以下模式会被 preflight 拦截：

```regex
rm\s+-rf\s+/           # rm -rf /
rm\s+-rf\s+~           # rm -rf ~
>\s*/dev/sd            # 写入磁盘设备
mkfs                   # 格式化磁盘
dd\s+if=.*of=/dev/     # dd 到设备
:()\s*{\s*:\|:&\s*}    # Fork bomb
chmod\s+777\s+/        # chmod 777 /
wget.*\|\s*sh          # 下载并执行
curl.*\|\s*sh          # 下载并执行
```

---

## 5. 受限路径

以下路径禁止访问：

- `/etc/passwd`
- `/etc/shadow`
- `/root`
- `/var/log`
- `/proc`
- `/sys`

---

## 6. 配置限制

| 参数 | 默认值 | 最大值 |
|------|--------|--------|
| 超时时间 | 30秒 | 5分钟 |
| 输入大小 | 10MB | 可配置 |
| 输出大小 | 10MB | 可配置 |

---

## 7. 使用方式

### 7.1 在工具执行前检查

```python
from app.runtime.tool_doctor import run_preflight

# 执行前检查
result = run_preflight("shell", {"command": "rm -rf /"})

if not result.success:
    # Preflight 失败，不执行工具
    return result

# 执行工具
tool_result = tool.execute(params)
```

### 7.2 获取错误建议

```python
from app.runtime.tool_doctor import get_doctor

doctor = get_doctor()
suggestions = doctor.get_suggestions("file", permission_error)

for suggestion in suggestions:
    print(f"  建议: {suggestion}")
```

---

## 8. 集成点

以下位置必须调用 preflight：

1. `Tool.execute()` - 工具执行入口
2. `TaskRuntime._execute_step()` - 步骤执行前
3. `CommandRouter._handle_*()` - 命令处理前

---

## 9. 验收标准

- [x] 实现 ToolPreflight 类
- [x] 实现 ToolDoctor 类
- [x] 定义危险命令模式
- [x] 定义受限路径
- [x] 实现输入大小检查
- [x] 实现超时配置检查
- [x] 提供错误建议功能
- [x] 返回 UnifiedExecutionResult
