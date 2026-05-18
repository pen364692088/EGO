# P2-C Scope Document

## Overview

P2-C implements Human-in-the-Loop minimal loop for EgoCore, a single Agent Runtime.

**Core Flow**: Ask → Wait → Resume

## Goals

1. System stops when confirmation needed
2. Waiting state is persisted and visible
3. Telegram sends clear confirmation request
4. User reply binds to original task
5. Task resumes (not creates new)
6. Background drivers don't bypass waiting gate

## Hard Boundaries

### Must Adhere

- Single Agent
- Telegram driven
- Single task human-in-the-loop
- Ask / wait / resume minimal loop
- Integrate with existing runtime / checkpoint / notification / status query

### Explicitly Forbidden

- Multi-Agent collaboration approval
- Dashboard / web approval panel
- Generic conversation state machine platform
- Large workflow / approval DSL
- Enterprise permission approval system
- Refactoring Phase 1 / P2-A / P2-B main chain
- Creating new task instead of resuming original

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Approval Policy | `app/runtime/approval_policy.py` | Define when to ask user |
| Waiting State | `app/storage/models.py` | Task WAITING_USER_INPUT status |
| Confirmation Renderer | `app/runtime/confirmation_renderer.py` | Render confirmation messages |
| Reply Binding | `app/runtime/reply_binding.py` | Bind user reply to waiting task |
| Resume Driver | `app/runtime/resume_driver.py` | Resume task after confirmation |
| Background Guard | `app/runtime/heartbeat_driver.py`, `cron_driver.py` | Skip waiting tasks |

## Test Coverage

- `tests/test_p2c.py`: 29 tests, all passing
- Total: 112 passed

## Verification

See `artifacts/verification/P2C_*.md` for verification proofs.
