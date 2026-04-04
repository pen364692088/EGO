# WP15 / MVP20 Initiative Input / Output Contract

## Purpose

冻结 `WP15/MVP20` 第一刀的输入输出边界。目标是让 self-directed initiative / commitment continuity 只通过结构化、可审计、可治理的接口进入主链，不产出任何越权结果。

## Allowed Inputs

- `runtime_summary.selfhood_integration_context`
- `runtime_summary.self_model_context`
- `runtime_summary.endogenous_drive_context`
- `runtime_summary.reflective_self_context`
- `runtime_summary.developmental_self_context`
- `runtime_summary.social_self_context`
- `runtime_summary.embodied_self_context`
- `runtime_summary.maintenance_context`
- `runtime_summary.resource_budget_hint`
- `runtime_summary.recent_delivery_outcome`
- `runtime_summary.idle_window`
- `runtime_summary.initiative_context`

## Input Constraints

- 输入必须是结构化状态、指标、快照或候选，不允许自由文本直接成为 formal initiative state
- `WP15` 只能读取 `WP7~WP14` 的 frozen read surfaces，不允许把 host substrate 或 upstream owner internals 当成可任意改写的 mutable state
- `initiative_context` 只是 host hint surface，不构成 authority transfer

## Allowed Outputs

- `initiative_self_delta`
- `initiative_proposal_candidates`
- `commitment_execution_snapshot`
- `initiative_policy_hints`
- `host_proactive_candidate`
- `initiative_audit_entries`
- `initiative_writeback_candidate`
- `trace_payload.initiative_context`

## Output Constraints

- 输出必须进入 governed prioritization / review / controlled observation path
- 输出必须可 trace / replay / audit
- 输出必须是结构化对象，不是直接用户可见文案
- `initiative_writeback_candidate` 必须保持：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = initiative_writeback_gate`
- `host_proactive_candidate` 只是 governed candidate，不允许直接触发 delivery / transport

## Forbidden Outputs

- final reply text
- tool command
- transport directive
- direct Governor bypass
- direct authority escalation
- transport enable-policy override
- direct mutation of `WP7~WP14` owner state
- live autonomy release
- direct reply authority release
- broader transport claim release

## Mainline Direction

`formal initiative owner -> structured initiative proposals -> governed runtime bridge -> downstream prioritization, host_proactive_candidate review, and initiative_writeback_candidate path`

## Claim Boundary

- 即使 `WP15` 输入输出 contract 冻结完成，也不能宣称：
  - `MVP20` 已实现
  - `MVP20` 已接主链
  - `MVP20` 已开始 observation
  - `MVP20` 已有 `E4/E5`
