# RUNTIME_V2_FILE_PROMPT_SYSTEM.md

> Status: development active
> Scope: file-based prompt loading for Runtime v2

## Goal

Introduce a simple file-based prompt system similar in spirit to AGENT.md / SOUL.md / TOOLS.md, while keeping Runtime v2 stable.

## Current Files

Runtime v2 now loads these files from `prompts/`:
- `prompts/AGENT.md`
- `prompts/SOUL.md`
- `prompts/TOOLS.md`

## Current Integration

Current integration point:
- `app/runtime_v2/decision_engine.py`

Behavior:
1. load markdown prompt files from `prompts/`
2. render them into the Runtime v2 system prompt
3. append the built-in Runtime v2 action/output contract
4. fall back to built-in prompt if files are missing

## Why This Shape

This is intentionally minimal:
- file-editable prompt surface
- Runtime v2 integration first
- no large cross-runtime migration yet

## What `/context list` Shows

`/context list` now shows:
- prompt root
- loaded prompt files

This makes the active prompt surface visible during Telegram testing.

## Not Yet Done

This does not yet replace:
- legacy `config/prompts.yaml` usage in older runtime modules
- older code-embedded system prompts outside Runtime v2

## Next Natural Extension

If this file-based prompt path proves stable, the next step is:
1. add more explicit prompt layering rules
2. decide whether old runtime prompt consumers should migrate
3. decide whether Telegram commands should expose prompt status/edit helpers
