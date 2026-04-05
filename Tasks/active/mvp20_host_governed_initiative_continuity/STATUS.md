# MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity 状态台账

```yaml
phase: WP15
status: maintenance_mode
current_layer: maintenance
main_chain_status: current_runtime_initiative_consumer_present_legacy_reference_only
enabled_status: repeated_controlled_observation_passed
trigger_evidence:
  - WP14/MVP19 is the predecessor and remains the last completed maintenance upstream
  - WP15 authority package now exists under Tasks/*
  - formal owner target is frozen to OpenEmotion/openemotion/initiative_self/*
  - current formal runtime mainline target remains runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2
  - formal intake is frozen to runtime_summary selfhood_integration, self_model, endogenous_drive, reflective_self, developmental_self, social_self, embodied_self, maintenance, resource_budget_hint, recent_delivery_outcome, idle_window, and initiative_context surfaces
  - phase 1 outputs are frozen to initiative_self_delta, initiative_proposal_candidates, commitment_execution_snapshot, initiative_policy_hints, host_proactive_candidate, initiative_audit_entries, initiative_writeback_candidate, and trace_payload.initiative_context
  - output discipline is frozen to proposal_only true, behavioral_authority none, and required_gate initiative_writeback_gate
  - WP7 host proactive chain is frozen as host execution substrate / reference-only, not as initiative semantic owner
  - WP8~WP14 remain maintenance / frozen upstreams and may not be reopened by WP15
  - selfhood initiative formal owner package now exists under OpenEmotion/openemotion/initiative_self/*
  - owner state now covers initiative state, initiative priority state, commitment continuity state, initiative proposal candidate, host proactive candidate semantics, and initiative ledger
  - owner package now includes governance validation, replay/history/store primitives, updater logic, and bounded runtime projection
  - targeted owner infra verification passed in OpenEmotion/tests/mvp20/test_initiative_owner_infra.py
  - proto_self_v2 now reads initiative_self through OpenEmotion/openemotion/proto_self_v2/initiative_self_context.py
  - KernelOutputV2 and trace now expose initiative_self_delta, initiative_proposal_candidates, commitment_execution_snapshot, initiative_policy_hints, host_proactive_candidate, initiative_audit_entries, initiative_writeback_candidate, and trace_payload.initiative_context
  - proposal discipline remains proposal_only true, behavioral_authority none, and required_gate initiative_writeback_gate
  - targeted proto-self contract verification passed in OpenEmotion/tests/mvp20/test_initiative_proto_self_integration.py
  - EgoCore runtime_v2 now injects initiative_self_context and initiative_context into the formal runtime mainline
  - current runtime mainline now records initiative_self_delta, initiative_proposal_candidates, commitment_execution_snapshot, initiative_policy_hints, host_proactive_candidate, initiative_audit_entries, initiative_writeback_candidate, initiative_context, and initiative_writeback in bounded host context
  - initiative writeback remains gated to initiative_writeback_gate with proposal_only discipline and behavioral_authority none
  - targeted runtime bridge verification passed in EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k initiative
  - WP7 host proactive runtime and tool surfaces are now explicitly frozen as host_execution_substrate_reference_only / host_substrate_only in LEGACY_REFERENCE_REGISTER.md
  - roadmap and historical proactive materials remain technical reference / reference-only and may not become WP15 current-runtime authority
  - OpenEmotion/tools/verify_mvp20_mainline_wiring.py now proves current runtime initiative consumer presence plus no-second-truth legacy demotion
  - OpenEmotion/tests/mvp20/test_mvp20_mainline_reference_demotion.py now proves host-substrate-only registration, roadmap reference-only registration, and current runtime consumer status
  - OpenEmotion/tests/mvp20/test_initiative_causal_formal_proof.py now proves bounded initiative downstream shifts for carry-forward activation, delivery-failure hold, continuity-fragility review, selfhood-guard override, and wording-only no-effect
  - OpenEmotion/tools/run_mvp20_causal_validation.py now emits the current V3/E3 causal artifact under OpenEmotion/artifacts/mvp20/mvp20_causal_validation_current.*
  - OpenEmotion/tests/mvp20/test_controlled_observation.py now proves the governed single-sample report shape and claim ceiling for MVP20 initiative controlled observation
  - OpenEmotion/tools/run_mvp20_controlled_observation.py now emits the first controlled runtime-mainline single observation artifact under OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_current.*
  - OpenEmotion/scenarios/mvp20_observation_bank/* now seeds the repo-authored MVP20 batch observation bank
  - OpenEmotion/tests/mvp20/test_controlled_observation_batch.py now proves batch aggregation and E5 claim ceiling under three accepted reports
  - OpenEmotion/tools/run_mvp20_controlled_observation_batch.py now emits the current V5/E5 batch artifact under OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_batch_current.*
verification_level: V5
evidence_level: E5
current_blocker: "none on the WP15 controlled axis"
next_minimal_closure_action: "maintenance intake only; do not reopen WP15 without authority breach or regression evidence"
```

## 当前口径

- 可宣称完成：`WP15/MVP20` 已在 formal owner + proposal-only initiative writeback + controlled observation 轴上收口进入 `maintenance_mode`
- 条件性完成：当前维护态只覆盖 owner 层 + proto-self contract + EgoCore runtime bridge + legacy demotion + bounded causal proof + single/batch controlled observation 这条 controlled axis
- 不可宣称完成：`WP15/MVP20` 已放开任何 authority、已具备 live autonomy、已具备 OpenEmotion direct reply authority、已具备 tool authority、或已具备 broader transport claims
- 后续处理：`WP15` 后续样本、回归与预算层噪声只进入 maintenance ledger；若命中 QA baseline 的 reopen 条件，再单独升级讨论
- `T90` 结果：`no-op accepted`，因为 `SUBAGENT_ASSIGNMENT.md` 已与 `cards/T00..T90`、write scope 和依赖顺序保持一致，无需再改

## 边界提醒

- `WP7` 的 host-governed proactive chain 不是 `WP15` 的 semantic owner
- `WP15` 只能读取 `WP8~WP14` 的冻结 surfaces，不能直接回写 upstream owner state
- `initiative_context` 当前只是 host hint surface target，不是 host authority transfer
- 不得出现“因为已有 initiative continuity，所以 OpenEmotion 可以直接说话 / 直接发工具 / 直接拿 transport claim”这类边界回退
