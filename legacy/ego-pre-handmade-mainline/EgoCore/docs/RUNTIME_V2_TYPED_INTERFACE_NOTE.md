# RUNTIME_V2_TYPED_INTERFACE_NOTE.md

> Status: active development note
> Scope: Runtime v2 primary interface cleanup

## Decision

In development, Runtime v2 now uses **typed turn results as the primary interface**.

For Telegram specifically:
- `use_runtime_v2=True` is the formal mainline path
- `use_new_runtime=True` without Runtime v2 is compatibility-only
- `_handle_with_legacy_router` is compatibility-only

Primary interface:
- `RuntimeV2Loop.run_turn_typed(...) -> RuntimeV2TurnResult`

Typed result objects:
- `RuntimeV2Reply`
- `RuntimeV2TurnResult`

## Hard Migration

The old dict-shaped compatibility path is removed from the Runtime v2 main interface in development.

That means:
- new adapter work should consume `RuntimeV2TurnResult`
- new CLI/runtime work should consume `RuntimeV2TurnResult`
- tests should assert typed fields first (`result.status`, `result.reply_text`, `result.delivery_kind`)

## Why

This removes three sources of drift:
1. runtime internals produce typed objects but adapters read loose dicts
2. adapters silently invent fallback field semantics
3. tests validate compatibility shape instead of the real contract

## Current Meaning

Runtime v2 result contract is now:
- status truth
- reply truth
- delivery kind truth
- suppressibility hint

owned by Runtime v2, not reconstructed by adapters.

## Remaining Work

The main remaining adapter-side cleanup is ingress policy generalization.

Current state:
- Telegram ingress inspection has moved into `app/runtime_v2/telegram_bridge.py`
- task/probe/challenge detection is no longer fully embedded in `telegram_bot.py`
- the bridge now provides ack/busy notice decisions used by the adapter
- bridge-side delivery planning now decides the final outbound text for Runtime v2 Telegram delivery
- Telegram runtime_v2 handling now follows a clearer orchestration skeleton: inspect -> pre-runtime action -> run turn -> deliver result

Still remaining:
- further generalize ingress/delivery bridge policy
- reduce remaining adapter-owned send plumbing
- move closer to transport-only Telegram behavior
- decide whether file-based Runtime v2 prompts should expand beyond the current `prompts/AGENT.md`, `prompts/SOUL.md`, `prompts/TOOLS.md` integration
