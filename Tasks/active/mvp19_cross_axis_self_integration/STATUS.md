# MVP19 Cross-Axis Self-Integration / Self-Maintenance Arbitration 状态台账

```yaml
phase: WP14
status: legacy_demotion_complete
current_layer: legacy_demotion
main_chain_status: current_runtime_selfhood_consumer_present_legacy_reference_only
enabled_status: owner_infra_plus_proto_self_contract_plus_runtime_bridge
trigger_evidence:
  - WP13/MVP18 is the predecessor and remains the last completed maintenance upstream
  - WP14 authority package now exists under Tasks/*
  - formal owner target is frozen to OpenEmotion/openemotion/selfhood_integration/*
  - current formal runtime mainline target remains runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2
  - formal intake is frozen to runtime_summary self_model, endogenous_drive, reflective_self, developmental_self, social_self, embodied_self, maintenance, resource_budget_hint, recent_delivery_outcome, and idle_window surfaces
  - phase 1 arbitration inputs are frozen to WP8/WP9/WP10/WP11/WP12/WP13 bounded proposal and priority surfaces only
  - phase 1 outputs are frozen to self_integration_delta, cross_axis_priority_snapshot, proposal_conflict_snapshot, integrated_policy_hints, integrated_tendency_proposal, axis_arbitration_hints, integration_audit_entries, self_integration_writeback_candidate, and trace_payload.selfhood_integration_context
  - output discipline is frozen to proposal_only true, behavioral_authority none, and required_gate self_integration_writeback_gate
  - stability-first priority policy is frozen with stabilize/conserve/guard/review ahead of repair, growth, and reflective modifier logic
  - WP14 owns only integration semantics and may not mutate WP8~WP13 owner state
  - EgoCore authority remains unchanged for runtime, session, task, tool, transport, outward response, ask/wait/block/escalate, trace/replay/gate/audit/maintenance ledger, and real-world execution/risk adjudication
  - selfhood_integration formal owner package now exists under OpenEmotion/openemotion/selfhood_integration/*
  - owner state covers integration_state, cross_axis_priority_state, proposal_conflict_state, stabilize_explore_balance, repair_progress_balance, social_boundary_balance, integrated_tendency_proposal, axis_arbitration_hints, and integration_ledger
  - owner store, replay, proposal-only governance, and bounded runtime projection tests passed in OpenEmotion/tests/mvp19/test_selfhood_integration_owner_infra.py
  - proto_self_v2 now reads WP8~WP13 frozen surfaces into a bounded selfhood_integration contract module under OpenEmotion/openemotion/proto_self_v2/selfhood_integration_context.py
  - KernelOutputV2 and trace payload now expose self_integration_delta, cross_axis_priority_snapshot, proposal_conflict_snapshot, integrated_policy_hints, integrated_tendency_proposal, axis_arbitration_hints, integration_audit_entries, self_integration_writeback_candidate, and trace_payload.selfhood_integration_context
  - proposal discipline remains proposal_only true, behavioral_authority none, required_gate self_integration_writeback_gate, and no upstream owner mutation path
  - scoped contract tests passed in OpenEmotion/tests/mvp19/test_selfhood_integration_proto_self_integration.py
  - EgoCore runtime_v2 now injects runtime_summary.selfhood_integration_context from the formal owner projection into the current mainline
  - current runtime mainline now records self_integration_delta, cross_axis_priority_snapshot, proposal_conflict_snapshot, integrated_policy_hints, integrated_tendency_proposal, axis_arbitration_hints, integration_audit_entries, self_integration_writeback_candidate, selfhood_integration_context, and selfhood_integration_writeback in state.proto_self_context
  - selfhood integration writeback remains gated to self_integration_writeback_gate with proposal_only discipline and behavioral_authority none
  - scoped EgoCore runtime bridge tests passed in EgoCore/tests/test_runtime_v2_proto_self_runtime.py
  - WP8~WP13 upstream owner surfaces are now explicitly registered as read-only to WP14 in LEGACY_REFERENCE_REGISTER.md
  - archived self-aware step files and roadmap materials are now explicitly classified as technical reference / reference-only and may not become WP14 fallback authority
  - OpenEmotion/tools/verify_mvp19_mainline_wiring.py now proves current runtime selfhood consumer presence plus no-second-truth legacy demotion
  - OpenEmotion/tests/mvp19/test_mvp19_mainline_reference_demotion.py now proves upstream read-only registration and legacy reference-only demotion
verification_level: V3
evidence_level: E3
current_blocker: "none on the T40 legacy demotion axis"
next_minimal_closure_action: "start T50_CAUSAL_VALIDATION without upgrading the claim ceiling beyond T40"
```

## 当前口径

- 可宣称完成：`WP14/MVP19` 的 authority 仍保持冻结，且 `T10_FORMAL_OWNER_PACKAGE`、`T20_PROTO_SELF_CONTRACT_INTEGRATION`、`T30_EGOCORE_RUNTIME_BRIDGE` 与 `T40_LEGACY_DEMOTION_AND_COMPAT_MAP` 已完成
- 条件性完成：当前只覆盖 authority + owner infra + `proto_self_v2` bounded contract + EgoCore runtime thin bridge + no-second-truth legacy demotion 这一条轴，不覆盖 causal proof、controlled observation、或 closeout
- 不可宣称完成：`MVP19` 已拿到 `E4/E5`、已开始 observation、或已进入 maintenance mode
- 后续处理：下一步只允许推进 `T50_CAUSAL_VALIDATION`；在此之前不得抬高 claim ceiling 超过 `T40`

## 边界提醒

- `WP8~WP13` 的 maintenance / frozen upstream 状态不是 `WP14` 的实现证据
- `WP14` 只能读取冻结 surfaces，不能直接回写 `self_model/*`、`endogenous_drives/*`、`reflective_self/*`、`developmental_self/*`、`social_self/*`、`embodied_self/*`
- `OpenEmotion/openemotion/selfhood_integration/*` 当前只证明 owner-level schema/state/store/governance/replay/projection primitives 成立，不证明 current runtime mainline 已消费
- `axis_arbitration_hints` 当前只允许 advisory use，不允许冒充行为裁决
- 不得出现“因为已有多轴 proposal，所以 OpenEmotion 可以直接说话 / 直接发工具 / 直接拿 transport claim”这类边界回退
