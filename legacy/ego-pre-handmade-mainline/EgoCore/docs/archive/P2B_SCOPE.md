# P2-B Scope Document

## Overview

P2-B implements the minimal background progression loop for EgoCore, a single Agent Runtime.

**Core Principle**: "Tool execution success" != "Task completion success"

## Goals

1. Enable background task progression (heartbeat + cron)
2. Prevent false-success scenarios from being auto-retried to "completed"
3. Maintain foreground/background isolation
4. Provide minimal notification and status query capabilities

## Hard Boundaries

### Must Adhere

- Single Agent Runtime
- Telegram driven
- Heartbeat minimal continuation
- Cron minimal compensation
- Reuse existing runtime main chain
- Reuse UnifiedExecutionResult
- Reuse preflight / tool_doctor
- Reuse IntentMapper / PostconditionValidator results

### Explicitly Forbidden

- Multi-Agent
- Dashboard
- Workflow DSL
- Sub-agent orchestration
- New parallel background execution chain
- Bypassing postcondition / intent validation
- Misclassifying `INTENT_MISMATCH / POSTCONDITION_FAILED / PATH_EXTRACTION_ERROR` as completed

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Failure Policy | `app/runtime/failure_policy.py` | failure_class → background_action mapping |
| Heartbeat Driver | `app/runtime/heartbeat_driver.py` | 30s interval task progression |
| Cron Driver | `app/runtime/cron_driver.py` | 5min interval stalled task recovery |
| Foreground Guard | `app/runtime/guard.py` | Foreground/background isolation |
| Notification Policy | `app/runtime/notification_policy.py` | User notification rules |
| Status Query | `app/runtime/status_query.py` | Task status summary |

## Test Coverage

- `tests/test_p2b.py`: 31 tests, all passing

## Verification

See `artifacts/verification/P2B_*.md` for verification proofs.
