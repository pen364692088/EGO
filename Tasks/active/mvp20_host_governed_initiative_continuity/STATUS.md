# MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity 状态台账

```yaml
phase: WP15
status: authority_frozen
current_layer: planning
main_chain_status: planning_only_no_current_runtime_consumer
enabled_status: not_enabled
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
verification_level: V1
evidence_level: E1
current_blocker: "none at authority-freeze scope"
next_minimal_closure_action: "T10_FORMAL_OWNER_PACKAGE"
```

## 当前口径

- 可宣称完成：`WP15/MVP20` 的 authority package 已冻结，状态是 `authority_frozen / task_package_ready`
- 条件性完成：当前只覆盖 formal owner、authority source、IO contract 与 boundary freeze；不覆盖 owner/runtime 实现
- 不可宣称完成：`MVP20` 已实现、已接主链、已 observation_started、已有 `E4/E5`、或已进入 `maintenance_mode`
- 后续处理：只有在 `T10` 起步后，才允许进入实现口径；当前不能跳过 authority package 直接做代码

## 边界提醒

- `WP7` 的 host-governed proactive chain 不是 `WP15` 的 semantic owner
- `WP15` 只能读取 `WP8~WP14` 的冻结 surfaces，不能直接回写 upstream owner state
- `initiative_context` 当前只是 host hint surface target，不是 host authority transfer
- 不得出现“因为已有 initiative continuity，所以 OpenEmotion 可以直接说话 / 直接发工具 / 直接拿 transport claim”这类边界回退
