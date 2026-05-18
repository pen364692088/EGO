# Proto-Self V2 Cross-Session Observation Plan

## Goal

Upgrade the evidence claim from:

- `same-session real-channel E5 observation reached`

to the next narrower claim:

- `real-channel continuity + proto_self.v2 persistence across session resets and across days`

## Authority Source

- [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
- [PROTO_SELF_V2_E5_OBSERVATION_PLAN.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_PLAN.md)
- [PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_REPORT_20260328.md)

## Observation Units

- counted successful session:
  - one repo-tracked `/new` command sample
  - at least one later repo-tracked natural-language sample in the same DM session window
  - optional diagnostic sample:
    - `/proto v2 on`
    - may be used to confirm default-v2 posture, but is not required for counted success
  - command samples are identified from `sample.json` by:
    - `raw_update.message.text`
    - `normalized_event.conversation_context.session_id`
  - natural-language samples are identified from `sample.json` by:
    - `raw_update.message.text`
    - `normalized_event.conversation_summary.session_id`
    - `openemotion_result.schema_version`
    - `openemotion_trace.schema_version`
  - at least one counted natural-language sample in that session must satisfy:
    - `source_type == "real_channel"`
    - `openemotion_result.schema_version == "proto_self.output.v2"`
    - `openemotion_trace.schema_version == "proto_self.trace.v2"`
- counted successful day:
  - a calendar day containing at least one counted successful session

## Current Baseline

- same-session observation:
  - reached
- counted successful sessions:
  - `1`
- counted successful days:
  - `1`
- current successful session anchor:
  - session 1 date: `2026-03-28`
  - session 1 command anchor:
    - `/new`:
      - `sample_20260328_191541_743c02b0`
  - session 1 optional diagnostic anchor:
    - `/proto v2 on`:
      - `sample_20260328_191549_923b4480`
  - session 1 counted natural-language samples:
    - `sample_20260328_191554_f778b476`
    - `sample_20260328_192536_a18d7479`
    - `sample_20260328_192603_a2464e9d`
    - `sample_20260328_192644_59eaca3f`
    - `sample_20260328_192907_0f99c382`
  - session 2 date: `2026-03-28`
  - session 2 command anchor:
    - `/new`:
      - `sample_20260328_194852_a212e63a`
  - session 2 optional diagnostic anchor:
    - `/proto v2 on`:
      - `sample_20260328_194857_86065453`
  - session 2 counted natural-language samples:
    - `sample_20260328_194904_9519d887`
    - `sample_20260328_194944_586667ef`

## Minimal Target

- same-DM cross-session target:
  - at least `2` counted successful sessions
  - the sessions must be separated by an explicit `/new`
- cross-day target:
  - at least `2` counted successful days
  - the second day must contain at least one counted successful session

## Sampling Procedure

### Phase A: Cross-session, same day

1. In the same Telegram DM, send:
   - `/new`
2. Send at least one natural-language message.
3. Inspect the newest real sample directory and collect:
   - command sample for `/new`
   - natural-language sample after the override
   - optional diagnostic sample for `/proto v2 on`
4. Count the session only if the acceptance fields hold.

### Phase B: Cross-day

1. On a later calendar day, repeat:
   - `/new`
   - at least one natural-language message
   - optional `/proto v2 on` if diagnostic confirmation is needed
2. Inspect the newest real sample directory.
3. Count the day only if at least one session on that day is successful.

## Acceptance Fields

Every counted successful session must satisfy:

- repo-tracked `/new` anchor sample:
  - `sample.json.raw_update.message.text == "/new"`
  - `sample.json.normalized_event.conversation_context.session_id == "telegram:dm:8420019401"`
- optional repo-tracked `/proto v2 on` diagnostic sample:
  - if present, `sample.json.raw_update.message.text == "/proto v2 on"`
  - if present, `sample.json.normalized_event.conversation_context.session_id == "telegram:dm:8420019401"`
- counted natural-language sample:
  - `sample.json.source_type == "real_channel"`
  - `sample.json.raw_update.message.text` is present and does not start with `/`
  - `sample.json.normalized_event.conversation_summary.session_id == "telegram:dm:8420019401"`
  - `sample.json.openemotion_result.schema_version == "proto_self.output.v2"`
  - `sample.json.openemotion_trace.schema_version == "proto_self.trace.v2"`
- counted natural-language sample timestamp must be later than the `/new` anchor sample

## Stop Rules

Stop and file a blocker report if any of the following occurs:

1. duplicate Telegram replies appear for a single user turn
2. more than one live `--telegram` process is detected
3. a candidate natural-language turn after `/proto v2 on` falls back to:
   - `proto_self.output.v1`
   - or `proto_self.trace.v1`
4. no real sample is generated after a candidate natural-language turn
5. the successful session cannot be tied to an explicit `/new` anchor and a later natural-language sample in the same DM session window

## Time Integrity Rule

- manual system clock changes do not count toward `cross-day` evidence
- a clock-shifted sample may be recorded only as:
  - `clock-shift / day-rollover compatibility`
- it must not be counted as:
  - `real-calendar-day continuity`
- counted `cross-day` evidence must come from a later real calendar day in the normal running environment

## Success Rule

Mark `cross-session real-channel continuity + v2 persistence reached` only if:

- `2 / 2` counted successful sessions
- `2 / 2` counted successful days
- no stop rule fired in the counted windows

## Current Status

- cross-session same-day:
  - `2 / 2`
- cross-day:
  - `1 / 2`
- next required action:
  - fastest path to closure:
    - capture one successful session on a later calendar day
  - optional diagnostic step:
    - use `/proto status` or `/proto v2 on` to confirm mainline posture before the next later-day natural-language turn
  - operator reminder:
    - on the next real calendar day, remind the operator to run:
      - `/new`
      - one natural-language Telegram message
