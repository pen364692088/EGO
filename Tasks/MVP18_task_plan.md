# MVP18 / WP13 Embodied Loop / Environment Coupling

> 状态：WP13 proto-self contract complete + T10 completed + T20 completed + T30 pending
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP13`
> predecessor: `WP12/MVP17`
> same_subject_line: `true`
> not_parallel_track: `true`
> legacy_mvp18_material_is_reference_only: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 host-governed、proposal-only 的 embodied loop / environment coupling；第一刀只冻结 `resource/slack pressure`、`action -> consequence` bounded writeback 与 `self/world boundary pressure`，不放开外发、transport 或 environment action authority。

## Real Goal
- 把 `WP13/MVP18` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP13/MVP18` 的 authority source 冻结到当前正式主线
- 把 `WP13/MVP18` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP12` 向 `WP13` 的边界，不让 `WP13` 反向改写 `WP7~WP12`
- 明确当前仍然不放开的 embodied / environment 能力，防止“`WP12 pass` => embodied authority 扩张”的错误升级

## Non-Goals
- 不把新能力塞回 `WP12`
- 不把 historical consequence / intervention materials 直接升格为 formal owner
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims
- 不做 embodied takeover
- 不做持续主动外发
- 不做 autonomous tool expansion
- 不把 bounded action-consequence 写成当前 readiness 或全局成熟

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP13` phase-detail authority：
  - `Tasks/MVP18_task_plan.md`
- technical reference：
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- 说明：
  - 当前没有 repo-tracked `OpenEmotion/roadmap/versions/MVP18.spec.yaml`
  - 若后续新增 `MVP18` version spec，它在 authority 显式更新前只能作为 technical reference

## Locked Decisions
- `WP13/MVP18` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/embodied_self/*`
- migration/reference surfaces 固定为：
  - `OpenEmotion/emotiond/consequence.py`
  - `OpenEmotion/emotiond/science/interventions.py`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP13` embodied outputs 只能进入 governed diagnosis / proposal / bounded downstream weighting path，不能直接控制 final reply / tool execution / transport
- `WP13` 只能读取：
  - `WP8` self-model projection
  - `WP9` endogenous drive projection
  - `WP10` reflective projection
  - `WP11` developmental projection
  - `WP12` social projection
- `WP13` 不得改写 `WP8~WP12` 的 formal owner contract
- phase 1 scope 固定为：
  - `resource/slack pressure`
  - `action -> consequence` bounded writeback
  - `self/world boundary pressure` 结构化 proposal
- proposal discipline 固定为：
  - `proposal_only`
  - `behavioral_authority = none`
  - `required_gate = embodied_writeback_gate`
  - `promotion_level ∈ {shadow_only, review_only, controlled_axis}`

## Capability Ownership
- OpenEmotion owns:
  - embodied state
  - environment coupling state
  - resource pressure state
  - boundary pressure state
  - action consequence memory
  - self-world boundary semantics
  - embodied policy hints
  - repair-or-stabilize proposal candidates
  - formal owner package: `OpenEmotion/openemotion/embodied_self/*`
- EgoCore owns:
  - runtime scheduling
  - Governor / approval / delivery / transport
  - final reply authority
  - tool execution authority
  - external channel claims
  - real environment interface and risk adjudication
- `proto_self_v2` owns:
  - bounded consumption of embodied and environment context
  - bounded emission of downstream consequence/resource/boundary weighting and writeback candidates
  - it does not own embodied state itself

## IO Contract Freeze
- Allowed inputs:
  - `runtime_summary.embodied_self_context`
  - `runtime_summary.environment_context`
  - `runtime_summary.self_model_context`
  - `runtime_summary.endogenous_drive_context`
  - `runtime_summary.reflective_self_context`
  - `runtime_summary.developmental_self_context`
  - `runtime_summary.social_self_context`
  - action outcome markers
  - resource / slack markers
  - self-world boundary markers
  - `runtime_summary.idle_window`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.maintenance_context`
- Allowed outputs:
  - `embodied_self_delta`
  - `consequence_update_candidates`
  - `resource_boundary_snapshot`
  - `embodied_policy_hints`
  - `repair_or_stabilize_proposal_candidates`
  - `embodied_writeback_candidate`
  - `trace_payload.environment_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - direct transport instruction
  - authority escalation
  - embodied takeover
  - ungoverned environment action
  - direct self-model rewrite
  - direct drive-state rewrite

## WP12 Boundary Freeze
- `WP7~WP12` stay `maintenance_mode`
- new samples for `WP7~WP12` go only to their maintenance ledgers
- provider `429/401` remains an external budget risk unless it causes formal owner writeback regression
- `WP13` may consume `WP7~WP12` outputs only through frozen read surfaces
- `WP13` may not reinterpret `WP12` controlled `E5` or institutionalized maintenance as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`implementation`
- 当前状态：`owner_layer_complete`
- 当前 blocker：`T30 EgoCore runtime bridge not started`
- 当前最小闭环动作：只开 `T30_EGOCORE_RUNTIME_BRIDGE`，不提前进入 observation

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP13: Embodied Loop / Environment Coupling`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP12` boundary freeze
  - locked non-releases
- 文档没有把 host-governed embodied loop 误写成当前 readiness 或全局成熟

## Completion Rules
- 本文件完成不等于 `MVP18` 已实现
- 本文件完成不等于 `MVP18` 已接当前 runtime 主链
- `T10` 完成只证明 formal owner package 在 OpenEmotion owner 层落地，且 owner-level store / governance / replay / bounded projection 已通过；不证明 embodied behavior 已生效
- `T20` 完成只证明 `embodied_self` 已接入 `proto_self_v2` bounded contract，不证明 EgoCore runtime mainline 已消费
- `T30` 完成只证明当前 EgoCore runtime thin bridge 已接入正式主链，不证明 `E4/E5` controlled observation
- `T40` 完成只证明 historical consequence / intervention surfaces 已 reference-only / input-only 化，并通过 no-second-truth verifier；不证明 causal influence 或 controlled observation
- `T50` 完成只证明 embodied proposals 会改变 bounded downstream weighting，并留下 `V3/E3` causal proof；不证明 controlled observation
- `T60` 完成只证明当前 formal owner + current runtime mainline 已拿到首个 controlled `V4/E4` single observation；不证明重复样本稳定性、`E5`、或维护态
- `T70` 完成只证明当前 formal owner + current runtime mainline 已通过 repeated controlled observation aggregate 拿到 `V5/E5`；不证明 closeout、`maintenance_mode`、或 authority 放开
- `T80` 完成才证明当前 `WP13` closeout docs、completion artifact 与 QA baseline 已冻结，可以按 maintenance-mode 口径维护；仍不证明 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
- 未拿到当前 formal owner + current mainline `E4` 之前，不得宣称 `WP13` 生效
- 未拿到重复样本 `E5` 之前，不得宣称 `WP13` 稳定解决或可收口
- 即使未来达到 controlled `E5`，也不得把 `WP13` 解释为 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
