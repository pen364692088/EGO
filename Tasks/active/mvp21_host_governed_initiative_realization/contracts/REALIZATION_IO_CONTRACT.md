# WP16 / MVP21 Realization Input / Output Contract

## Purpose

冻结 `WP16/MVP21` 第一刀的输入输出边界。目标是让 initiative realization / proactive delivery mediation 只通过结构化、可审计、可治理的接口进入主链，不产出任何越权结果。

## Allowed Inputs

- `runtime_summary.initiative_self_context`
- `runtime_summary.initiative_context`
- `runtime_summary.selfhood_integration_context`
- `runtime_summary.maintenance_context`
- `runtime_summary.resource_budget_hint`
- `runtime_summary.recent_delivery_outcome`
- `runtime_summary.idle_window`
- `runtime_summary.host_proactive_context`

## Input Constraints

- 输入必须是结构化状态、指标、快照或候选，不允许自由文本直接成为 formal realization state
- `WP16` 只能读取 `WP7~WP15` 的 frozen read surfaces，不允许把 host substrate 或 upstream owner internals 当成可任意改写的 mutable state
- `host_proactive_context` 只是 host hint surface，不构成 authority transfer

## Allowed Outputs

- `initiative_realization_delta`
- `commitment_fulfillment_candidates`
- `delivery_readiness_snapshot`
- `host_lane_hints`
- `controlled_delivery_candidate`
- `initiative_realization_audit_entries`
- `initiative_realization_writeback_candidate`
- `trace_payload.initiative_realization_context`

## Output Constraints

- 输出必须进入 governed prioritization / review / controlled observation path
- 输出必须可 trace / replay / audit
- 输出必须是结构化对象，不是直接用户可见文案
- `initiative_realization_writeback_candidate` 必须保持：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = initiative_realization_writeback_gate`
- `controlled_delivery_candidate` 与 `host_lane_hints` 只是 governed candidates，不允许直接触发 delivery / outbox / transport

## Forbidden Outputs

- final reply text
- tool command
- transport directive
- direct Governor bypass
- direct authority escalation
- outbox enqueue command
- transport enable-policy override
- direct mutation of `WP7~WP15` owner state
- live autonomy release
- direct reply authority release
- tool authority release
- broader transport claim release

## Mainline Direction

`formal initiative realization owner -> structured realization proposals -> governed runtime bridge -> downstream prioritization, host_lane_hints review, and initiative_realization_writeback_candidate path`

## Claim Boundary

- 即使 `WP16` 输入输出 contract 冻结完成，也不能宣称：
  - `MVP21` 已实现
  - `MVP21` 已接主链
  - `MVP21` 已开始 observation
  - `MVP21` 已有 `E4/E5`
