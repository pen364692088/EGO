# P2-B Failure Policy

## Overview

Defines the mapping from `failure_class` to `background_action` for heartbeat and cron drivers.

**Core Protection**: Prevents "fake completed" scenarios where:
- Tool executes successfully
- But actual result doesn't match user's goal
- Background drivers mistakenly mark as completed

## Failure Classes

### Never Auto-Retry (False Success Protection)

| Failure Class | Reason | Action |
|---------------|--------|--------|
| `INTENT_MISMATCH` | Executed wrong operation vs user intent | `BLOCK_MANUAL` |
| `POSTCONDITION_FAILED` | Tool success but goal not achieved | `BLOCK_MANUAL` |
| `PATH_EXTRACTION_ERROR` | Could not parse target path | `BLOCK_MANUAL` |
| `SAFETY_BLOCK` | Blocked by safety rules | `BLOCK_MANUAL` |
| `PERMISSION_ERROR` | Insufficient permissions | `BLOCK_MANUAL` |
| `VALIDATION_ERROR` | Input validation failed | `BLOCK_MANUAL` |
| `UNSUPPORTED` | Operation not supported | `BLOCK_MANUAL` |
| `TASK_LOGIC_ERROR` | Task planning issue | `BLOCK_MANUAL` |
| `UNKNOWN` | Unclassified failure | `BLOCK_MANUAL` |

### Retryable (Transient Failures)

| Failure Class | Reason | Retry Limit |
|---------------|--------|-------------|
| `TIMEOUT` | Transient timeout | 3 |
| `ENVIRONMENT_ERROR` | Network/infra issue | 3 |
| `MODEL_ERROR` | LLM transient error | 3 |
| `TOOL_ERROR` | Tool execution failed | 2 |
| `NOT_FOUND` | Resource not found | 2 |

## Policy Fields

Each failure class has:

```python
@dataclass
class FailurePolicyEntry:
    allow_auto_retry: bool           # Can auto-retry?
    allow_heartbeat_resume: bool     # Can heartbeat resume?
    allow_cron_resume: bool          # Can cron resume?
    retry_limit: int                 # Max retries
    final_state: str                 # Terminal state if exhausted
    user_notification_required: bool # Must notify user?
    background_action: BackgroundAction # Recommended action
    reason: str                      # Human-readable reason
    manual_action_hint: str          # Hint for manual intervention
```

## Usage

```python
from app.runtime.failure_policy import (
    get_failure_policy,
    should_heartbeat_resume,
    can_auto_retry,
    is_false_success_failure,
)

# Check if failure is false-success
if is_false_success_failure(failure_class):
    # Never auto-retry
    return BLOCK_MANUAL

# Check if heartbeat can resume
if should_heartbeat_resume(failure_class):
    # Allow heartbeat to process
    pass
```

## Key Functions

- `get_failure_policy(failure_class)` → `FailurePolicyEntry`
- `should_heartbeat_resume(failure_class)` → `bool`
- `should_cron_resume(failure_class)` → `bool`
- `can_auto_retry(failure_class, current_retry)` → `bool`
- `is_false_success_failure(failure_class)` → `bool`
- `is_background_blocked(failure_class)` → `bool`
