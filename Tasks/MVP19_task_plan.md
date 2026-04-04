# MVP19 / WP14 Cross-Axis Self-Integration / Self-Maintenance Arbitration

> 状态：observation_passed
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP14`
> predecessor: `WP13/MVP18`
> same_subject_line: `true`
> not_parallel_track: `true`
> docs_only_authority_package: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 host-governed、proposal-only 的 cross-axis self-integration / self-maintenance arbitration；第一刀只冻结跨轴整合语义、formal intake/output 与 `stability-first` 仲裁策略，不放开任何行为权、外发权、transport claim 或 upstream owner rewrite。

## Real Goal
- 把 `WP14/MVP19` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP14/MVP19` 的 authority source 冻结到当前正式主线
- 把 `WP14/MVP19` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP8~WP13` 向 `WP14` 的上游边界，不让 `WP14` 反向改写 upstream owner state
- 明确当前仍然不放开的 selfhood integration 能力，防止“已有多轴 proposal => 已有 live integrated authority”的错误升级

## Non-Goals
- 不宣称 owner/runtime 已实现
- 不宣称已接当前 runtime 主链
- 不宣称 `E4/E5`
- 不宣称 observation started
- 不宣称 maintenance mode
- 不 reopen `WP8~WP13`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims
- 不允许 direct reply / tool command / transport directive / authority escalation

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP14` phase-detail authority：
  - `Tasks/MVP19_task_plan.md`
- technical reference：
  - `Tasks/MVP13_task_plan.md`
  - `Tasks/MVP14_task_plan.md`
  - `Tasks/MVP15_task_plan.md`
  - `Tasks/MVP16_task_plan.md`
  - `Tasks/MVP17_task_plan.md`
  - `Tasks/MVP18_task_plan.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- 说明：
  - 当前没有 repo-tracked `OpenEmotion/roadmap/versions/MVP19.spec.yaml`
  - 若后续新增 `MVP19` version spec，它在 authority 显式更新前只能作为 technical reference

## Locked Decisions
- `WP14/MVP19` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/selfhood_integration/*`
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP14` phase 1 formal intake 只覆盖冻结 read surfaces：
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
- phase 1 formal arbitration inputs 明确包括：
  - `WP8`: self-model confidence / identity consistency / known-unknowns constraints
  - `WP9`: `candidate_bias_terms`, `priority_snapshot`, `self_maintenance_candidate`
  - `WP10`: `revision_proposal_candidates`, `confidence_adjustment_hints`, `maintenance_priority_hints`
  - `WP11`: `developmental_proposal_candidates`, `developmental_priority_hints`, `developmental_continuity_snapshot`
  - `WP12`: `relation_update_candidates`, `repair_proposal_candidates`, `social_policy_hints`, `trust_commitment_snapshot`
  - `WP13`: `consequence_update_candidates`, `repair_or_stabilize_proposal_candidates`, `embodied_policy_hints`, `resource_boundary_snapshot`
- phase 1 formal outputs 固定为：
  - `self_integration_delta`
  - `cross_axis_priority_snapshot`
  - `proposal_conflict_snapshot`
  - `integrated_policy_hints`
  - `integrated_tendency_proposal`
  - `axis_arbitration_hints`
  - `integration_audit_entries`
  - `self_integration_writeback_candidate`
  - `trace_payload.selfhood_integration_context`
- proposal discipline 固定为：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = self_integration_writeback_gate`
  - `axis_arbitration_hints` 只是 advisory，不能直接改写 `WP8~WP13` owner state
- phase 1 arbitration policy 固定为 `stability-first`：
  - priority 1：若 `WP8` low confidence，或 `WP9/WP13` 出现高 maintenance / resource / boundary pressure，则优先 `stabilize / conserve / guard / review`
  - priority 2：否则，`WP12` commitment / repair risk 可抬高 repair bias
  - priority 3：否则，`WP11` growth / continuity 可抬高 growth bias
  - priority 4：`WP10` reflective revision 只作 modifier，不是 phase 1 更高优先轴
- `WP14` 只拥有 integration semantics，不拥有 upstream owner state：
  - owns: `integration_state`, `cross_axis_priority_state`, `proposal_conflict_state`, `stabilize_explore_balance`, `repair_progress_balance`, `social_boundary_balance`, `integrated_tendency_proposal`, `axis_arbitration_hints`, `integration_ledger`
  - does not own: `reflective_self/*`, `developmental_self/*`, `social_self/*`, `embodied_self/*`, `self_model/*`, `endogenous_drives/*`
- keep EgoCore authority unchanged：
  - runtime / session / task / tool / transport
  - outward response contract
  - ask / wait / block / escalate
  - trace / replay / gate / audit / maintenance ledger
  - real-world execution / risk adjudication
- `WP8~WP13` 全部继续是 maintenance / frozen upstreams；`WP14` 不得 reopen 它们
- `WP14` 不意味着 live autonomy、OpenEmotion direct reply authority 或 broader transport claims

