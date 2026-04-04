# MVP19 Cross-Axis Self-Integration / Self-Maintenance Arbitration 执行包

```yaml
task_id: L3-20260404-MVP19-CSISA
created_at: "2026-04-04T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: legacy_demotion_complete
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP19_task_plan.md"
predecessor: "WP13/MVP18"
same_subject_line: true
not_parallel_track: true
scope: "WP14 / MVP19 Cross-Axis Self-Integration / Self-Maintenance Arbitration"
claim_ceiling: "T40 only / legacy_demotion_complete"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP14/MVP19` 的 formal owner target 冻结到 `OpenEmotion/openemotion/selfhood_integration/*`，并把 `WP8~WP13` 的 frozen read surfaces、phase 1 `stability-first` arbitration policy、proposal-only outputs 与 upstream boundary freeze 全部收成可执行 authority package。

## 当前正式 owner target

- `OpenEmotion/openemotion/selfhood_integration/*`

## 当前正式主链 target

`frozen upstream read surfaces -> selfhood integration owner / bounded integration proposals -> proto_self_runtime / proto_self_adapter / proto_self_v2 -> governed downstream weighting and self_integration_writeback_candidate path`

## 当前锁定口径

- `MVP19` 是 `WP14`，接在 `WP13/MVP18` 后，不是新的主体线
- phase 1 只冻结 cross-axis integration semantics、formal intake/output 与 `stability-first` 仲裁策略
- `EgoCore` 继续保留 runtime / session / task / tool / transport、outward response contract、ask / wait / block / escalate、trace / replay / gate / audit / maintenance ledger、real-world execution / risk adjudication 的最终权威
- `WP8~WP13` 都保持 maintenance / frozen upstreams；`WP14` 只能读取冻结 surfaces，不能重写 upstream owner state
- `WP14` 当前不放开 live autonomy、OpenEmotion direct reply authority、broader transport claims、或任何 direct reply / tool / transport / authority escalation

## 当前范围

- authority / contract freeze
- formal selfhood integration owner package target
- bounded proto-self selfhood integration contract target
- EgoCore runtime selfhood integration bridge target
- `WP8~WP13` upstream boundary freeze
- legacy / compat / upstream read-only register
- subagent-ready task decomposition

## 当前状态

- 执行包状态：`runtime_bridge_completed`
- authority freeze：`completed`
- `T00_AUTHORITY_FREEZE`：`completed`
- `T10` formal owner：`completed`
- `T20` proto_self_v2 contract：`completed`
- `T30` EgoCore runtime bridge：`completed`
- `T40` legacy demotion / compat map：`completed`
- `T50` causal validation：`pending`
- `T60` single controlled observation：`pending`
- `T70` batch controlled observation / aggregate：`pending`
- `T80` closeout / QA baseline：`pending`
- `T90` subagent assignment sync：`completed`
- 主链接线：`current_runtime_selfhood_consumer_present_legacy_reference_only`
- 启用状态：`owner_infra_plus_proto_self_contract_plus_runtime_bridge`
- 当前 blocker：`none on the T40 legacy demotion axis`
- 当前最小动作：`T50_CAUSAL_VALIDATION`

## 当前已证实内容

- `Tasks/MVP19_task_plan.md` 已冻结 `WP14` 的 formal owner、authority source、IO contract、`WP8~WP13` boundary freeze 与 locked non-releases
- `contracts/SELFHOOD_INTEGRATION_CAPABILITY_OWNERSHIP.md` 已锁定 `WP14` 只拥有 cross-axis integration semantics，不拥有 upstream axis owner state
- `contracts/SELFHOOD_INTEGRATION_IO_CONTRACT.md` 已锁定：
  - formal intake 只来自 `WP8~WP13` 的 frozen read surfaces
  - phase 1 arbitration policy 是 `stability-first`
  - outputs 只允许 proposal-only / advisory / gated writeback candidates
- `SUBAGENT_ASSIGNMENT.md` 与 `cards/T00..T90` 已把初始 worker mapping、write scope 与后续实现顺序收成可执行 package

## T10 已证实内容

