# P2-A T7: 工具治理清单与风险矩阵

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 工具总览

| 工具 | 用途 | 风险级别 | 默认启用 |
|-----|------|---------|---------|
| file | 文件读写列表 | 中 | ✅ |
| shell | 命令执行 | 高 | ✅ |
| python | Python 代码执行 | 高 | ✅ |

---

## 2. File 工具治理

### 2.1 支持的操作

| 操作 | 说明 | 风险 | 需确认 |
|-----|------|-----|--------|
| read | 读取文件内容 | 低 | ❌ |
| list | 列出目录内容 | 低 | ❌ |
| write | 写入文件 | 中 | ⚠️ 覆盖时 |
| delete | 删除文件 | 高 | ✅ |

### 2.2 禁止的操作

- 访问 `/etc/passwd`, `/etc/shadow`
- 访问 `/root` 目录
- 访问 `/proc`, `/sys` 文件系统
- 写入系统目录

### 2.3 限制

| 参数 | 限制 | 说明 |
|-----|------|------|
| 输入大小 | 10MB | 单次写入最大 |
| 输出大小 | 10MB | 单次读取最大 |
| 路径深度 | 20 层 | 防止路径遍历 |

### 2.4 超时配置

| 操作 | 默认超时 | 最大超时 |
|-----|---------|---------|
| read | 30s | 5min |
| list | 10s | 1min |
| write | 60s | 5min |

---

## 3. Shell 工具治理

### 3.1 支持的操作

| 类型 | 示例 | 风险 |
|-----|------|-----|
| 查询 | ls, cat, grep | 低 |
| 分析 | find, wc, sort | 低 |
| 执行 | python, node | 中 |

### 3.2 需要确认的操作

- 删除文件 (`rm`)
- 修改权限 (`chmod`, `chown`)
- 网络操作 (`curl`, `wget`)
- 系统命令 (`systemctl`, `service`)

### 3.3 禁止的操作 (自动拦截)

| 模式 | 说明 |
|-----|------|
| `rm -rf /` | 删除根目录 |
| `rm -rf ~` | 删除用户目录 |
| `mkfs` | 格式化磁盘 |
| `dd if=... of=/dev/...` | 写入设备 |
| `:(){ :|:& };:` | Fork bomb |
| `wget ... \| sh` | 下载并执行 |
| `curl ... \| sh` | 下载并执行 |

### 3.4 限制

| 参数 | 限制 |
|-----|------|
| 命令长度 | 1000 字符 |
| 输出大小 | 10MB |
| 超时时间 | 5 分钟 |

---

## 4. Python 工具治理

### 4.1 支持的操作

- 数据处理
- 数学计算
- 文本分析
- JSON/CSV 处理

### 4.2 受限的操作

| 操作 | 说明 | 建议 |
|-----|------|------|
| `os.system()` | 执行命令 | 使用 shell 工具 |
| `subprocess.*` | 执行命令 | 使用 shell 工具 |
| `open()` | 文件操作 | 使用 file 工具 |
| `eval()` | 动态执行 | 避免 |
| `exec()` | 动态执行 | 避免 |

### 4.3 限制

| 参数 | 限制 |
|-----|------|
| 代码长度 | 10000 字符 |
| 执行超时 | 60 秒 |
| 内存限制 | 512MB |

---

## 5. 与 Semantic Router 一致性

### 5.1 高风险操作检测

Semantic Router 和 Tool Doctor 使用相同的高风险模式列表:

```python
# 共享模式
DANGEROUS_PATTERNS = [
    r"(删除|删除文件|删除目录|remove|delete)",
    r"(rm\s*-rf|rmdir|格式化|format)",
    r"(修改|修改文件|覆写|overwrite)",
    ...
]
```

### 5.2 检测层级

1. **Semantic Router** - 自然语言层面检测意图
2. **Tool Doctor** - 执行参数层面检测具体操作
3. **Tool Execute** - 运行时层面验证

---

## 6. 错误映射规则

| 错误类型 | 映射到 |
|---------|--------|
| FileNotFoundError | NOT_FOUND |
| PermissionError | PERMISSION_ERROR |
| TimeoutError | TIMEOUT |
| subprocess.TimeoutExpired | TIMEOUT |
| OSError (ENOSPC) | ENVIRONMENT_ERROR |

---

## 7. 日志与证据保存

### 7.1 必须记录

- 工具名称
- 操作类型
- 输入参数 (脱敏)
- 输出预览
- 执行时间
- 成功/失败状态
- 错误信息

### 7.2 证据保留

- 成功操作: 保留输出摘要
- 失败操作: 保留完整错误和堆栈
- 安全拦截: 保留拦截原因

---

## 8. 配置化

工具治理规则通过 `config/tools.yaml` 配置:

```yaml
file:
  enabled: true
  max_input_size: 10485760  # 10MB
  max_output_size: 10485760
  restricted_paths:
    - /etc/passwd
    - /etc/shadow
    - /root

shell:
  enabled: true
  timeout_ms: 30000
  max_output_size: 10485760
  dangerous_patterns:
    - "rm -rf /"
    - "mkfs"

python:
  enabled: true
  timeout_ms: 60000
  max_code_length: 10000
  restricted_functions:
    - os.system
    - subprocess.call
```

---

## 9. 验收标准

- [x] File 工具治理规则
- [x] Shell 工具治理规则
- [x] Python 工具治理规则
- [x] 高风险操作模式
- [x] 与 Semantic Router 一致
- [x] 错误映射规则
- [x] 配置化支持
