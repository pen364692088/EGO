# Proto-Self V2 E5 Observation Plan

## Goal

Collect the minimum real Telegram DM evidence needed to move from:

- `real-channel E4 established`

to:

- `real-channel E5 observation reached`

for the narrow claim:

- `same real Telegram DM session can continue to emit proto_self.trace.v2 on consecutive natural-language turns`

## Authority Source

- [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
- [PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md)
- [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py)
- [proto_self_runtime.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py)

## Current Baseline

- session:
  - `telegram:dm:8420019401`
- single-live-poller:
  - required
- baseline positive sample:
  - `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260328_191554_f778b476`
- baseline proof:
  - `openemotion.result.schema_version == "proto_self.output.v2"`
  - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`

## Minimal E5 Target

- minimum positive natural-language samples:
  - `3`
- preferred positive natural-language samples:
  - `5`
- same session:
  - required
- same channel:
  - `real Telegram DM`
- command turns:
  - do not count toward the 3-5 positive observation samples

## Sampling Procedure

1. Keep only one live Telegram poller.
2. In the same Telegram DM session:
   - `/new`
   - `/proto v2 on`
3. Send `3-5` natural-language user messages in the same session.
4. After each message, inspect the newest real sample:
   - `artifacts/telegram_real_mainline_v1/real_telegram/sample_*/ledger.json`

## Acceptance Fields Per Counted Sample

Each counted sample must satisfy all of the following:

- `source_type == "real_channel"`
- user turn is natural language, not a command
- `openemotion.result.schema_version == "proto_self.output.v2"`
- `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`
- sample path is repo-tracked under:
  - `artifacts/telegram_real_mainline_v1/real_telegram/sample_*`

## Allowed Variance

- `openemotion.normalized_event` may be absent in the persisted real-channel ledger
- reply wording may vary
- exact cycle deltas may vary

These do not fail the observation as long as the required E5 fields above hold.

## Stop Rules

Stop the observation immediately if any of the following occurs:

1. duplicate Telegram replies appear for a single user turn
2. more than one live `--telegram` process is detected
3. a counted natural-language sample falls back to:
   - `proto_self.output.v1`
   - or `proto_self.trace.v1`
4. no real sample is generated for a natural-language turn
5. the session is implicitly reset or routed to a different session key

If stopped, file a blocker report before continuing.

## Success Rule

Mark `real-channel E5 observation reached` only if:

- at least `3` counted natural-language samples in the same real DM session
- all counted samples satisfy the acceptance fields
- no stop rule fired during the counted window

## Current Observation Status

- counted positive samples:
  - `5 / 5`
- counted sample set:
  - `sample_20260328_191554_f778b476`
  - `sample_20260328_192536_a18d7479`
  - `sample_20260328_192603_a2464e9d`
  - `sample_20260328_192644_59eaca3f`
  - `sample_20260328_192907_0f99c382`
- next required action:
  - observation threshold reached; file and maintain the E5 observation report
