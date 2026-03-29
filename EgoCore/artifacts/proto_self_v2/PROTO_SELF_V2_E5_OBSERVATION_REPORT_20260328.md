# Proto-Self V2 E5 Observation Report

## Scope

- authority source:
  - [PROTO_SELF_V2_E5_OBSERVATION_PLAN.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_E5_OBSERVATION_PLAN.md)
  - [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
  - [PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_REAL_CHANNEL_SUCCESS_20260328.md)

## Decision

- result:
  - `real-channel E5 observation reached`
- claim scope:
  - `same real Telegram DM session can continue to emit proto_self.output.v2 + proto_self.trace.v2 on consecutive natural-language turns after explicit /proto v2 on`

## Counted Samples

The following samples satisfy the plan acceptance fields:

| Count | Sample | User Text | Result Schema | Trace Schema |
|---|---|---|---|---|
| 1 | `sample_20260328_191554_f778b476` | `你好啊` | `proto_self.output.v2` | `proto_self.trace.v2` |
| 2 | `sample_20260328_192536_a18d7479` | `你叫什么名字?` | `proto_self.output.v2` | `proto_self.trace.v2` |
| 3 | `sample_20260328_192603_a2464e9d` | `能帮我看看今天温尼伯多少温度吗` | `proto_self.output.v2` | `proto_self.trace.v2` |
| 4 | `sample_20260328_192644_59eaca3f` | `你可以学习用API去查询吗` | `proto_self.output.v2` | `proto_self.trace.v2` |
| 5 | `sample_20260328_192907_0f99c382` | `方案1吧` | `proto_self.output.v2` | `proto_self.trace.v2` |

## Plan Conformance

- same session:
  - satisfied
  - `telegram:dm:8420019401`
- same channel:
  - satisfied
  - `real Telegram DM`
- minimum positive natural-language samples:
  - satisfied
  - `5 / 3`
- preferred positive natural-language samples:
  - satisfied
  - `5 / 5`
- stop rules fired:
  - none during the counted window

## Evidence Boundary

- this report proves:
  - `proto_self.v2` can remain active across multiple consecutive natural-language turns in the same real Telegram DM session
  - the persisted real-channel ledgers continue to emit both `proto_self.output.v2` and `proto_self.trace.v2`
- this report does not prove:
  - `proto_self.v2` is the default path for all Telegram traffic
  - command turns such as `/new` or `/proto` themselves emit V2
  - cross-session or cross-day stability
  - broader MVP admission claims
