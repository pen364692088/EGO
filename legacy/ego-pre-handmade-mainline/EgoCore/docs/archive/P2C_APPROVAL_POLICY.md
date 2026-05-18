# P2-C Approval Policy

## Overview

Defines when user confirmation is required before task execution.

## Approval Types

| Type | Description | Example |
|------|-------------|---------|
| `YES_NO` | Simple yes/no confirmation | "Delete file? (yes/no)" |
| `OPTION_SELECT` | Choose from options | Multiple candidate paths |
| `INTENT_DISAMBIGUATE` | Disambiguate intent | Multiple possible operations |
| `PATH_CLARIFY` | Clarify target path | Path not determined |
| `FREE_TEXT` | Free-text clarification | User provides value |

## Approval Reasons

| Reason | Description |
|--------|-------------|
| `PATH_AMBIGUOUS` | Path not clear from user message |
| `MULTIPLE_TARGETS` | Multiple candidate targets found |
| `HIGH_RISK_OPERATION` | Delete/overwrite/risky write |
| `MULTIPLE_INTENTS` | Multiple high-confidence intents |
| `BRANCH_CHOICE` | User needs to choose branch |
| `SAFETY_CONFIRM` | Safety confirmation required |
| `PERMISSION_CONFIRM` | Permission confirmation |

## High-Risk Detection

### High-Risk Operations

Patterns that trigger approval:
- `delete`, `remove`, `rm`, `unlink`, `wipe`
- `overwrite`, `replace`, `truncate`
- `format`, `reboot`, `shutdown`, `restart`
- `push`, `deploy`, `upload`
- `chmod`, `chown`

### High-Risk Paths

Paths that trigger approval:
- `/etc`, `/usr`, `/bin`, `/sbin`
- `/boot`, `/root`, `/home`
- `~/.ssh`, `~/.gnupg`

## Decision Flow

```
check_approval_needed(step, intent, path, candidates)
    │
    ├─ Multiple intents? → INTENT_DISAMBIGUATE
    │
    ├─ Path not determined? → PATH_CLARIFY
    │
    ├─ Multiple candidate paths? → OPTION_SELECT
    │
    ├─ High-risk operation? → YES_NO
    │
    ├─ High-risk path? → YES_NO
    │
    ├─ Overwrite existing? → YES_NO
    │
    └─ Safe → No approval needed
```

## Reply Validation

### YES_NO

Valid replies: `yes`, `no`, `y`, `n`, `是`, `否`, `确认`, `取消`

### OPTION_SELECT

Valid replies: Option index (0, 1, 2, ...)

### PATH_CLARIFY

Valid replies: Any non-empty path string

## Usage

```python
from app.runtime.approval_policy import check_approval_needed, ApprovalType

# Check if approval needed
decision = check_approval_needed(
    step_description="delete the file /tmp/test.txt",
    task_id="task_1",
)

if decision.approval_needed:
    request = decision.approval_request
    # Render confirmation message
    # Wait for user reply
```
