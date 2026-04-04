# MVP17 Maintenance Ledger

## Purpose

`WP12/MVP17` 已进入维护态。后续新增样本、补充 observation、预算层波动和非 scope 变动统一记在这里，不自动触发 `WP12` scope reopen。

## Frozen Completion Context

- closure artifact:
  - `OpenEmotion/artifacts/mvp17/MVP17_COMPLETION_CURRENT.md`
- current batch report:
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_batch_current.md`
- current status:
  - `Tasks/active/mvp17_social_self_other_modeling/STATUS.md`
- QA baseline:
  - `Tasks/active/mvp17_social_self_other_modeling/WP12_QA_BASELINE.md`

## Reopen Policy

默认不 reopen `WP12`。仅当出现以下任一项时，才允许升级为 reopen 讨论：

- formal owner writeback regression
- proposal discipline regression
- behavioral authority regression
- replay consistency regression
- authority boundary regression
- evidence classification regression

## External Budget Risk Register

### 2026-04-04

- batch 与 single controlled runner 期间可能出现 provider transient `429/401`
- 当前归类：`external_budget_risk`
- 当前影响：会影响重复运行预算稳定性
- 当前不构成：`WP12 blocker`
- 升级条件：只有在 formal owner writeback 主链因此失效时，才升级处理

## Sample Intake Rule

- `WP12` 新增 controlled observation 样本只在本 ledger 追加记录
- maintenance 回归判断统一对照 `WP12_QA_BASELINE.md`
- 这些样本不会自动改变 `WP12 maintenance_mode`
- 若样本触发 reopen policy，再单独开裁决，不直接在后续阶段文档里偷改

## Entries

### 2026-04-04 — Controlled closeout baseline established

- refreshed evidence:
  - `OpenEmotion/artifacts/mvp17/mvp17_causal_validation_current.md`
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_current.md`
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_batch_current.md`
- outcome:
  - `causal proof = pass (V3/E3)`
  - `single controlled observation = pass (V4/E4)`
  - `batch controlled observation = pass (V5/E5)`
  - `proposal_only_discipline_count = 3/3`
  - `behavioral_authority_none_count = 3/3`
  - `bounded_influence_present_count = 3/3`
  - `replay_consistent_count = 3/3`
- reopen decision:
  - `no`
- notes:
  - closeout scope only covers the formal owner + proposal-only social writeback + controlled observation axis
