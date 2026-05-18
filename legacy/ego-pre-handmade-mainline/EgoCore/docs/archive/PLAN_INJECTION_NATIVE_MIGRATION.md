# Plan Injection Native Migration

## Overview

This document describes the migration of Plan Injection from OpenClaw hook host to EgoCore native integration.

## Why Migration Was Necessary

### Previous Architecture (Incorrect)

```
EgoCore → OpenClaw Gateway Hooks → OpenEmotion
```

Problems with this architecture:
1. **Wrong host layer**: Plan Injection is EgoCore's internal capability, not OpenClaw's hook responsibility
2. **Unnecessary dependency**: Required OpenClaw gateway hooks configuration and token
3. **Deployment complexity**: Two systems to configure for one feature
4. **Architecture mismatch**: OpenEmotion is independent, EgoCore should directly couple

### Current Architecture (Correct)

```
EgoCore
  ├─ Reply Generation
  │   ├─ Injection Gate (skip commands/control/tools)
  │   ├─ OpenEmotion Client (/plan)
  │   ├─ Plan Adapter
  │   └─ Fallback Handler
  └─ Event Mirror (/event)
        │
        ▼
OpenEmotion (localhost:18080)
```

Benefits:
1. **Correct ownership**: EgoCore owns its reply enhancement
2. **No hook dependency**: No OpenClaw gateway hooks required
3. **Simpler deployment**: Configure only EgoCore
4. **Clear architecture**: EgoCore ↔ OpenEmotion direct

## Migration Changes

### Files Removed from OpenClaw Hook Path

- `~/.openclaw/workspace/hooks/plan-injection` (symlink) - REMOVED
- `openclaw.json` → `hooks.internal.entries.plan-injection` - REMOVED

### Files Added to EgoCore

| File | Purpose |
|------|---------|
| `app/integrations/openemotion/injection_gate.py` | Gate logic (skip commands/control/tools) |
| `app/integrations/openemotion/plan_adapter.py` | Adapt PlanResponse to ReplyGuidance |
| `app/integrations/openemotion/reply_injection.py` | Main entry point for injection |
| `config/openemotion.yaml` | Configuration (plan_injection section) |
| `tests/test_plan_injection.py` | Unit tests |

### Configuration Migration

**Old (OpenClaw openclaw.json)**:
```json
{
  "env": {
    "inject_plan_into_reply": "true",
    "skip_plan_for_commands": "true",
    ...
  },
  "hooks": {
    "internal": {
      "entries": {
        "plan-injection": {"enabled": true}
      }
    }
  }
}
```

**New (EgoCore config/openemotion.yaml)**:
```yaml
bridge:
  plan_injection:
    enabled: true
    chat_only: true
    skip_commands: true
    skip_task_control: true
    skip_tool_paths: true
    soft_fail: true
```

## Usage in EgoCore

### Basic Usage

```python
from app.integrations.openemotion import maybe_inject_plan

# In reply generation path
result = maybe_inject_plan(
    user_id="telegram:123",
    message_text="Hello, I need help",
    context={}
)

if result.injected:
    # Use guidance for response
    tone = result.guidance.tone
    key_points = result.guidance.key_points
    
    # Build response with this context
    prompt_context = result.guidance.to_prompt_context()
else:
    # Fallback - use neutral response
    pass
```

### Integration Point

The injection should happen in EgoCore's reply generation flow:

```python
# In command_router.py or similar
async def generate_reply(user_id: str, message: str, context: dict) -> str:
    # 1. Attempt plan injection
    injection_result = maybe_inject_plan(user_id, message, context)
    
    # 2. Build prompt with plan context
    if injection_result.injected:
        plan_context = injection_result.guidance.to_prompt_context()
        prompt = f"{plan_context}\n\nUser message: {message}"
    else:
        prompt = f"User message: {message}"
    
    # 3. Generate response via LLM
    response = await llm.generate(prompt)
    
    # 4. Still send event to OpenEmotion (separate path)
    # event_result = send_event(...)
    
    return response
```

## Gate Behavior

| Path Type | Gate Result | Reason |
|-----------|-------------|--------|
| Normal chat | ALLOW | chat_path |
| Slash commands | SKIP | is_command |
| Task control | SKIP | is_task_control |
| Tool execution | SKIP | is_tool_path |
| Feature disabled | DISABLED | feature_disabled |

## Fallback Scenarios

| Scenario | Behavior |
|----------|----------|
| OpenEmotion down | Neutral response, log warning |
| Timeout | Neutral response, log warning |
| 5xx error | Neutral response, log error |
| Schema invalid | Neutral response, log warning |
| Empty plan | Use decision fallback if available |

## Verification

Run tests:
```bash
cd /home/moonlight/Project/Github/MyProject/EgoCore
python -m pytest tests/test_plan_injection.py -v
```

## Still Remaining Limitations

1. **Integration not connected**: The injection modules exist but are not yet connected to EgoCore's main reply generation path
2. **No E2E test**: Need real Telegram bot test to verify end-to-end
3. **No metrics collection**: Fallback metrics not yet aggregated
4. **Event mirror separate**: Event mirroring still uses separate code path

## Version

- **Migration Date**: 2026-03-13
- **EgoCore Version**: Phase 2 Complete
- **OpenEmotion Version**: v0.1.0
