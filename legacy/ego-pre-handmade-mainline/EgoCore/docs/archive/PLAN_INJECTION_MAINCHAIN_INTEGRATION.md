# Plan Injection Mainchain Integration

## Overview

This document describes the integration of Plan Injection into EgoCore's main reply chain.

## Integration Point

Plan Injection is now integrated into:
- `_handle_chat_intent()` - For chat messages
- `_handle_question_intent()` - For question messages

## Flow

```
Incoming Message
    │
    ├─► Semantic Router (classify intent)
    │   ├─► CHAT → _handle_chat_intent()
    │   ├─► QUESTION → _handle_question_intent()
    │   ├─► NEW_TASK → _handle_new_task_intent()
    │   └─► CONTINUE_TASK → _handle_continue_intent()
    │
    ├─► In chat/question handlers:
    │   ├─► record_injection_attempt()
    │   ├─► maybe_inject_plan()
    │   ├─► Gate check (skip commands/control/tools)
    │   ├─► If allowed: Call /plan API
    │   ├─► If success: Use plan context in reply
    │   └─► If failure: Fallback to normal reply
    │
    └─► Generate Response
```

## Code Location

| File | Function | Purpose |
|------|----------|---------|
| `app/command_router.py` | `_handle_chat_intent()` | Chat handling with injection |
| `app/command_router.py` | `_handle_question_intent()` | Question handling with injection |
| `app/integrations/openemotion/reply_injection.py` | `maybe_inject_plan()` | Main injection entry point |
| `app/integrations/openemotion/injection_gate.py` | `InjectionGate` | Gate logic |
| `app/integrations/openemotion/plan_adapter.py` | `PlanAdapter` | Plan adaptation |
| `app/integrations/openemotion/injection_metrics.py` | `InjectionMetrics` | Metrics collection |

## Metrics

The following metrics are collected:

| Metric | Type | Description |
|--------|------|-------------|
| `attempt_total` | counter | Total injection attempts |
| `allowed_total` | counter | Allowed injections |
| `skipped_total` | counter | Skipped injections |
| `fallback_total` | counter | Fallback triggered |
| `error_total` | counter | Errors |
| `skipped_by_reason` | map | Skip count by reason |
| `fallback_by_reason` | map | Fallback count by reason |
| `latency_samples` | list | Latency samples in ms |

## Gate Behavior

| Path Type | Gate Result | Metrics Label |
|-----------|-------------|---------------|
| Normal chat | ALLOW | `allowed_total++` |
| Slash commands | SKIP | `skipped_by_reason[is_command]++` |
| Task control | SKIP | `skipped_by_reason[is_task_control]++` |
| Tool paths | SKIP | `skipped_by_reason[is_tool_path]++` |
| Feature disabled | DISABLED | `skipped_by_reason[feature_disabled]++` |

## Fallback Behavior

| Scenario | Behavior | Metrics Label |
|----------|----------|---------------|
| OpenEmotion down | Normal reply | `fallback_by_reason[down]++` |
| Timeout | Normal reply | `fallback_by_reason[timeout]++` |
| 5xx error | Normal reply | `fallback_by_reason[http_5xx]++` |
| Schema invalid | Normal reply | `fallback_by_reason[schema_invalid]++` |
| Empty plan | Normal reply | `fallback_by_reason[empty_plan]++` |

## Testing

### Unit Tests

```bash
cd /home/moonlight/Project/Github/MyProject/EgoCore
python -m pytest tests/test_plan_injection.py -v
```

Expected: 12 passed

### Integration Test

```bash
# 1. Start OpenEmotion
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
python -m emotiond.api

# 2. In another terminal, start EgoCore
cd /home/moonlight/Project/Github/MyProject/EgoCore
python -m app.main --telegram

# 3. Send test messages via Telegram
# Normal chat: "Hello, how are you?"
# Command: "/status" (should skip injection)
```

## Configuration

Configuration is in `config/openemotion.yaml`:

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

## Version

- **Integration Date**: 2026-03-13
- **EgoCore Version**: Phase 2 Complete + Plan Injection
- **Commit**: (pending)
