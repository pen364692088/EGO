# WP14 / MVP19 Selfhood Integration Input / Output Contract

## Purpose

冻结 `WP14/MVP19` 第一刀的输入输出边界。目标是让 cross-axis self-integration / self-maintenance arbitration 只通过结构化、可审计、可治理的接口进入主链，不产出任何越权结果。

## Allowed Inputs

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
- `WP8`: self-model confidence / identity consistency / known-unknowns constraints
- `WP9`: `candidate_bias_terms`, `priority_snapshot`, `self_maintenance_candidate`
- `WP10`: `revision_proposal_candidates`, `confidence_adjustment_hints`, `maintenance_priority_hints`
- `WP11`: `developmental_proposal_candidates`, `developmental_priority_hints`, `developmental_continuity_snapshot`
- `WP12`: `relation_update_candidates`, `repair_proposal_candidates`, `social_policy_hints`, `trust_commitment_snapshot`
- `WP13`: `consequence_update_candidates`, `repair_or_stabilize_proposal_candidates`, `embodied_policy_hints`, `resource_boundary_snapshot`

## Input Constraints

- 输入必须是结构化状态、指标、快照或候选，不允许自由文本直接成为 formal integration state
- `WP14` 只能读取 `WP8~WP13` 的 frozen read surfaces，不允许把 upstream owner internals 当成可任意改写的 mutable state
- `recent_delivery_outcome`、`idle_window`、`resource_budget_hint` 与 `maintenance_context` 只用于仲裁权重和 writeback gating 提示，不构成行为授权

## Allowed Outputs

- `self_integration_delta`
- `cross_axis_priority_snapshot`
- `proposal_conflict_snapshot`
- `integrated_policy_hints`
- `integrated_tendency_proposal`
- `axis_arbitration_hints`
- `integration_audit_entries`
- `self_integration_writeback_candidate`
- `trace_payload.selfhood_integration_context`

## Output Constraints

- 输出必须进入 governed prioritization / review / controlled observation path
- 输出必须可 trace / replay / audit
- 输出必须是结构化对象，不是直接用户可见文案
- `self_integration_writeback_candidate` 必须保持：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = self_integration_writeback_gate`
- `axis_arbitration_hints` 必须保持 advisory only，不允许直接改写 `WP8~WP13` owner state

## Phase 1 Arbitration Policy

- `stability-first`
- priority 1：若 `WP8` low confidence，或 `WP9/WP13` 出现高 maintenance / resource / boundary pressure，则优先 `stabilize / conserve / guard / review`
- priority 2：否则，`WP12` commitment / repair risk 可抬高 repair bias
- priority 3：否则，`WP11` growth / continuity 可抬高 growth bias
- priority 4：`WP10` reflective revision 只作 modifier，不是更高优先轴

## Forbidden Outputs

- final reply text
- tool command
- transport directive
- direct Governor bypass
- direct authority escalation
- direct mutation of `WP8~WP13` owner state
- live autonomy release
- direct reply authority release
- broader transport claim release

## Mainline Direction

`formal selfhood integration owner -> structured cross-axis arbitration proposals -> governed runtime bridge -> downstream prioritization, proposal conflict review, and self_integration_writeback_candidate path`

## Claim Boundary

- 即使 `WP14` 输入输出 contract 冻结完成，也不能宣称：
  - `MVP19` 已实现
  - `MVP19` 已接主链
  - `MVP19` 已开始 observation
  - `MVP19` 已有 `E4/E5`

