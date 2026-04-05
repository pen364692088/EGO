# MVP21 / WP16 Host-Governed Initiative Realization / Proactive Delivery Mediation

> 状态：T20 complete / T30 pending
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP16`
> predecessor: `WP15/MVP20`
> same_subject_line: `true`
> not_parallel_track: `true`
> legacy_mvp21_material_is_reference_only: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 host-governed、proposal-only 的 initiative realization / proactive delivery mediation；第一刀只冻结 formal owner、realization intake / output contract、`WP7` proactive runtime substrate 边界与 `WP8~WP15` upstream freeze，不放开任何 execution、delivery、transport 或 authority。

## Real Goal
- 把 `WP16/MVP21` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP16/MVP21` 的 authority source 冻结到当前正式主线
- 把 `WP16/MVP21` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP7` proactive runtime / outbox / transport substrate 与 `WP8~WP15` upstream maintenance 边界，不让 `WP16` 反向改写既有 owner
- 明确当前仍然不放开的 realization / delivery / transport 权限，防止“已有 initiative continuity => 已有主动交付 authority”的错误升级

## Non-Goals
- 不宣称 owner/runtime 已实现
- 不宣称已接当前 runtime 主链
- 不宣称 `E4/E5`
- 不宣称 observation started
- 不宣称 maintenance mode
- 不 reopen `WP7~WP15`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 tool execution authority
- 不放开 broader transport claims
- 不改 host proactive enable policy
- 不允许 direct outbox enqueue
- 不允许 direct transport execution
- 不创建 `WP17` docs

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP16` phase-detail authority：
  - `Tasks/MVP21_task_plan.md`
- technical reference：
  - `Tasks/MVP12_task_plan.md`
  - `Tasks/MVP13_task_plan.md`
  - `Tasks/MVP14_task_plan.md`
  - `Tasks/MVP15_task_plan.md`
  - `Tasks/MVP16_task_plan.md`
  - `Tasks/MVP17_task_plan.md`
  - `Tasks/MVP18_task_plan.md`
  - `Tasks/MVP19_task_plan.md`
  - `Tasks/MVP20_task_plan.md`
  - `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- 说明：
  - 当前没有 repo-tracked `MVP21` version spec
  - 若后续新增 `MVP21` version spec，它在 authority 显式更新前只能作为 technical reference

## Locked Decisions
- `WP16/MVP21` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/initiative_realization/*`
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP16` 只拥有 initiative realization / fulfillment / readiness semantics，不拥有 host proactive execution substrate、outbox/transport substrate 或 upstream owner state
- `WP7` proactive runtime chain 只保留为 host execution substrate / evidence reference：
  - `initiative_arbiter`
  - `proactive_delivery`
  - `proactive_outbox`
  - `proactive_outbox_drain`
  - `telegram_proactive_transport`
  - `host_governed_proactive_telegram_cycle`
- phase 1 formal intake 固定为：
  - `runtime_summary.initiative_self_context`
  - `runtime_summary.initiative_context`
  - `runtime_summary.selfhood_integration_context`
  - `runtime_summary.maintenance_context`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.idle_window`
  - `runtime_summary.host_proactive_context`
- phase 1 formal outputs 固定为：
  - `initiative_realization_delta`
  - `commitment_fulfillment_candidates`
  - `delivery_readiness_snapshot`
  - `host_lane_hints`
  - `controlled_delivery_candidate`
  - `initiative_realization_audit_entries`
  - `initiative_realization_writeback_candidate`
  - `trace_payload.initiative_realization_context`
