# P2-B Notification Policy

## Overview

Defines what notifications are sent to users, when, and by which execution mode.

## Notification Categories

### MUST Notify (Always Sent)

| Type | Description |
|------|-------------|
| `TASK_COMPLETED` | Task finished successfully |
| `TASK_BLOCKED` | Task is blocked and needs attention |
| `MANUAL_ACTION_REQUIRED` | User intervention needed |
| `INTENT_MISMATCH_BLOCKED` | Intent mismatch detected |
| `PATH_EXTRACTION_BLOCKED` | Path could not be parsed |
| `STATUS_QUERY_RESPONSE` | Response to user status query |

### SHOULD Notify (Unless Suppressed)

| Type | Description |
|------|-------------|
| `TASK_FAILED` | Task terminally failed |
| `RECOVERY_COMPLETED` | Cron recovery succeeded |

### DEFAULT NOT Notify (Background Noise)

| Type | Description |
|------|-------------|
| `HEARTBEAT_TICK` | Heartbeat scan cycle |
| `CRON_TICK` | Cron scan cycle |
| `RETRY_ATTEMPT` | Automatic retry happening |
| `CHECKPOINT_SAVE` | Checkpoint written |
| `INTERMEDIATE_PROGRESS` | Step progress |

## Execution Mode Rules

### Foreground Mode

- Can send any notification type
- Includes debug information
- Full verbosity allowed

### Background Mode

- Only sends MUST_NOTIFY types
- Filters out intermediate noise
- No heartbeat/cron tick notifications

## Reply Channel Protection

Background drivers do NOT write to foreground reply channel for:

- Heartbeat ticks
- Cron ticks
- Retry attempts
- Checkpoint saves
- Intermediate progress

## Notification Formatting

```python
def format_notification(payload: NotificationPayload) -> str:
    """Format notification for display."""
    
    # Emoji by type
    ✅ TASK_COMPLETED
    ⚠️ TASK_BLOCKED
    🔔 MANUAL_ACTION_REQUIRED
    🚫 INTENT_MISMATCH_BLOCKED
    🚫 PATH_EXTRACTION_BLOCKED
    ❌ TASK_FAILED
    📊 STATUS_QUERY_RESPONSE
```

## Usage

```python
from app.runtime.notification_policy import (
    should_notify,
    get_notification_for_failure,
    get_notification_for_completion,
    NotificationDispatcher,
)

# Check if should notify
if should_notify(NotificationType.TASK_COMPLETED, execution_mode):
    send_notification(...)

# Create failure notification
payload = get_notification_for_failure(
    FailureClass.INTENT_MISMATCH,
    task_id,
    trigger_source
)

# Dispatch
dispatcher = get_notification_dispatcher()
dispatcher.dispatch(payload, execution_mode)
```

## Integration Points

1. **Task Runtime**: Sends completion/failure notifications
2. **Heartbeat Driver**: Sends blocked/recovery notifications
3. **Cron Driver**: Sends recovery completion notifications
4. **Telegram Bot**: Receives and delivers notifications
