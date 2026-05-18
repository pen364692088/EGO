# P2-D Audit Trail

## Overview

All control actions are logged to an append-only audit log.

## Audit Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| actor | string | Who performed the action ("user" or system) |
| command | string | Command executed (approve, reject, etc.) |
| task_id | string | Target task ID |
| previous_status | string | Status before action |
| new_status | string | Status after action |
| timestamp | ISO8601 | When action occurred |
| source | enum | telegram_command, heartbeat, cron, internal |
| reason | string? | Optional reason provided by user |
| payload | object? | Additional data |
| success | boolean | Whether action succeeded |
| error | string? | Error message if failed |

## Audit Sources

| Source | Description |
|--------|-------------|
| telegram_command | User-initiated via Telegram |
| heartbeat | Automatic heartbeat driver |
| cron | Automatic cron recovery |
| internal | Internal system action |

## Storage

- File: `data/control_audit.jsonl`
- Format: JSON Lines (one entry per line)
- Append-only for integrity

## Query Functions

```python
# Get entries for a specific task
entries = audit_log.get_entries_for_task("task_abc123")

# Get recent entries
entries = audit_log.get_recent_entries(limit=20)

# Get entries by source
entries = audit_log.get_entries_by_source(AuditSource.TELEGRAM_COMMAND)

# Get summary for a task
summary = audit_log.get_summary_for_task("task_abc123")
```

## Example Entry

```json
{
  "actor": "user",
  "command": "approve",
  "task_id": "task_abc123",
  "previous_status": "waiting_user_input",
  "new_status": "running",
  "timestamp": "2026-03-13T18:51:00.000000",
  "source": "telegram_command",
  "reason": null,
  "payload": null,
  "success": true,
  "error": null
}
```

## Distinguishing User vs Background

User actions have:
- `source`: "telegram_command"
- `actor`: "user"

Background actions have:
- `source`: "heartbeat" or "cron"
- `actor`: "system"
