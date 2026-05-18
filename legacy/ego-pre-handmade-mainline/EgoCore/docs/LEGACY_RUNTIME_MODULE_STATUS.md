# Legacy Runtime Module Status

## Formal Mainline

- Telegram Runtime v2 under `app/runtime_v2/*` is the formal mainline for current Telegram runtime behavior.
- Legacy runtime files under `app/runtime/*` remain present only for compatibility containment and historical references.

## Compatibility-Only Paths

- `app/runtime/agent_runner.py`
- `app/runtime/request_classifier.py`
- `app/runtime/request_registry.py`

## Notes

- These modules are kept so older call sites and historical tests can resolve imports during transition.
- They are not the authority source for Telegram Runtime v2 mainline behavior.
