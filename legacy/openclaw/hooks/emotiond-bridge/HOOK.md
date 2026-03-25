---
name: emotiond-bridge
description: "Bridge hook for OpenEmotion emotiond - auto time_passed and context extraction"
homepage: https://docs.openclaw.ai/automation/hooks
metadata:
  {
    "openclaw":
      {
        "emoji": "🌉",
        "events": ["message:received"],
        "requires": { "env": ["EMOTIOND_BASE_URL", "EMOTIOND_OPENCLAW_TOKEN"] }
      }
  }
---

# Emotiond Bridge Hook

Automatically bridges OpenClaw message events to the emotiond daemon.

## What It Does

1. **Context Extraction**: On each `message:received`, extracts `conversationId` and writes to workspace
2. **Time Pass Tracking**: Calculates real elapsed time since last message and sends `time_passed` events
3. **Target Isolation**: Ensures `target_id` = `conversationId` for MVP-3.1 per-target learning

## Configuration

Environment variables (set in `~/.openclaw/openclaw.json`):

- `EMOTIOND_BASE_URL`: emotiond API endpoint (default: http://127.0.0.1:18080)
- `EMOTIOND_OPENCLAW_TOKEN`: Bearer token for authenticated requests

## Installation

Hook is installed at: `<workspace>/hooks/emotiond-bridge/`

Enable via config:
```json
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "emotiond-bridge": { "enabled": true }
      }
    }
  }
}
```
