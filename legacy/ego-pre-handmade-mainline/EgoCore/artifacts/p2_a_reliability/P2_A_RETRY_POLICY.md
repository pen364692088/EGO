# P2-A T4: 重试策略与边界

**版本**: 1.0  
**日期**: 2026-03-13  
**状态**: FROZEN

---

## 1. 重试策略矩阵

| Failure Class | 可重试 | 最大次数 | 间隔 | 退避策略 |
|--------------|--------|---------|------|---------|
| TIMEOUT | ✅ | 3 | 2s | 指数退避 |
| ENVIRONMENT_ERROR | ✅ | 3 | 2s | 指数退避 |
| MODEL_ERROR | ✅ | 3 | 2s | 指数退避 |
| TOOL_ERROR | ⚠️ | 1 | 1s | 无 |
| VALIDATION_ERROR | ❌ | 0 | - | - |
| PERMISSION_ERROR | ❌ | 0 | - | - |
| NOT_FOUND | ❌ | 0 | - | - |
| SAFETY_BLOCK | ❌ | 0 | - | - |
| UNSUPPORTED | ❌ | 0 | - | - |
| TASK_LOGIC_ERROR | ❌ | 0 | - | - |
| UNKNOWN | ⚠️ | 1 | 1s | 无 |

---

## 2. 重试配置

### 2.1 RetryHint 结构

```python
@dataclass
class RetryHint:
    retryable: bool              # 是否可重试
    max_retries: int = 3         # 最大重试次数
    current_retry: int = 0       # 当前重试次数
    retry_after_ms: int = 1000   # 重试间隔(毫秒)
    backoff_multiplier: float = 2.0  # 退避乘数
    reason: Optional[str] = None     # 原因说明
```

### 2.2 退避策略

指数退避计算:

```
delay = retry_after_ms * (backoff_multiplier ^ current_retry)

示例 (初始 2s, 乘数 2):
- 第 1 次重试: 2s
- 第 2 次重试: 4s
- 第 3 次重试: 8s
```

---

## 3. 重试边界

### 3.1 全局重试预算

- 单任务最大重试时间: 5 分钟
- 单步骤最大重试次数: 3 次
- 连续失败后进入 BLOCKED 状态

### 3.2 重试终止条件

以下情况立即终止重试:

1. 达到最大重试次数
2. 重试预算耗尽
3. 失败类型变为 non-retryable
4. 用户取消任务
5. 安全边界触发

---

## 4. 重试日志

每次重试必须记录:

```python
{
    "event": "retry",
    "task_id": "task_xxx",
    "step_id": "step_xxx",
    "retry_number": 2,
    "max_retries": 3,
    "delay_ms": 4000,
    "failure_class": "timeout",
    "timestamp": "2026-03-13T14:00:00"
}
```

---

## 5. 用户可见行为

### 5.1 自动重试

```
⚠️ 操作超时，正在重试 (2/3)...
```

### 5.2 重试耗尽

```
❌ 重试次数已用尽
📊 失败原因: [timeout] API 调用超时
💡 建议: 稍后使用 /resume 重试或检查网络连接
```

### 5.3 不可重试失败

```
❌ 操作失败
📊 失败原因: [validation_error] 参数验证失败
💡 建议: 检查输入参数后重试
🔄 重试: 不支持 (需修正输入)
```

---

## 6. 与状态流转集成

```
RUNNING
   ↓ (transient failure)
RETRYABLE → 自动重试 → RUNNING
   ↓ (重试成功)
COMPLETED

   ↓ (重试失败)
BLOCKED → 用户干预 → /resume → RUNNING
```

---

## 7. 验收标准

- [x] 定义重试策略矩阵
- [x] 实现 RetryHint 类
- [x] 实现指数退避
- [x] 定义重试边界
- [x] 重试日志记录
- [x] 用户可见消息
