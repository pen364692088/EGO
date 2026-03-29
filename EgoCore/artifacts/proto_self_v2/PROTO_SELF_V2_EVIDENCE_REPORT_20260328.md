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
- ingress selector: default Telegram natural-language mainline
- ingress merge point:
  - `TelegramBot._handle_with_runtime_v2()`
  - default path resolves to `proto_self.v2`
  - `/proto off` is only a session-scoped compatibility fallback
- expected schema_version chain:
  - normalized_event: `proto_self.v2`
  - openemotion_result: `proto_self.output.v2`
  - openemotion_trace: `proto_self.trace.v2`
- persisted ledger trace path:
  - `sample_*/ledger.json -> openemotion.trace_payload.schema_version`
- verification command:
  - `PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q EgoCore/tests/test_telegram_proto_self_v2_evidence.py`

## Real Telegram capture procedure

1. Ensure the live Telegram process has been restarted after the default-v2 mainline landed on `main`.
2. Send `/new` in the target Telegram DM session.
3. Send one natural-language message in the same session.
4. Optional diagnostic:
   - send `/proto status`
   - or `/proto v2 on`
5. Check the newest real sample under:
   - `artifacts/telegram_real_mainline_v1/real_telegram/sample_*/ledger.json`
6. Confirm:
   - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`

## Real Telegram attempt tracking

- artifact index:
  - [README.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/README.md)
- update log:
  - [PROTO_SELF_V2_UPDATE_LOG_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_UPDATE_LOG_20260328.md)
- first negative real-channel attempt:
  - [PROTO_SELF_V2_REAL_CHANNEL_ATTEMPT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_ATTEMPT_20260328.md)
- first positive real-channel capture:
  - [PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md)
- E5 observation plan:
  - [PROTO_SELF_V2_E5_OBSERVATION_PLAN.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_PLAN.md)
- E5 observation result:
  - [PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md)
- cross-session observation plan:
  - [PROTO_SELF_V2_CROSS_SESSION_OBSERVATION_PLAN.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_CROSS_SESSION_OBSERVATION_PLAN.md)
- cross-session observation status:
  - [PROTO_SELF_V2_CROSS_SESSION_STATUS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_CROSS_SESSION_STATUS_20260328.md)
- live process version report:
  - [PROTO_SELF_V2_LIVE_PROCESS_VERSION_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_LIVE_PROCESS_VERSION_REPORT_20260328.md)
- live process version json:
  - [LIVE_TELEGRAM_PROCESS_VERSION.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json)

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
  - the real Telegram channel can persist `proto_self.output.v2` and `proto_self.trace.v2` on the Telegram natural-language mainline
  - the same real Telegram DM session has now produced `5/5` counted natural-language samples with `proto_self.output.v2 + proto_self.trace.v2`
  - the current live Telegram process version is repo-tracked and currently bound to commit `468d9a4`
- this report does not prove:
  - cross-session or cross-day stability
  - broader real-channel admission evidence
  - normalized-event parity across every evidence path
