# Proto-Self V2 Real Telegram Channel Success Report

## Scope

- authority source:
  - [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
  - [proto_self_v2.schema.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/contracts/proto_self_v2.schema.json)
  - [proto_self_adapter.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py)
  - [proto_self_runtime.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py)
  - [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py)

## Real Channel Success Capture

- channel: `real Telegram DM`
- session_key: `telegram:dm:8420019401`
- single live poller requirement:
  - satisfied
  - verified after killing the duplicate `--restore --telegram` poller and keeping one clean `--telegram` process
- user trigger sequence:
  1. `/new`
  2. `/proto v2 on`
  3. `你好啊`

## Positive Sample

- sample directory:
  - `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_191554_f778b476`
- ledger path:
  - `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_191554_f778b476/ledger.json`
- source_type:
  - `real_channel`
- observed schema chain:
  - `openemotion.result.schema_version == "proto_self.output.v2"`
  - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`
- observed user text:
  - `你好啊`

## Decision

- result:
  - `real_channel_v2_capture_established`
- evidence level:
  - `E4`
- why this counts:
  - the capture came from the real Telegram DM entry
  - the natural-language turn, not only repo-local tests, produced `proto_self.output.v2` and `proto_self.trace.v2`
  - the resulting evidence is persisted in the real-channel sample ledger

## Evidence Boundary

- this report proves:
  - a real Telegram channel natural-language turn can enter the controlled `proto_self.v2` path
  - the real-channel ledger can persist `proto_self.output.v2`
  - the real-channel ledger can persist `proto_self.trace.v2`
- this report does not prove:
  - `proto_self.v2` is now the default mainline for all Telegram turns
  - every command turn (`/new`, `/proto`) will emit V2 trace payloads
  - long-run stability or E5
  - broader MVP admission claims

## Notes

- in this successful real-channel sample, `openemotion.normalized_event` was not present in the persisted ledger
- the positive E4 claim for real Telegram should therefore be stated narrowly as:
  - `real_channel -> proto_self.output.v2 + proto_self.trace.v2 persisted in ledger`
