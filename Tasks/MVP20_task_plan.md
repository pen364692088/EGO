# MVP20 / WP15 Host-Governed Self-Directed Initiative / Commitment Continuity

> 状态：maintenance_mode on the controlled axis
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP15`
> predecessor: `WP14/MVP19`
> same_subject_line: `true`
> not_parallel_track: `true`
> docs_only_authority_package: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 host-governed、proposal-only 的 self-directed initiative / commitment continuity；第一刀只冻结 formal owner、initiative intake / output contract、`WP7` proactive substrate 边界与 `WP8~WP14` upstream freeze，不放开任何行为权、外发权或 transport claim。

## Real Goal
- 把 `WP15/MVP20` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP15/MVP20` 的 authority source 冻结到当前正式主线
- 把 `WP15/MVP20` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP7` host proactive chain 与 `WP8~WP14` upstream maintenance 边界，不让 `WP15` 反向改写既有 owner
- 明确当前仍然不放开的 initiative / proactive 权限，防止“已有 selfhood integration => 已有 live initiative authority”的错误升级

## Non-Goals
- 不宣称 owner/runtime 已实现
- 不宣称已接当前 runtime 主链
- 不宣称 `E4/E5`
- 不宣称 observation started
- 不 reopen `WP7~WP14`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 tool execution authority
- 不放开 broader transport claims
- 不改 host proactive enable policy
- 不允许 direct response-plan injection

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP15` phase-detail authority：
  - `Tasks/MVP20_task_plan.md`
- technical reference：
  - `Tasks/MVP12_task_plan.md`
  - `Tasks/MVP13_task_plan.md`
  - `Tasks/MVP14_task_plan.md`
  - `Tasks/MVP15_task_plan.md`
  - `Tasks/MVP16_task_plan.md`
  - `Tasks/MVP17_task_plan.md`
  - `Tasks/MVP18_task_plan.md`
  - `Tasks/MVP19_task_plan.md`
  - `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- 说明：
  - 当前没有 repo-tracked `OpenEmotion/roadmap/versions/MVP20.spec.yaml`
  - 若后续新增 `MVP20` version spec，它在 authority 显式更新前只能作为 technical reference

## Locked Decisions
- `WP15/MVP20` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/initiative_self/*`
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP15` 只拥有 initiative semantics，不拥有 host proactive execution substrate 或 upstream owner state
- `WP7` proactive chain 只保留为 host execution substrate / evidence reference：
  - `initiative_arbiter`
  - `initiative_scheduler`
  - `pending_proactive_followup`
  - `controlled_proactive_delivery_lane`
  - `host_proactive_outbox_lane`
  - `controlled_outbox_drain`
  - `controlled_telegram_transport_bridge`
  - `feature_flagged_host_governed_proactive_telegram_auto_cycle`
  - `host_governed_proactive_telegram_enable_policy`
- phase 1 formal intake 固定为：
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
- phase 1 formal outputs 固定为：
  - `initiative_self_delta`
  - `initiative_proposal_candidates`
  - `commitment_execution_snapshot`
  - `initiative_policy_hints`
  - `host_proactive_candidate`
  - `initiative_audit_entries`
  - `initiative_writeback_candidate`
  - `trace_payload.initiative_context`
- proposal discipline 固定为：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = initiative_writeback_gate`
  - `host_proactive_candidate` 只是 governed candidate，不得直接触发 delivery / transport
- phase 1 scope 固定为：
  - initiative proposal semantics
  - commitment continuity / carryover semantics
  - bounded host-proactive candidate generation under host governance
  - no autonomous outreach
  - no transport enable-policy changes
  - no direct response-plan injection
- `WP7~WP14` 全部继续是 maintenance / frozen upstreams；`WP15` 不得 reopen 它们
- `WP15` 不意味着 live autonomy、OpenEmotion direct reply authority、tool authority 或 broader transport claims

## Capability Ownership
- OpenEmotion owns:
  - initiative state
  - initiative priority state
  - commitment continuity state
  - initiative proposal semantics
  - bounded host-proactive candidate semantics
  - initiative audit / ledger
  - formal owner target: `OpenEmotion/openemotion/initiative_self/*`
