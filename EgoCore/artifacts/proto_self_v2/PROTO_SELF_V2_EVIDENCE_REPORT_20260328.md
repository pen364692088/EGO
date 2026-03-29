# Proto-Self V2 Evidence Report

## Scope

- authority source:
  - [PROTO_SELF_KERNEL_V2_SPEC.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/docs/PROTO_SELF_KERNEL_V2_SPEC.md)
  - [proto_self_v2.schema.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/contracts/proto_self_v2.schema.json)
  - [proto_self_adapter.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py)
  - [proto_self_runtime.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py)
  - [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py)

## Captures

### Capture A: Runtime mainline, repo-local

- entry: `RuntimeV2Loop.run_turn_typed()`
- ingress selector: `state.ingress_context["proto_self_version"] = "v2"`
- expected schema_version chain:
  - normalized_event: `proto_self.v2`
  - openemotion_result: `proto_self.output.v2`
  - openemotion_trace: `proto_self.trace.v2`
- ledger trace path:
  - `sample.ledger["openemotion"]["trace_payload"]["schema_version"]`
- verification command:
  - `PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q EgoCore/tests/test_runtime_v2_proto_self_runtime.py`

### Capture B: Telegram external entry, repo-local

- entry: `TelegramBot.handle_message()`
- ingress selector: session-scoped Telegram command `/proto v2 on`
- ingress merge point: `TelegramBot._handle_with_runtime_v2() -> state.ingress_context["proto_self_version"] = "v2"`
- expected schema_version chain:
  - normalized_event: `proto_self.v2`
  - openemotion_result: `proto_self.output.v2`
  - openemotion_trace: `proto_self.trace.v2`
- persisted ledger trace path:
  - `sample_*/ledger.json -> openemotion.trace_payload.schema_version`
- verification command:
  - `PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q EgoCore/tests/test_telegram_proto_self_v2_evidence.py`

## Real Telegram capture procedure

1. Ensure the live Telegram process has been restarted after the `/proto v2 on` feature landed on `main`.
2. Send `/proto v2 on` in the target Telegram DM session.
3. Send one natural-language message in the same session.
4. Check the newest real sample under:
   - `artifacts/telegram_real_mainline_v1/real_telegram/sample_*/ledger.json`
5. Confirm:
   - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`

## Real Telegram attempt tracking

- first negative real-channel attempt:
  - [PROTO_SELF_V2_REAL_CHANNEL_ATTEMPT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_ATTEMPT_20260328.md)
- first positive real-channel capture:
  - [PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md)
- E5 observation plan:
  - [PROTO_SELF_V2_E5_OBSERVATION_PLAN.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_PLAN.md)
- E5 observation result:
  - [PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md)

## Contract gate

- pre-route validator:
  - [proto_self_contract_validator.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_contract_validator.py)
- adapter enforcement point:
  - [proto_self_adapter.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py)
- negative verification:
  - missing required `event` must fail before V2 routing
  - command:
    - `PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q EgoCore/tests/test_proto_self_v2_contracts.py`

## Evidence boundary

- this report proves:
  - `proto_self.v2` ingress payload is contract-checked before adapter routing
  - the repo-local runtime mainline can emit `proto_self.trace.v2`
  - the repo-local Telegram external entry can persist `proto_self.trace.v2` into `ledger.json`
  - the real Telegram channel can persist `proto_self.output.v2` and `proto_self.trace.v2` in a natural-language turn after explicit `/proto v2 on`
  - the same real Telegram DM session has now produced `5/5` counted natural-language samples with `proto_self.output.v2 + proto_self.trace.v2`
- this report does not prove:
  - V2 is now the default runtime mainline
  - cross-session or cross-day stability
  - broader real-channel admission evidence
  - normalized-event parity across every evidence path
