# P2-D Commands and States

## Command State Matrix

| Command | CREATED | PLANNING | RUNNING | PAUSED | BLOCKED | WAITING | COMPLETED | FAILED | ABORTED |
|---------|---------|----------|---------|--------|---------|---------|-----------|--------|---------|
| /approve | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| /reject | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| /retry | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| /cancel | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| /resume | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| /pause | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| /abort | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

## State Transitions

### Approve

```
WAITING_USER_INPUT → RUNNING
```

- Task must be in WAITING_USER_INPUT state
- Sets user_decision.approved = true
- Clears waiting_reason, waiting_request

### Reject

```
WAITING_USER_INPUT → FAILED
```

- Task must be in WAITING_USER_INPUT state
- Sets user_decision.approved = false
- Sets error: "[user_rejected] 用户拒绝了操作"

### Retry

```
BLOCKED → RUNNING
```

- Task must be in BLOCKED state
- Checks failure policy allows retry
- Increments retry_count
- Sets trigger_source = "user_retry"

### Cancel

```
RUNNING → ABORTED
PAUSED → ABORTED
BLOCKED → ABORTED
WAITING_USER_INPUT → ABORTED
```

- Sets error: "[user_cancelled] 用户取消了任务"

### Resume

```
PAUSED → RUNNING
WAITING_USER_INPUT → RUNNING
```

- Sets trigger_source = "user_resume"

## Error Messages

| Error | Message |
|-------|---------|
| task_not_found | "任务不存在" |
| invalid_state | "当前状态 [xxx] 不允许执行 /yyy" |
| invalid_id | "无效的任务 ID 格式: xxx" |
| retry_not_allowed | "失败类型 [xxx] 不允许重试" |

## Idempotency

- Same command on same task within 1 minute is skipped
- Prevents duplicate control actions
- Logged as "skipped_duplicate" in audit