- proposal discipline 固定为：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = initiative_realization_writeback_gate`
  - `controlled_delivery_candidate` 与 `host_lane_hints` 只是 governed advisory candidates，不得直接触发 delivery / outbox / transport
- phase 1 scope 固定为：
  - semantic readiness / realization / fulfillment interpretation
  - bounded delivery-readiness proposal semantics
  - host-lane mediation hints under host governance
  - no execution authority release
  - no outbox enqueue authority
  - no transport enable-policy changes
  - no direct response-plan injection
- `WP7~WP15` 全部继续是 maintenance / frozen upstreams；`WP16` 不得 reopen 它们
- `WP16` 不意味着 live autonomy、OpenEmotion direct reply authority、tool authority 或 broader transport claims

## Capability Ownership
- OpenEmotion owns:
  - initiative realization state
  - commitment fulfillment state
  - proactive readiness state
  - realization hold state
  - delivery readiness snapshot semantics
  - host lane hint semantics
  - controlled delivery candidate semantics
  - initiative realization audit / ledger
  - formal owner target: `OpenEmotion/openemotion/initiative_realization/*`
- Upstream owners remain authoritative and read-only to `WP16`:
  - `OpenEmotion/openemotion/initiative_self/*`
  - `OpenEmotion/openemotion/selfhood_integration/*`
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/openemotion/endogenous_drives/*`
  - `OpenEmotion/openemotion/reflective_self/*`
  - `OpenEmotion/openemotion/developmental_self/*`
  - `OpenEmotion/openemotion/social_self/*`
  - `OpenEmotion/openemotion/embodied_self/*`
- EgoCore owns:
  - runtime / scheduler / proactive delivery / outbox / transport substrate
  - outward response contract
  - ask / wait / block / escalate
  - final reply authority
  - tool execution authority
  - real-world execution and risk adjudication
  - trace / replay / gate / audit / maintenance ledger
- `proto_self_v2` owns:
  - bounded consumption of realization context
  - bounded emission of realization candidates, snapshots, hints, and writeback candidates
  - it does not own initiative realization owner state itself

## IO Contract Freeze
- Allowed inputs:
  - `runtime_summary.initiative_self_context`
  - `runtime_summary.initiative_context`
  - `runtime_summary.selfhood_integration_context`
  - `runtime_summary.maintenance_context`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.idle_window`
  - `runtime_summary.host_proactive_context`
- Allowed outputs:
  - `initiative_realization_delta`
  - `commitment_fulfillment_candidates`
  - `delivery_readiness_snapshot`
  - `host_lane_hints`
  - `controlled_delivery_candidate`
  - `initiative_realization_audit_entries`
  - `initiative_realization_writeback_candidate`
  - `trace_payload.initiative_realization_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - transport directive
  - direct Governor bypass
  - direct authority escalation
  - outbox enqueue command
  - transport enable-policy override
  - direct mutation of `WP7~WP15` owner state
  - live autonomy claim

## WP7~WP15 Boundary Freeze
- `WP7` host proactive runtime chain stays host-governed execution substrate only
- `WP8~WP15` stay maintenance / frozen upstreams
- new samples for `WP8~WP15` go only to their maintenance ledgers
- `WP16` may consume `WP8~WP15` outputs only through frozen read surfaces
- `WP16` may not reinterpret `WP7` transport or proactive evidence as realization semantic ownership
- `WP16` may not reinterpret `WP15` maintenance institutionalization or controlled evidence as delivery authority or broader transport maturity

## Current Phase Status
- 当前层级：`proto_self_contract`
- 当前状态：`proto_self_contract_complete`
- 当前 blocker：`none on the WP16 proto-self-contract axis`
- 当前最小闭环动作：`T30_EGOCORE_RUNTIME_BRIDGE`
- 当前 claim ceiling：`T20 complete only`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP16: Host-Governed Initiative Realization / Proactive Delivery Mediation`
- `Tasks/active/mvp21_host_governed_initiative_realization/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP7~WP15` boundary freeze
  - locked non-releases
  - subagent assignment
  - task-card write scopes
- 文档没有把 initiative realization 误写成当前 implementation、mainline wiring、`E4/E5`、observation、或 maintenance mode

## Completion Rules
- 本文件完成只证明 `WP16/MVP21` authority 已冻结并具备 task-package readiness
- 本文件完成不等于 `MVP21` 已实现
- 本文件完成不等于 `MVP21` 已接当前 runtime 主链
- 本文件完成不等于 `MVP21` 已拿到 `E4/E5`
- 本文件完成不等于 `MVP21` 已开始 observation
- 本文件完成不等于 `MVP21` 已进入 maintenance mode
- `T10` 完成只证明 formal owner package 在 OpenEmotion owner 层落地，且 owner-level schema/state/store/governance/replay/projection 已通过定向验证；当前证据等级上限是 `V2/E2`，不证明 proto-self contract、runtime mainline 或 observation
- `T20` 完成只证明 `initiative_realization` 已接入 `proto_self_v2` bounded contract，且 realization outputs / trace mirror 已通过定向验证；不证明 EgoCore runtime mainline 已消费
- `T30` 完成只证明当前 EgoCore runtime thin bridge 已接入正式主链，并把 gated realization writeback 挂回 bounded host context；不证明 `E4/E5` controlled observation
- `T40` 完成只证明 host proactive runtime substrate / legacy demotion / compat map 已冻结并通过 no-second-truth verifier；不证明 causal influence 或 controlled observation
- `T50` 完成只证明 realization proposals 会改变 bounded downstream weighting，并留下 `V3/E3` causal proof；不证明 controlled observation
- `T60` 完成只证明当前 formal owner + current runtime mainline 已拿到首个 controlled `V4/E4` single observation；不证明 repeated stability、`E5`、或 maintenance mode
- `T70` 完成只证明当前 formal owner + current runtime mainline 已通过 repeated controlled observation aggregate 拿到 `V5/E5`；不证明 closeout、maintenance mode、或 authority 放开
- `T80` 完成才证明当前 `WP16` closeout docs、completion artifact 与 QA baseline 已冻结，可以按 maintenance 口径维护；仍不证明 live autonomy、OpenEmotion direct reply authority、tool authority、或 broader transport maturity
