# MVP15 / WP10 Reflective Self / Counterfactual Self

> 状态：WP10 maintenance_mode
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP10`
> predecessor: `WP9/MVP14`
> same_subject_line: `true`
> not_parallel_track: `true`
> wp9_boundary_frozen: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 reflective self 与 counterfactual self-evaluation；它们只作为受治理的 diagnosis / proposal / counterfactual analysis 来源，不获得 final reply、tool execution 或 transport authority。

## Real Goal
- 把 `WP10/MVP15` 的 capability ownership 冻结到唯一 formal owner
- 把 `WP10/MVP15` 的 authority source 冻结到当前主线
- 把 `WP10/MVP15` 的 input / output contract 冻结成 proposal-disciplined bounded surfaces
- 冻结 `WP9` 向 `WP10` 的边界，不让 `WP10` 反向改写 `WP9`
- 明确当前仍然不放开的能力，防止“`WP9 pass` => reflection authority 扩张”的错误升级

## Non-Goals
- 不把新能力塞回 `WP9`
- 不把旧 `emotiond/reflection_engine / reflection_adapter / reflection_shadow / self_counterfactual` 直接升格为 formal owner
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims
- 不把 counterfactual 或 reflection proposal 直接升格为 action authority

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP10` phase-detail authority：
  - `Tasks/MVP15_task_plan.md`
- version spec：
  - `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- technical reference：
  - `OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
  - `OpenEmotion/docs/mvp15/MVP15_EXIT_CRITERIA.md`
  - `OpenEmotion/docs/mvp15/REFLECTIVE_SELF_ARCHITECTURE.md`
  - `OpenEmotion/docs/mvp15/REFLECTION_STATE_SCHEMA.md`
  - `OpenEmotion/docs/mvp15/COUNTERFACTUAL_SELF_EVALUATION.md`
  - `OpenEmotion/docs/mvp15/REFLECTIVE_GOVERNANCE_POLICY.md`

## Locked Decisions
- `WP10/MVP15` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/reflective_self/*`
- `OpenEmotion/emotiond/reflection_engine/*`、`reflection_adapter.py`、`reflection_shadow.py`、`self_counterfactual.py`、`core.py`、`api.py`、`workspace.py` 只作为 bounded compatibility / migration / replay-friendly reference surfaces
- 当前正式主链接线目标固定为：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP10` 的 reflection / counterfactual 输出只能进入 governed diagnosis / proposal / bounded downstream weighting path，不能直接控制 final reply / tool execution / transport
- `WP10` 只能读取 `WP8` self-model projection 与 `WP9` drive projection；不得改写它们的 formal owner contract
- proposal discipline 固定为：
  - `proposal_only`
  - `behavioral_authority = none`
  - counterfactual uncertainty must remain explicit

## Capability Ownership
- OpenEmotion owns:
  - reflection queue / reflection targets
  - diagnosis records
  - counterfactual records
  - revision proposal candidates
  - unresolved reflection items
  - reflection history / audit / replayable transitions
  - formal owner package: `OpenEmotion/openemotion/reflective_self/*`
- EgoCore owns:
  - runtime scheduling
  - Governor / approval / delivery / transport
  - final reply authority
  - tool execution authority
  - external channel claims
- `proto_self_v2` owns:
  - bounded consumption of reflection context
  - bounded emission of downstream weighting / maintenance / revision proposal hooks
  - it does not own reflective state itself

## IO Contract Freeze
- Allowed inputs:
  - `WP8` self-model projection
  - `WP9` drive state / priority / maintenance candidate projection
  - developmental tensions / unresolved contradictions
  - continuity break signals
  - replay inconsistency / replay debt / audit traces
  - maintenance outcomes and revision history
  - decision history / response-plan evidence
  - `runtime_summary.idle_window`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.maintenance_context`
- Allowed outputs:
  - `reflective_self_delta`
  - `diagnosis_records`
  - `counterfactual_records`
  - `revision_proposal_candidates`
  - `confidence_adjustment_hints`
  - `maintenance_priority_hints`
  - `trace_payload.reflection_context`
  - `reflection_writeback_candidate`
- Forbidden outputs:
  - final reply text
  - tool command
  - direct transport instruction
  - authority escalation
  - direct self-model rewrite
  - direct drive-state rewrite
  - ungoverned policy mutation

## WP9 Boundary Freeze
- `WP9` stays `maintenance_mode`
- new `WP9` samples go only to `Tasks/active/mvp14_endogenous_drives_self_maintenance/MAINTENANCE_LEDGER.md`
- provider `429/401` remains an external budget risk unless it causes formal owner writeback regression
- `WP10` may consume `WP9` outputs only through frozen read surfaces
- `WP10` may not reinterpret `WP9 controlled E5` as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`closure`
- 当前状态：`maintenance_mode`
- 当前 blocker：controlled observation 范围内无主 blocker；provider `429/401` 仍仅记为外部预算层风险
- 当前最小闭环动作：维持 `WP10` maintenance ledger intake，不扩 authority 边界，并在进入下一阶段前先定义新的 authority package

## Current Proven State
- `MVP15` spec / docs / tests / legacy implementation 已存在
- legacy bounded consumer 已在旧 `emotiond` `/plan` 与 `/decision/target` surface 上出现过 `reflection_guidance`
- legacy paired behavioral relevance proof 已存在，但只属于 reference-only 旧线，不自动构成当前 `runtime_v2` 主链 formal proof
- 当前 `openemotion/reflective_self/*` formal owner package 已落地
- 当前 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 已消费 bounded reflective context 并记录 governed reflective writeback
- 当前 `OpenEmotion/artifacts/mvp15/mvp15_causal_validation_current.md` 为 `pass`，`pair_count = 3`、`passed_count = 3`
- 当前 `OpenEmotion/artifacts/mvp15/mvp15_controlled_observation_current.md` 为 `pass`，`verification_level = V4`、`evidence_level = E4`、`gate_verdict = allow_writeback`、`replay_valid = true`
- 当前 `OpenEmotion/artifacts/mvp15/mvp15_controlled_observation_batch_current.md` 为 `pass`，`verification_level = V5`、`evidence_level = E5`、`report_count = 3`、`accepted_count = 3`、`proposal_discipline_consistent_count = 3`、`behavioral_authority_none_count = 3`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP10: Reflective Self / Counterfactual Self`
- `Tasks/active/mvp15_reflective_self_counterfactual/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input / output contract
  - `WP9` boundary freeze
  - locked non-releases
- 文档没有把旧 `MVP15` bounded / shadow 线误写成当前 `WP10` readiness 或全局成熟

## Completion Rules
- 本文件完成不等于 `MVP15` 已实现
- 本文件完成不等于 `MVP15` 已接当前 runtime 主链
- 未拿到当前 formal owner + current mainline `E4` 之前，不得宣称 `WP10` 生效
- 未拿到重复样本 `E5` 之前，不得宣称 `WP10` 稳定解决或可收口
- 即使未来达到 controlled `E5`，也不得把 `WP10` 解释为 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