- Upstream owners remain authoritative and read-only to `WP15`:
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/openemotion/endogenous_drives/*`
  - `OpenEmotion/openemotion/reflective_self/*`
  - `OpenEmotion/openemotion/developmental_self/*`
  - `OpenEmotion/openemotion/social_self/*`
  - `OpenEmotion/openemotion/embodied_self/*`
  - `OpenEmotion/openemotion/selfhood_integration/*`
- EgoCore owns:
  - runtime scheduling
  - proactive delivery / outbox / transport substrate
  - outward response contract
  - ask / wait / block / escalate
  - final reply authority
  - tool execution authority
  - real-world execution and risk adjudication
  - trace / replay / gate / audit / maintenance ledger
- `proto_self_v2` owns:
  - bounded consumption of initiative context
  - bounded emission of initiative candidates, snapshots, hints, and writeback candidates
  - it does not own initiative owner state itself

## IO Contract Freeze
- Allowed inputs:
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
- Allowed outputs:
  - `initiative_self_delta`
  - `initiative_proposal_candidates`
  - `commitment_execution_snapshot`
  - `initiative_policy_hints`
  - `host_proactive_candidate`
  - `initiative_audit_entries`
  - `initiative_writeback_candidate`
  - `trace_payload.initiative_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - transport directive
  - direct Governor bypass
  - direct authority escalation
  - host proactive send execution
  - transport enable-policy override
  - direct mutation of `WP7~WP14` owner state
  - live autonomy claim

## WP7~WP14 Boundary Freeze
- `WP7` host proactive chain stays host-governed execution substrate only
- `WP8~WP14` stay maintenance / frozen upstreams
- new samples for `WP7~WP14` go only to their maintenance ledgers
- `WP15` may consume `WP8~WP14` outputs only through frozen read surfaces
- `WP15` may not reinterpret `WP7` transport or proactive evidence as initiative semantic ownership
- `WP15` may not reinterpret `WP8~WP14` maintenance institutionalization or controlled evidence as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`maintenance`
- 当前状态：`T80 completed`
- 当前 blocker：`none on the WP15 controlled axis`
- 当前最小闭环动作：`maintenance verification / ledger intake only`
- 当前 claim ceiling：`maintenance_mode on the controlled axis only`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP15: Host-Governed Self-Directed Initiative / Commitment Continuity`
- `Tasks/active/mvp20_host_governed_initiative_continuity/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP7~WP14` boundary freeze
  - locked non-releases
  - subagent assignment
  - task-card write scopes
- 文档没有把 initiative continuity 误写成当前 implementation、mainline wiring、`E4/E5`、observation、或 maintenance mode

## Completion Rules
- 本文件完成只证明 `WP15/MVP20` authority 已冻结并具备 task-package readiness
- 本文件完成不等于 `MVP20` 已实现
- 本文件完成不等于 `MVP20` 已接当前 runtime 主链
- 本文件完成不等于 `MVP20` 已拿到 `E4/E5`
- 本文件完成不等于 `MVP20` 已开始 observation
- 本文件完成不等于 `MVP20` 已进入 maintenance mode
- `T10` 完成只证明 formal owner package 在 OpenEmotion owner 层落地，且 owner-level schema/state/store/governance/replay/projection 已通过定向验证；不证明 runtime mainline 或 observation
- `T20` 完成只证明 `initiative_self` 已接入 `proto_self_v2` bounded contract，且 initiative outputs / trace mirror 已通过定向验证；不证明 EgoCore runtime mainline 已消费
- `T30` 完成只证明当前 EgoCore runtime thin bridge 已接入正式主链，并把 gated initiative writeback 挂回 bounded host context；不证明 `E4/E5` controlled observation
- `T40` 完成只证明 host proactive substrate / legacy demotion / compat map 已冻结并通过 no-second-truth verifier；不证明 causal influence 或 controlled observation
- `T50` 完成只证明 initiative proposals 会改变 bounded downstream weighting，并留下 `V3/E3` causal proof；不证明 controlled observation
- `T60` 完成只证明当前 formal owner + current runtime mainline 已拿到首个 controlled `V4/E4` single observation；不证明 repeated stability、`E5`、或 maintenance mode
- `T70` 完成只证明当前 formal owner + current runtime mainline 已通过 repeated controlled observation aggregate 拿到 `V5/E5`；不证明 closeout、maintenance mode、或 authority 放开
- `T80` 完成才证明当前 `WP15` closeout docs、completion artifact 与 QA baseline 已冻结，可以按 maintenance 口径维护；仍不证明 live autonomy、OpenEmotion direct reply authority、tool authority、或 broader transport maturity
