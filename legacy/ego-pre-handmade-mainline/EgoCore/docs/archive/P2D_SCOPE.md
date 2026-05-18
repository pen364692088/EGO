# P2-D Scope Document

## Overview

P2-D implements Operator Control Minimal Loop for EgoCore, a single Agent Runtime.

**Core Principle**: Users can explicitly view, approve, reject, retry, cancel, and resume tasks through Telegram commands.

## Goals

1. Users can list and view tasks
2. Users can control tasks through commands
3. All control actions have state machine guards
4. All control actions are logged to audit trail
5. No parallel tasks created by control actions

## Hard Boundaries

### Must Adhere

- Telegram command-level control interface
- Single Agent / Single User / Single Task control
- Integrate with existing runtime / checkpoint / notification

### Explicitly Forbidden

- Dashboard / Web UI
- Multi-Agent console
- Multi-user approval flow
- RBAC / Permission system
- Large command DSL
- Generic task scheduling platform
- Refactoring P2-A/P2-B/P2-C main chain
- Bypassing state machine and unified main chain

## Commands

| Command | Description | Valid States |
|---------|-------------|--------------|
| `/tasks` | List tasks | N/A |
| `/task <id>` | Task detail | N/A |
| `/approve <id>` | Approve waiting task | WAITING_USER_INPUT |
| `/reject <id>` | Reject waiting task | WAITING_USER_INPUT |
| `/retry <id>` | Retry blocked task | BLOCKED |
| `/cancel <id>` | Cancel task | RUNNING, PAUSED, BLOCKED, WAITING_USER_INPUT |
| `/resume <id>` | Resume task | PAUSED, WAITING_USER_INPUT |

## Components

| Component | File | Purpose |
|-----------|------|---------|
| State Guard | `app/runtime/control_guard.py` | Validate command-state transitions |
| Control Audit | `app/runtime/control_audit.py` | Log all control actions |
| Control Commands | `app/runtime/control_commands.py` | Handle user commands |

## Test Coverage

- `tests/test_p2d.py`: 27 tests, all passing
- Total: 139 passed

## Verification

See `artifacts/verification/P2D_*.md` for verification proofs.
