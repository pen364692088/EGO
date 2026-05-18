# P2-B State Machine

## Task States

```
                    ┌─────────┐
                    │ created │
                    └────┬────┘
                         │ plan
                         ▼
                    ┌─────────┐
          ┌────────│ running │────────┐
          │        └────┬────┘        │
          │             │             │
     pause│        complete│      block│
          ▼             ▼             ▼
     ┌─────────┐   ┌───────────┐  ┌─────────┐
     │ paused  │   │ completed │  │ blocked │
     └────┬────┘   └───────────┘  └────┬────┘
          │                            │
      resume│                     retry│fail
          ▼                            ▼
     ┌─────────┐                  ┌─────────┐
     │ running │                  │ failed  │
     └─────────┘                  └─────────┘
```

## Background Driver States

### Heartbeat Driver

```
┌─────────────┐     scan      ┌─────────────┐
│   IDLE      │──────────────▶│  SCANNING   │
└─────────────┘               └──────┬──────┘
      ▲                              │
      │         ┌────────────────────┴────────────────────┐
      │         │                                         │
      │    no tasks                                found tasks
      │         │                                         │
      │         ▼                                         ▼
      │  ┌─────────────┐                         ┌─────────────┐
      └──│   WAITING   │◀────────────────────────│ PROCESSING  │
         └─────────────┘   lease released        └─────────────┘
```

### Cron Driver

```
┌─────────────┐     scan      ┌─────────────┐
│   IDLE      │──────────────▶│  SCANNING   │
└─────────────┘               └──────┬──────┘
      ▲                              │
      │         ┌────────────────────┴────────────────────┐
      │         │                                         │
      │    no stalled                             found stalled
      │         │                                         │
      │         ▼                                         ▼
      │  ┌─────────────┐                         ┌─────────────┐
      └──│   WAITING   │◀────────────────────────│  RECOVERING │
         └─────────────┘   recovery done         └─────────────┘
```

## Failure → State Transitions

| Failure Class | From State | To State | Background Action |
|---------------|------------|----------|-------------------|
| `INTENT_MISMATCH` | RUNNING | FAILED | BLOCK_MANUAL |
| `POSTCONDITION_FAILED` | RUNNING | FAILED | BLOCK_MANUAL |
| `PATH_EXTRACTION_ERROR` | RUNNING | FAILED | BLOCK_MANUAL |
| `SAFETY_BLOCK` | RUNNING | BLOCKED | BLOCK_MANUAL |
| `PERMISSION_ERROR` | RUNNING | FAILED | BLOCK_MANUAL |
| `TIMEOUT` | RUNNING | BLOCKED | RETRY |
| `ENVIRONMENT_ERROR` | RUNNING | BLOCKED | RETRY |
| `MODEL_ERROR` | RUNNING | BLOCKED | RETRY |
| `TOOL_ERROR` | RUNNING | BLOCKED | RETRY |
| `NOT_FOUND` | RUNNING | BLOCKED | RETRY (limited) |

## Concurrency Protection

### Lease System

```python
# Acquire lease before processing
if driver.acquire_lease(task_id, "heartbeat"):
    try:
        # Process task
        result = process_task(task)
    finally:
        driver.release_lease(task_id)
```

### Lease Properties

- Duration: 60 seconds (heartbeat), 120 seconds (cron)
- Holder: "heartbeat" or "cron"
- Auto-expire: Yes
- Re-entrant: No (must wait for expiration)
