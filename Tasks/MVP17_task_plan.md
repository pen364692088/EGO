# MVP17 / WP12 Social Self / Other-Modeling

> 状态：WP12 authority_frozen + T10 formal owner package completed
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP12`
> predecessor: `WP11/MVP16`
> same_subject_line: `true`
> not_parallel_track: `true`
> legacy_mvp17_material_is_reference_only: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 host-governed、proposal-only 的 social self / other-modeling；第一刀只冻结 `trust / commitment / repair` 这条可验证社会连续性，不放开外发或 transport authority。

## Real Goal
- 把 `WP12/MVP17` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP12/MVP17` 的 authority source 冻结到当前正式主线
- 把 `WP12/MVP17` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP11` 向 `WP12` 的边界，不让 `WP12` 反向改写 `WP7~WP11`
- 明确当前仍然不放开的社会能力，防止“`WP11 pass` => social authority 扩张”的错误升级

## Non-Goals
- 不把新能力塞回 `WP11`
- 不把 historical social / relation materials 直接升格为 formal owner
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims
- 不做 autonomous social outreach
- 不做无约束 other-model mind-reading
- 不把 social proposal 直接升格为 action authority
- 不把 bounded social self 写成“完整社会人格已成立”

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP12` phase-detail authority：
  - `Tasks/MVP17_task_plan.md`
- technical reference：
  - `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
  - `OpenEmotion/docs/archive/mvp9/MVP9_SPEC.md`
- 说明：
  - 当前没有 repo-tracked `OpenEmotion/roadmap/versions/MVP17.spec.yaml`
  - 若后续新增 `MVP17` version spec，它在 authority 显式更新前只能作为 technical reference

## Locked Decisions
- `WP12/MVP17` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/social_self/*`
- migration/reference surfaces 固定为：
  - `EgoCore/app/response/relationship_context.py`
  - `EgoCore/app/handlers/social_chat_handler.py`
  - `EgoCore/app/runtime/repair_context_manager.py`
  - `EgoCore/app/bridges/openemotion_bridge.py`
  - `OpenEmotion/emotiond/db.py`
  - `OpenEmotion/emotiond/state.py`
  - `OpenEmotion/emotiond/api.py`
  - `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
  - `OpenEmotion/docs/archive/mvp9/MVP9_SPEC.md`
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP12` social outputs 只能进入 governed diagnosis / proposal / bounded downstream weighting path，不能直接控制 final reply / tool execution / transport
- `WP12` 只能读取：
  - `WP8` self-model projection
  - `WP9` endogenous drive projection
  - `WP10` reflective projection
  - `WP11` developmental projection
- `WP12` 不得改写 `WP8~WP11` 的 formal owner contract
- phase 1 scope 固定为：
  - `trust`
  - `commitment`
  - `repair`
  - bounded `other-model` / `social role continuity` 仅作为结构化状态，不做泛化心智解读
- proposal discipline 固定为：
  - `proposal_only`
  - `behavioral_authority = none`
  - `required_gate = social_writeback_gate`
  - `promotion_level ∈ {shadow_only, review_only, controlled_axis}`

## Capability Ownership
- OpenEmotion owns:
  - other-model state
  - relation memory
  - trust state
  - commitment state
  - repair state
  - social boundary state
  - relationship update semantics
  - repair proposal candidates
  - formal owner package: `OpenEmotion/openemotion/social_self/*`
- EgoCore owns:
  - runtime scheduling
  - Governor / approval / delivery / transport
  - final reply authority
  - tool execution authority
  - external channel claims
- `proto_self_v2` owns:
  - bounded consumption of social context
  - bounded emission of downstream weighting / trust-commitment / repair hooks
  - it does not own social self state itself

## IO Contract Freeze
- Allowed inputs:
  - `runtime_summary.social_context`
  - `runtime_summary.social_self_context`
  - `runtime_summary.self_model_context`
  - `runtime_summary.endogenous_drive_context`
  - `runtime_summary.reflective_self_context`
  - `runtime_summary.developmental_self_context`
  - relationship continuity markers
  - commitment breach markers
  - repair outcomes / unresolved conflict markers
  - social boundary and trust drift indicators
  - `runtime_summary.idle_window`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.maintenance_context`
- Allowed outputs:
  - `social_self_delta`
  - `relation_update_candidates`
  - `trust_commitment_snapshot`
  - `social_policy_hints`
  - `repair_proposal_candidates`
  - `social_writeback_candidate`
  - `trace_payload.social_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - direct transport instruction
  - authority escalation
  - autonomous outreach
  - direct self-model rewrite
  - direct drive-state rewrite
  - ungoverned relation mutation

## WP11 Boundary Freeze
- `WP7~WP11` stay `maintenance_mode`
- new samples for `WP7~WP11` go only to their maintenance ledgers
- provider `429/401` remains an external budget risk unless it causes formal owner writeback regression
- `WP12` may consume `WP7~WP11` outputs only through frozen read surfaces
- `WP12` may not reinterpret `WP11 controlled E5` as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`implementation`
- 当前状态：`authority_frozen + owner_package_in_place`
- 当前 blocker：`runtime intake and proto_self social contract are not connected yet`
- 当前最小闭环动作：只做 `T20_PROTO_SELF_CONTRACT_INTEGRATION`，不 reopen `WP11`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP12: Social Self / Other-Modeling`
- `Tasks/active/mvp17_social_self_other_modeling/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP11` boundary freeze
  - locked non-releases
- 文档没有把 bounded social self 误写成当前 readiness 或全局成熟

## Completion Rules
- 本文件完成不等于 `MVP17` 已实现
- 本文件完成不等于 `MVP17` 已接当前 runtime 主链
- `T10` 完成只证明 formal owner package 在 OpenEmotion owner 层落地，不证明 social behavior 已生效
- 未拿到当前 formal owner + current mainline `E4` 之前，不得宣称 `WP12` 生效
- 未拿到重复样本 `E5` 之前，不得宣称 `WP12` 稳定解决或可收口
- 即使未来达到 controlled `E5`，也不得把 `WP12` 解释为 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
