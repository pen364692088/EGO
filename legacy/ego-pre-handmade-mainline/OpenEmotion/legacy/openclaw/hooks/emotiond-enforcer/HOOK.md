---
name: emotiond-enforcer
description: "Enforcer hook for OpenEmotion emotiond - ensures bot responses comply with emotional decisions"
homepage: https://docs.openclaw.ai/automation/hooks
metadata:
  {
    "openclaw":
      {
        "emoji": "🛡️",
        "events": ["message:sending"],
        "requires": { "env": ["EMOTIOND_BASE_URL", "EMOTIOND_OPENCLAW_TOKEN"] }
      }
  }
---

# Emotiond Enforcer Hook

Ensures bot responses comply with emotiond decisions before sending.

## What It Does

1. **Decision Enforcement**: On `message:sending`, fetches current decision for target
2. **Response Modification**: Replaces/modifies responses that violate decision constraints
3. **Audit Logging**: All enforcement decisions logged for traceability

## Enforcement Rules

| Action | Enforcement | Template |
|--------|-------------|----------|
| `withdraw` | Replace with brief, neutral template | "I understand. Noted." |
| `boundary` | Check for violations, warn if detected | (no replacement) |
| `attack` | Sanitize to safe response | "I need to step back." |
| `approach` | Allow (no enforcement) | - |
| `repair_offer` | Allow (no enforcement) | - |
| `observe` | Allow (no enforcement) | - |

## Boundary Violation Patterns

- `I (love|adore|worship) you`
- `you('re| are) (my|the) (everything|world|life)`
- `I can't live without you`
- `forever together`
- `I'll do anything for you`

## Configuration

Environment variables (set in `~/.openclaw/openclaw.json`):

- `EMOTIOND_BASE_URL`: emotiond API endpoint (default: http://127.0.0.1:18080)
- `EMOTIOND_OPENCLAW_TOKEN`: Bearer token for authenticated requests

## Installation

Hook is installed at: `<workspace>/hooks/emotiond-enforcer/`

Enable via config:
```json
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "emotiond-enforcer": { "enabled": true }
      }
    }
  }
}
```

## Audit Log

All enforcement decisions are logged to:
```
~/.openclaw/workspace/emotiond/enforcement_audit.jsonl
```
