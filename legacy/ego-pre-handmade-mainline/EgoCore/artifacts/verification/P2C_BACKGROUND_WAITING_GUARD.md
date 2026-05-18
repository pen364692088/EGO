# P2-C Background Waiting Guard Verification

## Objective

Verify that background drivers (heartbeat/cron) do not progress WAITING_USER_INPUT tasks.

## Guard Implementation

### Heartbeat Driver

```python
# In heartbeat_driver.py
def scan_resumable_tasks(self) -> list[Task]:
    for task in all_tasks:
        # ... other checks ...
        
        # P2-C: Skip WAITING_USER_INPUT
        if task.status == TaskStatus.WAITING_USER_INPUT:
            logger.debug(f"Task {task.id} is waiting for user input, skipping")
            continue
```

### Cron Driver

```python
# In cron_driver.py
def find_stalled_tasks(self) -> List[Task]:
    for task in all_tasks:
        # ... other checks ...
        
        # P2-C: Skip WAITING_USER_INPUT
        if task.status == TaskStatus.WAITING_USER_INPUT:
            logger.debug(f"Task {task.id} is waiting for user input, skipping")
            continue
```

## Test Cases

### TC1: Heartbeat Skips Waiting Tasks

**Verification**:

```python
# State machine identifies waiting state
assert StateMachine.is_waiting(TaskStatus.WAITING_USER_INPUT) == True

# Heartbeat code explicitly skips
if task.status == TaskStatus.WAITING_USER_INPUT:
    continue
```

**Status**: ✅ PASSED - `test_heartbeat_skips_waiting_tasks`

### TC2: Cron Skips Waiting Tasks

**Verification**:

```python
# Cron code explicitly skips
if task.status == TaskStatus.WAITING_USER_INPUT:
    continue
```

**Status**: ✅ PASSED - `test_cron_skips_waiting_tasks`

### TC3: Waiting State in Paused States

**Verification**:

```python
assert TaskStatus.WAITING_USER_INPUT in StateMachine.PAUSED_STATES
assert TaskStatus.WAITING_USER_INPUT in StateMachine.WAITING_STATES
```

**Status**: ✅ PASSED - `test_state_machine_waiting_in_paused_states`

### TC4: Background Does Not Make Decisions

**Principle**: Background drivers never guess user decisions.

**Verification**:
- Heartbeat only processes BLOCKED or RUNNING tasks
- Cron only processes stalled BLOCKED or RUNNING tasks
- WAITING_USER_INPUT is explicitly excluded
- No auto-confirmation logic exists

**Status**: ✅ VERIFIED - No decision-making code for waiting tasks

## State Flow

```
┌─────────────┐
│   RUNNING   │
└──────┬──────┘
       │ needs approval
       ▼
┌─────────────────────────┐
│ WAITING_USER_INPUT      │◄─── Background CANNOT progress
│                         │     - Heartbeat: skip
│ (waiting for user)      │     - Cron: skip
└──────┬──────────────────┘
       │ user replies
       ▼
┌─────────────┐
│   RUNNING   │◄─── Only manual resume
└─────────────┘
```

## What Background Cannot Do

| Action | Allowed? |
|--------|----------|
| Auto-progress waiting task | ❌ NO |
| Guess user decision | ❌ NO |
| Auto-confirm high-risk op | ❌ NO |
| Retry waiting task | ❌ NO |
| Bypass waiting gate | ❌ NO |

## What Background Can Do

| Action | Allowed? |
|--------|----------|
| Log waiting task skip | ✅ YES |
| Report waiting status | ✅ YES |
| Wait for user reply | ✅ YES (required) |

## Test Results

| Test | Status |
|------|--------|
| test_heartbeat_skips_waiting_tasks | ✅ PASSED |
| test_cron_skips_waiting_tasks | ✅ PASSED |
| test_state_machine_waiting_in_paused_states | ✅ PASSED |
| test_background_cannot_progress_waiting | ✅ PASSED |

## Conclusion

✅ **Background Waiting Guard: VERIFIED**

- Heartbeat explicitly skips WAITING_USER_INPUT
- Cron explicitly skips WAITING_USER_INPUT
- State machine correctly identifies waiting states
- Background drivers cannot make user decisions