- `OpenEmotion/openemotion/selfhood_integration/*` 已成为 phase 1 的唯一 formal owner 落点
- owner state 已覆盖 `integration_state / cross_axis_priority_state / proposal_conflict_state / stabilize_explore_balance / repair_progress_balance / social_boundary_balance / integrated_tendency_proposal / axis_arbitration_hints / integration_ledger`
- owner store、revision log、replay、proposal-only governance 与 bounded runtime projection 已由 `OpenEmotion/tests/mvp19/test_selfhood_integration_owner_infra.py` 定向证明
- `axis_arbitration_hints` 当前仍保持 advisory-only，`integrated_tendency_proposal` 仍保持 `proposal_only + behavioral_authority = none + required_gate = self_integration_writeback_gate`
- `WP8~WP13` upstream owner surfaces 仍只作为 frozen read surfaces / read-only authority，不构成 `WP14` fallback owner 或 direct mutation authority

## T20 已证实内容

- `OpenEmotion/openemotion/proto_self_v2/selfhood_integration_context.py` 已作为 bounded reader/deriver 接入 `proto_self_v2`
- `proto_self_v2` 当前可基于 `WP8~WP13` frozen surfaces 与 bounded `selfhood_integration_context` projection 生成：
  - `self_integration_delta`
  - `cross_axis_priority_snapshot`
  - `proposal_conflict_snapshot`
  - `integrated_policy_hints`
  - `integrated_tendency_proposal`
  - `axis_arbitration_hints`
  - `integration_audit_entries`
  - `self_integration_writeback_candidate`
  - `trace_payload.selfhood_integration_context`
- 所有 `WP14` outputs 仍保持 `proposal_only + behavioral_authority = none + required_gate = self_integration_writeback_gate`
- `OpenEmotion/tests/mvp19/test_selfhood_integration_proto_self_integration.py` 已定向证明 stability-first bounded arbitration、repair/growth priority selection、proposal-only discipline、legacy-not-promoted 与 developmental tick 下的相邻 contract safety

## T30 已证实内容

- `EgoCore/app/runtime_v2/proto_self_runtime.py` 现在会把 `runtime_summary.selfhood_integration_context` 注入当前 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 正式主链
- 当前 runtime thin bridge 会把 `self_integration_delta / cross_axis_priority_snapshot / proposal_conflict_snapshot / integrated_policy_hints / integrated_tendency_proposal / axis_arbitration_hints / integration_audit_entries / self_integration_writeback_candidate / selfhood_integration_context` 记录进 `state.proto_self_context`
- `selfhood_integration_writeback` 当前已通过宿主侧 gate 接回 `OpenEmotion/openemotion/selfhood_integration/*` formal owner，且仍保持 `proposal_only + behavioral_authority = none + required_gate = self_integration_writeback_gate`
- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py` 已定向证明 current runtime bridge 成立，且不会把 `WP14` proposal-only 输出抬高成 direct reply / tool / transport authority

## T40 已证实内容

- `WP8~WP13` upstream owner surfaces 现在已在 `LEGACY_REFERENCE_REGISTER.md` 中明确登记为 `upstream_authority_read_only`
- historical self-aware step files 与 roadmap materials 现在已明确登记为 technical reference / reference-only，不得充当 `WP14` fallback owner 或 current-mainline proof
- `OpenEmotion/tools/verify_mvp19_mainline_wiring.py` 已静态证明：
  - `OpenEmotion/openemotion/selfhood_integration/*` 是 formal owner path
  - `proto_self_v2` 与 `runtime_v2` 的 current runtime selfhood consumer 仍在 formal owner 路径上
  - upstream read-only map 与 legacy reference-only demotion 同时成立
- `OpenEmotion/tests/mvp19/test_mvp19_mainline_reference_demotion.py` 已定向锁定 no-second-truth demotion contract

## 当前不做

- 不宣称 owner/runtime 已实现
- 不宣称 `E4/E5`
- 不宣称 observation started
- 不宣称 maintenance mode
- 不 reopen `WP8~WP13`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims

## 执行入口

- authority：`Tasks/MVP19_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- task cards：`cards/`
- subagent assignment：`SUBAGENT_ASSIGNMENT.md`
