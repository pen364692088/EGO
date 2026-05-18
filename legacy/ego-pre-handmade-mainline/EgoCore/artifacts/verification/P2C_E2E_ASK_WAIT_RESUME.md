# P2-C E2E Ask/Wait/Resume Verification

## Objective

Verify the complete ask/wait/resume loop works correctly.

## Test Scenario

### Step 1: User Initiates Task

```
User: "删除 /tmp/test.txt 文件"
```

### Step 2: Runtime Detects Need for Confirmation

```python
from app.runtime.approval_policy import check_approval_needed

decision = check_approval_needed(
    step_description="删除 /tmp/test.txt 文件",
    task_id="task_1",
)

# Result
assert decision.approval_needed == True
assert decision.approval_request.approval_type == ApprovalType.YES_NO
assert decision.approval_request.reason == ApprovalReason.HIGH_RISK_OPERATION
```

**Verification**: ✅ PASSED - `test_approval_needed_for_high_risk`

### Step 3: Task Enters WAITING_USER_INPUT

```python
task.status = TaskStatus.WAITING_USER_INPUT
task.waiting_reason = "high_risk_operation"
task.waiting_request = decision.approval_request.to_dict()

# Verify state machine
assert StateMachine.is_waiting(TaskStatus.WAITING_USER_INPUT) == True
```

**Verification**: ✅ PASSED - `test_state_machine_is_waiting`

### Step 4: Telegram Sends Confirmation

```python
from app.runtime.confirmation_renderer import render_telegram_confirmation

message = render_telegram_confirmation(decision.approval_request)

# Message contains:
# - "需要确认"
# - "删除 /tmp/test.txt 文件"
# - "回复 yes/no"
```

**Verification**: ✅ PASSED - `test_render_yes_no_message`

### Step 5: User Replies

```
User: "yes"
```

### Step 6: Reply Binds to Task

```python
from app.runtime.reply_binding import handle_user_reply

result = handle_user_reply(
    user_reply="yes",
    chat_id="123",
    user_id="456",
)

# Result
assert result["action"] == "resume_task"
assert result["decision"]["approved"] == True
```

**Verification**: ✅ PASSED - `test_parse_user_decision_yes_no`

### Step 7: Task Resumes

```python
from app.runtime.resume_driver import resume_task_with_user_reply

result = resume_task_with_user_reply(
    task_id="task_1",
    user_reply="yes",
)

# Result
assert result["success"] == True
assert result["action"] == "resumed"
```

**Verification**: ✅ PASSED - `test_ask_wait_resume_flow`

### Step 8: Continue Execution

- Task status → RUNNING
- Execute next step via `execute_next_step_unified()`
- Go through preflight / unified result / postcondition

## Complete Flow Verification

```
┌─────────────────────────────────────────────────────────────┐
│  1. User initiates task                                      │
│     "删除 /tmp/test.txt 文件"                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Approval check                                           │
│     HIGH_RISK_OPERATION detected → approval_needed = True   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Task enters WAITING_USER_INPUT                          │
│     waiting_reason = "high_risk_operation"                  │
│     waiting_request = ApprovalRequest(...)                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Telegram sends confirmation message                     │
│     "⚠️ 需要确认 ... 回复 yes/no"                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  5. User replies "yes"                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Reply binds to waiting task                              │
│     decision.approved = True                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Task resumes (not new task)                              │
│     status → RUNNING                                         │
│     user_decision written to event                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  8. Continue unified execution chain                         │
│     execute_next_step_unified()                              │
│     → preflight → execution → postcondition                 │
└─────────────────────────────────────────────────────────────┘
```

## Test Results

| Test | Status |
|------|--------|
| test_approval_needed_for_high_risk | ✅ PASSED |
| test_state_machine_is_waiting | ✅ PASSED |
| test_render_yes_no_message | ✅ PASSED |
| test_parse_user_decision_yes_no | ✅ PASSED |
| test_ask_wait_resume_flow | ✅ PASSED |

## Conclusion

✅ **E2E Ask/Wait/Resume: VERIFIED**

All steps in the flow are tested and pass.
