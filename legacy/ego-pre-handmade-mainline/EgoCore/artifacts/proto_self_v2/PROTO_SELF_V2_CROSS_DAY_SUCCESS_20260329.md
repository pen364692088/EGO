# Proto-Self V2 Cross-Day Success

**Date**: 2026-03-29
**Status**: `PASS`

## Result

The defined claim

- `real-channel continuity + proto_self.v2 persistence across session resets and across days`

is now satisfied.

## Later-Day Evidence

Later-day `/new` anchor:

- `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260329_122242_8f01f48b/sample.json`

Counted later-day natural-language sample:

- `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260329_122250_7005b885/sample.json`

Observed fields:

- `source_type = real_channel`
- `session_id = telegram:dm:8420019401`
- `openemotion_result.schema_version = proto_self.output.v2`
- `openemotion_trace.schema_version = proto_self.trace.v2`

Additional later-day natural-language samples in the same session window:

- `sample_20260329_122259_1767e7c5`
- `sample_20260329_122307_9c311412`
- `sample_20260329_122319_5b9b9131`

## Final Counts

- same-day counted successful sessions:
  - `2 / 2`
- counted successful days:
  - `2 / 2`
- no stop rule fired in the counted windows

## Evidence Boundary

This report proves:

- real Telegram DM cross-day continuity reached
- `proto_self.output.v2` and `proto_self.trace.v2` persisted across the later-day session

This report does not prove:

- broader long-horizon stability beyond the observation plan
- admission or stage-level claims outside the proto-self v2 evidence scope