## Capability Ownership
- OpenEmotion owns:
  - integration semantics
  - cross-axis priority state
  - proposal conflict state
  - bounded integrated tendency proposal
  - advisory axis arbitration hints
  - selfhood integration audit / ledger
  - formal owner target: `OpenEmotion/openemotion/selfhood_integration/*`
- Upstream OpenEmotion owners remain authoritative and read-only to `WP14`:
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/openemotion/endogenous_drives/*`
  - `OpenEmotion/openemotion/reflective_self/*`
  - `OpenEmotion/openemotion/developmental_self/*`
  - `OpenEmotion/openemotion/social_self/*`
  - `OpenEmotion/openemotion/embodied_self/*`
- EgoCore owns:
  - runtime scheduling
  - session / task / tool / transport authority
  - outward response contract
  - ask / wait / block / escalate
  - final reply authority
  - real-world execution and risk adjudication
  - trace / replay / gate / audit / maintenance ledger
- `proto_self_v2` owns:
  - bounded consumption of upstream frozen read surfaces
  - bounded emission of integrated proposals, priority snapshots, and writeback candidates
  - it does not own upstream axis state or selfhood integration owner state itself

## IO Contract Freeze
- Allowed inputs:
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
- Allowed outputs:
  - `self_integration_delta`
  - `cross_axis_priority_snapshot`
  - `proposal_conflict_snapshot`
  - `integrated_policy_hints`
  - `integrated_tendency_proposal`
  - `axis_arbitration_hints`
  - `integration_audit_entries`
  - `self_integration_writeback_candidate`
  - `trace_payload.selfhood_integration_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - transport directive
  - direct Governor bypass
  - direct authority escalation
  - direct mutation of `WP8~WP13` owner state
  - direct reply authority claim
  - live autonomy claim

## WP8~WP13 Boundary Freeze
- `WP8~WP13` stay maintenance / frozen upstreams
- new samples for `WP8~WP13` go only to their maintenance ledgers
- provider `429/401` remains an external budget risk unless it causes formal owner writeback regression in the relevant upstream phase
- `WP14` may consume `WP8~WP13` outputs only through frozen read surfaces
- `WP14` may not reinterpret `WP8~WP13` maintenance or controlled evidence as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`controlled_observation_batch`
- 当前状态：`observation_passed`
- 当前 blocker：`none on the T70 controlled batch axis`
- 当前最小闭环动作：`T80_CLOSEOUT_AND_QA_BASELINE`
- 当前 claim ceiling：`T70 only / controlled-axis V5-E5 observation_passed`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP14: Cross-Axis Self-Integration / Self-Maintenance Arbitration`
- `Tasks/active/mvp19_cross_axis_self_integration/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP8~WP13` boundary freeze
  - locked non-releases
  - subagent assignment
  - task-card write scopes
- 文档没有把 cross-axis integration / arbitration 误写成当前 implementation、mainline wiring、`E4/E5`、observation、或 maintenance mode

## Completion Rules
- 本文件完成只证明 `WP14/MVP19` authority 已冻结并具备 task-package readiness
- 本文件完成不等于 `MVP19` 已实现
- 本文件完成不等于 `MVP19` 已接当前 runtime 主链
- 本文件完成不等于 `MVP19` 已拿到 `E4/E5`
- 本文件完成不等于 `MVP19` 已开始 observation
- 本文件完成不等于 `MVP19` 已进入 maintenance mode
- `T10` 完成只证明 formal owner package 在 OpenEmotion owner 层落地，且 owner-level store / governance / replay / bounded projection 已通过；不证明 runtime mainline 或 observation
- `T20` 完成只证明 `selfhood_integration` 已接入 `proto_self_v2` bounded contract，不证明 EgoCore runtime mainline 已消费
- `T30` 完成只证明当前 EgoCore runtime thin bridge 已接入正式主链，并把 gated `selfhood_integration_writeback` 挂回 formal owner；不证明 `E4/E5` controlled observation
- `T40` 完成只证明 upstream read-only / demotion / compat map 已冻结并通过 no-second-truth verifier；不证明 causal influence 或 controlled observation
- `T50` 完成只证明 stability-first cross-axis arbitration 会改变 bounded downstream weighting，并留下 `V3/E3` causal proof；不证明 controlled observation
- `T60` 完成只证明当前 formal owner + current runtime mainline 已拿到首个 controlled `V4/E4` single observation；不证明 repeated stability、`E5`、或 maintenance mode
- `T70` 完成只证明当前 formal owner + current runtime mainline 已通过 repeated controlled observation aggregate 拿到 `V5/E5`；不证明 closeout、maintenance mode、或 authority 放开
- `T80` 完成才证明当前 `WP14` closeout docs、completion artifact 与 QA baseline 已冻结，可以按 maintenance 口径维护；仍不证明 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
- 未拿到当前 formal owner + current mainline `E4` 之前，不得宣称 `WP14` 生效
- 未拿到重复样本 `E5` 之前，不得宣称 `WP14` 稳定解决或可收口
- 即使未来达到 controlled `E5`，也不得把 `WP14` 解释为 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
