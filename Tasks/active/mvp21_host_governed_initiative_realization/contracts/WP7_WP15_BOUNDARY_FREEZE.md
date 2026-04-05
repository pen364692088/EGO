# WP7~WP15 Boundary Freeze For WP16

## Frozen Upstream State

- `WP7~WP15` 当前都保持 maintenance / frozen upstream 状态
- 各 phase 的 formal owner、formal read/write path、evidence claim 与 maintenance ledger 仍各自由其 phase authority 管理
- `WP16` 启动不构成任何 upstream reopen

## What WP16 May Read

- `runtime_summary.initiative_self_context`
- `runtime_summary.initiative_context`
- `runtime_summary.selfhood_integration_context`
- `runtime_summary.maintenance_context`
- `runtime_summary.resource_budget_hint`
- `runtime_summary.recent_delivery_outcome`
- `runtime_summary.idle_window`
- `runtime_summary.host_proactive_context`

## What WP16 May Not Do

- 不得改写 `WP7~WP15` formal owner contract
- 不得直接回写 `initiative_self/*`、`selfhood_integration/*`、`self_model/*`、`endogenous_drives/*`、`reflective_self/*`、`developmental_self/*`、`social_self/*`、`embodied_self/*`
- 不得把 `WP7` host proactive delivery / outbox / transport substrate 升格成 `WP16` semantic owner
- 不得把 `WP7~WP15` maintenance institutionalization、controlled evidence 或 frozen upstream status 升格为 `WP16` implementation / mainline / observation / maintenance proof
- 不得因 `WP16` 启动而 reopen `WP7~WP15`
- 不得把 upstream bounded outputs 解释成 live autonomy、direct reply authority、tool authority、或 broader transport maturity
