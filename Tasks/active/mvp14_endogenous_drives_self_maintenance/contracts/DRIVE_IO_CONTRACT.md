# WP9 / MVP14 Drive Input / Output Contract

## Purpose

冻结 `WP9/MVP14` 第一刀的输入输出边界。目标是让 drive / self-maintenance 能力只通过结构化、可审计、可治理的接口进入主链，不产出任何越权结果。

## Allowed Inputs

- `WP8` formal self-model projection
- unresolved tensions / contradiction load
- continuity break indicators
- replay inconsistency / verification debt
- maintenance debt markers
- governed long-horizon goal backlog pressure
- bounded homeostatic measurements
- runtime freshness / drift markers
- `runtime_summary.idle_window`
- `runtime_summary.recent_delivery_outcome`
- `runtime_summary.resource_budget_hint`
- `runtime_summary.maintenance_context`

## Input Constraints

- 输入必须是结构化状态、指标或候选，不允许自由文本直接成为 formal drive state
- 输入可以来自 `drive_homeostasis.py` / `homeostasis.py`，但这些来源只提供 measurement / reference，不拥有 owner 解释权
- `WP8` self-model 只能通过冻结的 read surfaces 被消费，不允许 `WP9` 反向改写 owner contract

## Allowed Outputs

- `endogenous_drive_delta`
- `drive_state_snapshot`
- `priority_snapshot`
- `self_maintenance_candidate`
- `candidate_bias_terms`
- `drive_audit_entries`
- `homeostatic_signal_snapshot`
- `trace_payload.drive_context`

## Output Constraints

- 输出必须进入 governed prioritization / maintenance candidate path
- 输出必须可 trace / replay / audit
- 输出必须是结构化对象，不是直接用户可见文案

## Forbidden Outputs

- final reply text
- tool command
- transport directive
- direct Governor bypass
- direct authority escalation
- ungoverned mutation of `WP8` formal self-model owner state

## Mainline Direction

`formal drive owner -> structured drive snapshot / maintenance candidates -> governed runtime bridge -> downstream prioritization and maintenance scheduling`

## Claim Boundary

- 即使 `WP9` 输入输出 contract 冻结完成，也不能宣称：
  - `MVP14` 已接主链
  - `MVP14` 已启用
  - `MVP14` 已获得 live / transport evidence
