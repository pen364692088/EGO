# WP8 Boundary Freeze For WP9

## Purpose

启动 `WP9` 不能重开 `WP8`。本文件冻结 `WP8/MVP13` 与 `WP9/MVP14` 之间的边界，防止阶段偷换。

## Frozen WP8 Facts

- `WP8/MVP13` 已在 controlled observation 轴上达到 `V5/E5`
- `WP8` 当前状态是 `maintenance_mode`
- `WP8` 的 formal owner 仍固定为：
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/schemas/self_model.schema.json`
- `proto_self_v2.state.self_model` 仍只表示 runtime-local projection

## Maintenance Rule

- `WP8` 后续新增样本只进入：
  - `Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md`
- 默认不会因为新增样本自动 reopen `WP8`
- 只有以下情况才允许考虑 reopen：
  - formal owner writeback regression
  - replay / invariant regression
  - authority boundary regression
  - evidence classification regression

## External Risk Classification Rule

- provider `429/401` 持续标注为外部预算层风险
- 只有当它们导致 formal owner writeback 主链失效时，才可升级为 `WP8` blocker
- 单纯预算波动、速率限制、认证波动，不构成 `WP8` reopen 条件

## Non-Regression Rules

- `WP9` 不得改写 `WP8` 的 formal read path / formal write path
- `WP9` 不得把 `WP8` 的 controlled `E5` 改写成 live maturity claim
- `WP9` 不得借 `WP8 pass` 放开 OpenEmotion direct reply authority
- `WP9` 不得借 `WP8 pass` 放开 broader transport claims
