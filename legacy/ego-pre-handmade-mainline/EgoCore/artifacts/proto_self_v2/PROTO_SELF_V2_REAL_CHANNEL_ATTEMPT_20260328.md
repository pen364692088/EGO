# Proto-Self V2 Real Telegram Channel Attempt Report

## Scope

- authority source:
  - [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
  - [proto_self_v2.schema.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/contracts/proto_self_v2.schema.json)
  - [proto_self_adapter.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_adapter.py)
  - [proto_self_runtime.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py)
  - [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py)

## Real Channel Attempt

- channel: `real Telegram DM`
- session_key: `telegram:dm:8420019401`
- user-provided trigger sequence:
  1. `/new`
  2. `/proto v2 on`
  3. natural-language turns in the same DM session
- expected:
  - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`
- observed:
  - all captured real-channel samples in this attempt remained `proto_self.trace.v1`

## Captured Samples

| Sample | Ledger Path | Observed Trace Schema | Notes |
|---|---|---|---|
| `sample_20260328_190006_9546065b` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190006_9546065b/ledger.json` | `proto_self.trace.v1` | `/new` |
| `sample_20260328_190029_6d6af8d1` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190029_6d6af8d1/ledger.json` | `proto_self.trace.v1` | `你好啊` |
| `sample_20260328_190045_77df9d65` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190045_77df9d65/ledger.json` | `proto_self.trace.v1` | `你叫什么名字?` |
| `sample_20260328_190130_326ddde4` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190130_326ddde4/ledger.json` | `None` | task ingest turn, no trace payload |
| `sample_20260328_190136_9c6350c3` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190136_9c6350c3/ledger.json` | `proto_self.trace.v1` | `继续` |
| `sample_20260328_190311_b413f77c` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190311_b413f77c/ledger.json` | `proto_self.trace.v1` | `生成文件了吗 要落地到文件夹里` |
| `sample_20260328_190410_589b5587` | `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_190410_589b5587/ledger.json` | `proto_self.trace.v1` | `还是没有哦` |

## Decision

- result: `real_channel_v2_capture_not_established`
- evidence level:
  - `E4 negative evidence` for this attempt
- current best explanation:
  - two concurrent Telegram pollers were serving the same DM session:
    - `python.exe -u -m app.main --restore --telegram`
    - `python.exe -u -m app.main --telegram`
  - the duplicate-poller condition is consistent with the duplicated `/new` reply and the mixed real-channel evidence
  - after killing both pollers and relaunching a single clean `--telegram` process, the next real Telegram natural-language sample switched to `proto_self.trace.v2`

## Evidence Boundary

- this report proves:
  - the real Telegram channel was actually triggered
  - the resulting real-channel ledgers for this attempt did not switch to `proto_self.trace.v2`
- this report does not prove:
  - the newly committed `/proto v2 on` code path is wrong
  - `proto_self.v2` cannot be captured on the real Telegram channel after restart

## Next Minimal Closure Action

1. Restart the Telegram process onto the latest `origin/main`.
2. In the same real Telegram DM, send:
   - `/new`
   - `/proto v2 on`
   - one natural-language message
3. Re-check the newest sample under:
   - `artifacts/telegram_real_mainline_v1/real_telegram/sample_*/ledger.json`
4. Confirm:
   - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`

## Follow-up

- superseded by the later positive real-channel capture:
  - [PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md)
