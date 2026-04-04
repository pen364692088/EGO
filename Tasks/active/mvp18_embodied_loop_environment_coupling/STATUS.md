# MVP18 Embodied Loop / Environment Coupling 状态台账

```yaml
phase: WP13
status: proto_self_contract_complete
current_layer: implementation
main_chain_status: bounded_proto_self_contract_present
enabled_status: not_started
trigger_evidence:
  - WP12/MVP17 maintenance institutionalization complete
  - WP12 remains maintenance_mode
  - WP13 authority package present under Tasks/*
  - embodied_self formal owner package present under OpenEmotion/openemotion/embodied_self/*
  - owner state covers embodied, environment coupling, resource pressure, boundary pressure, action consequence memory, and self-world boundary semantics
  - owner store, replay, governance, and bounded runtime projection tests passed
  - proto_self_v2 consumes runtime_summary.embodied_self_context and environment_context through a bounded embodied contract
  - KernelOutputV2 emits embodied_self_delta, consequence_update_candidates, resource_boundary_snapshot, embodied_policy_hints, repair_or_stabilize_proposal_candidates, and embodied_writeback_candidate
  - trace payload mirrors environment_context without promoting legacy consequence or intervention surfaces
  - embodied outputs remain proposal_only with behavioral_authority locked to none
  - legacy consequence / intervention surfaces explicitly classified as reference-only or input-only
verification_level: V3
evidence_level: E3
current_blocker: "T30 EgoCore runtime bridge not started"
next_minimal_closure_action: "start T30_EGOCORE_RUNTIME_BRIDGE; do not implement observation before T30"
```

## 当前口径

- 可宣称完成：`WP13/MVP18` 已完成 `T20_PROTO_SELF_CONTRACT_INTEGRATION`，当前 embodied owner 已通过 `proto_self_v2` bounded contract 发出 proposal-only outputs
- 条件性完成：当前只证明 owner 层与 `proto_self_v2` bounded contract 已成立，不覆盖 EgoCore runtime bridge、controlled observation、或 `E4/E5`
- 不可宣称完成：`MVP18` 已实现、已接主链、已启用、或已有 `E4/E5`
- 后续处理：只能按 `T30 -> T40 -> T50 -> T60 -> T70 -> T80` 串行推进；不得回头扩写 `WP12`

## 边界提醒

- `WP12` 的 institutionalized maintenance 不是 `WP13` 的实现证据
- `WP12` 新样本只写入其 maintenance ledger
- provider `429/401` 仍按外部预算层风险记录
- `embodied_self/*` 当前已是 formal owner 落点，且已有 `proto_self_v2` bounded consumer；但还没有 EgoCore runtime bridge、single controlled observation、或 batch aggregate evidence
- 不得出现“因为 `WP12` 已 institutionalized，所以 embodied loop 可以直接外发 / 直接拿 transport claim”这类边界回退
