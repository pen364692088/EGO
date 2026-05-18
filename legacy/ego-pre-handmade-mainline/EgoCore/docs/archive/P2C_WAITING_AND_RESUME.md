# P2-C Waiting and Resume

## Waiting State

### Task Status

New status: `WAITING_USER_INPUT`

```
RUNNING → WAITING_USER_INPUT → RUNNING (after user reply)
                        ↘ FAILED (user rejected)
                        ↘ ABORTED (aborted while waiting)
```

### Task Fields

| Field | Type | Description |
|-------|------|-------------|
| `waiting_reason` | str | Reason for waiting |
| `waiting_request` | dict | ApprovalRequest serialization |
| `user_decision` | dict | User's decision after reply |

### State Machine

```python
# Valid transitions
RUNNING → WAITING_USER_INPUT  # Enter waiting
WAITING_USER_INPUT → RUNNING  # Resume after reply
WAITING_USER_INPUT → FAILED   # User rejected
WAITING_USER_INPUT → ABORTED  # Aborted

# Waiting is a paused state
WAITING_USER_INPUT in PAUSED_STATES
WAITING_USER_INPUT in WAITING_STATES
```

## Resume Flow

### 1. User Reply Received

```python
from app.runtime.reply_binding import handle_user_reply

result = handle_user_reply(
    user_reply="yes",
    chat_id="123",
    user_id="456",
)
```

### 2. Reply Bound to Task

```python
# BindingResult
{
    "success": True,
    "task_id": "task_xxx",
    "decision": {
        "is_valid": True,
        "approved": True,
        "parsed_value": "yes",
    },
}
```

### 3. Resume Task

```python
from app.runtime.resume_driver import resume_task_with_user_reply

result = resume_task_with_user_reply(
    task_id="task_xxx",
    user_reply="yes",
)
```

### 4. Continue Execution

- Write `user_decision` event
- Update task status to RUNNING
- Clear `waiting_reason`, `waiting_request`
- Execute next step via unified execution chain
- Go through preflight / unified result / postcondition

## User Rejection

If user replies "no":
- Task status → FAILED
- Error: "[user_rejected] 用户拒绝了操作"
- No further execution

## Background Guard

### Heartbeat

```python
def scan_resumable_tasks(self):
    for task in all_tasks:
        # P2-C: Skip WAITING_USER_INPUT
        if task.status == TaskStatus.WAITING_USER_INPUT:
            continue
```

### Cron

```python
def find_stalled_tasks(self):
    for task in all_tasks:
        # P2-C: Skip WAITING_USER_INPUT
        if task.status == TaskStatus.WAITING_USER_INPUT:
            continue
```

## Multiple Waiting Tasks

When multiple tasks are waiting:

1. System asks user to select task first
2. User replies `/reply <task_index> <answer>`
3. Reply binds to selected task

## Checkpoint

Waiting state is persisted to checkpoint:
- `waiting_reason`
- `waiting_request`
- Current step index

On resume:
- Load from checkpoint
- Restore step index
- Continue execution
