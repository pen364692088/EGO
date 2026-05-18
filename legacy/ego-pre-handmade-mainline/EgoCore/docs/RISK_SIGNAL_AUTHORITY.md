# Risk Signal Authority

P7 defines a single formal authority for runtime risk signal generation.

## Canonical Source

- Generator: `EgoCore/app/risk_signal.py`
- Canonical field: `safety_context.risk_level`
- Canonical values: `low`, `medium`, `high`, `critical`

`EgoCore` owns risk generation. Runtime modules may consume the canonical scorer, but they must not maintain their own keyword tables or parallel score rules.

## Consumer Boundary

- `EgoCore/app/runtime_v2/proto_self_runtime.py` consumes the canonical scorer and emits canonical `risk_level`.
- `EgoCore/app/runtime/context_assembler.py` consumes the canonical scorer for approval hints.
- `EgoCore/app/runtime/semantic_router.py` consumes the canonical scorer for routing safeguards.
- `EgoCore/app/runtime/approval_policy.py` consumes the canonical scorer for operation confirmation.
- `OpenEmotion/openemotion/proto_self/schemas.py` normalizes compatibility input and consumes canonical `risk_level`.

## Compatibility Policy

- Legacy input alias `safety_context.risk` is compatibility-only input.
- Numeric `risk_level` values are compatibility-only input and must be normalized before downstream use.
- Canonical producers must emit string `risk_level` values only.

## Guardrail

If a new module needs risk semantics, it must import `app.risk_signal` instead of copying a keyword list or inventing a second score mapping.
