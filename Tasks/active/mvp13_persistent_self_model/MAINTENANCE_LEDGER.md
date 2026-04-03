# MVP13 Maintenance Ledger

## Purpose

`WP8/MVP13` 已进入维护态。后续新增样本、补充 observation、预算层波动和非 scope 变动统一记在这里，不自动触发 `WP8` scope reopen。

## Frozen Completion Context

- closure artifact:
  - `OpenEmotion/artifacts/mvp13/MVP13_COMPLETION_CURRENT.md`
- current batch report:
  - `OpenEmotion/artifacts/mvp13/mvp13_controlled_observation_batch_current.md`
- current status:
  - `Tasks/active/mvp13_persistent_self_model/STATUS.md`

## Reopen Policy

默认不 reopen `WP8`。仅当出现以下任一项时，才允许升级为 reopen 讨论：

- formal owner writeback regression
- replay consistency regression
- invariant violation regression
- authority boundary regression
- evidence classification regression

## External Budget Risk Register

### 2026-04-03

- batch 运行期间出现 chat provider transient `429/401`
- 当前归类：`external_budget_risk`
- 当前影响：会影响重复运行预算稳定性
- 当前不构成：`WP8 blocker`
- 升级条件：只有在 formal owner writeback 主链因此失效时，才升级处理

## Sample Intake Rule

- `WP8` 新增 controlled observation 样本只在本 ledger 追加记录
- 这些样本不会自动改变 `WP8 maintenance_mode`
- 若样本触发 reopen policy，再单独开裁决，不直接在 `WP9` 文档里偷改
