# MVP15 Maintenance Ledger

## Purpose

`WP10/MVP15` 已进入维护态。后续新增样本、补充 observation、预算层波动和非 scope 变动统一记在这里，不自动触发 `WP10` scope reopen。

## Frozen Completion Context

- closure artifact:
  - `OpenEmotion/artifacts/mvp15/MVP15_COMPLETION_CURRENT.md`
- current batch report:
  - `OpenEmotion/artifacts/mvp15/mvp15_controlled_observation_batch_current.md`
- current status:
  - `Tasks/active/mvp15_reflective_self_counterfactual/STATUS.md`

## Reopen Policy

默认不 reopen `WP10`。仅当出现以下任一项时，才允许升级为 reopen 讨论：

- formal owner writeback regression
- proposal discipline regression
- behavioral authority regression
- replay consistency regression
- authority boundary regression
- evidence classification regression

## External Budget Risk Register

### 2026-04-03

- batch 运行期间仍可能出现 chat provider transient `429/401`
- 当前归类：`external_budget_risk`
- 当前影响：会影响重复运行预算稳定性
- 当前不构成：`WP10 blocker`
- 升级条件：只有在 formal owner writeback 主链因此失效时，才升级处理

## Sample Intake Rule

- `WP10` 新增 controlled observation 样本只在本 ledger 追加记录
- 这些样本不会自动改变 `WP10 maintenance_mode`
- 若样本触发 reopen policy，再单独开裁决，不直接在后续阶段文档里偷改
