# MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity 执行包

```yaml
task_id: L3-20260404-MVP20-HGIC
created_at: "2026-04-04T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: maintenance_mode
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP20_task_plan.md"
predecessor: "WP14/MVP19"
same_subject_line: true
not_parallel_track: true
scope: "WP15 / MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity"
claim_ceiling: "maintenance_mode on the controlled axis only"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP15/MVP20` 的 formal owner target 冻结到 `OpenEmotion/openemotion/initiative_self/*`，并把 `WP14` 的 integrated tendency、`WP7` 的 host proactive substrate、以及 `WP8~WP14` 的 frozen read surfaces 全部收成可执行 authority package。

## 当前正式 owner target

- `OpenEmotion/openemotion/initiative_self/*`

## 当前正式主链 target

`frozen upstream read surfaces -> initiative owner / bounded initiative proposals -> proto_self_runtime / proto_self_adapter / proto_self_v2 -> governed host-proactive candidate and initiative_writeback_candidate path`

## 当前锁定口径

- `MVP20` 是 `WP15`，接在 `WP14/MVP19` 后，不是新的主体线
- phase 1 只冻结 initiative semantics、commitment continuity、bounded host-proactive candidate 与 `WP7~WP14` boundary freeze
- `EgoCore` 继续保留 runtime / proactive delivery / outbox / transport、outward response contract、ask / wait / block / escalate、trace / replay / gate / audit / maintenance ledger、real-world execution / risk adjudication 的最终权威
- `WP7` proactive chain 继续只是 host execution substrate / evidence reference；不是 `WP15` 的 semantic owner
- `WP8~WP14` 都保持 maintenance / frozen upstreams；`WP15` 只能读取冻结 surfaces，不能重写 upstream owner state
- `WP15` 当前不放开 live autonomy、OpenEmotion direct reply authority、tool authority、broader transport claims、或任何 direct reply / tool / transport / authority escalation

## 当前范围

- authority / contract freeze
- formal initiative owner package target
- bounded proto-self initiative contract target
- EgoCore runtime initiative bridge target
- `WP7` proactive substrate freeze
- `WP8~WP14` upstream boundary freeze
- legacy / compat / roadmap register
- subagent-ready task decomposition

## 当前状态

- 执行包状态：`maintenance_mode`
- authority freeze：`completed`
- `T00_AUTHORITY_FREEZE`：`completed`
- `T10` formal owner：`completed`
- `T20` proto_self_v2 contract：`completed`
- `T30` EgoCore runtime bridge：`completed`
- `T40` legacy demotion / compat map：`completed`
- `T50` causal validation：`completed`
- `T60` single controlled observation：`completed`
- `T70` batch controlled observation / aggregate：`completed`
- `T80` closeout / QA baseline：`completed`
- `T90` subagent assignment sync：`no-op accepted (already in sync)`
- 主链接线：`current_runtime_initiative_consumer_present_legacy_reference_only`
- 启用状态：`repeated_controlled_observation_passed`
- 当前 blocker：`none on the WP15 controlled axis`
- 当前最小动作：`maintenance verification / ledger intake only`

## 当前已证实内容

- `Tasks/MVP20_task_plan.md` 已冻结 `WP15` 的 formal owner、authority source、IO contract、`WP7~WP14` boundary freeze 与 locked non-releases
- `contracts/INITIATIVE_CAPABILITY_OWNERSHIP.md` 已锁定 `WP15` 只拥有 initiative semantics / commitment continuity，不拥有 host execution substrate 或 upstream owner state
- `contracts/INITIATIVE_IO_CONTRACT.md` 已锁定：
  - formal intake 只来自 `WP14` integration、`WP8~WP13` upstream contexts、maintenance / resource / delivery / idle 与 host `initiative_context`
  - outputs 只允许 proposal-only / advisory / gated writeback candidates
  - `host_proactive_candidate` 只是 governed candidate，不得直接触发 delivery / transport
- `LEGACY_REFERENCE_REGISTER.md` 已把 `WP7` proactive tools、runtime proactive substrate 与旧 roadmap 材料登记为 technical reference / host substrate reference
- `SUBAGENT_ASSIGNMENT.md` 与 `cards/T00..T90` 已把 worker mapping、write scope 与后续实现顺序收成可执行 package
- `OpenEmotion/openemotion/initiative_self/*` 现已落地为 formal owner package，覆盖 initiative state、initiative priority state、commitment continuity state、initiative proposal candidate、host-proactive candidate semantics 与 initiative ledger
- `OpenEmotion/tests/mvp20/test_initiative_owner_infra.py` 已验证 bounded projection、proposal-only governance、store roundtrip、replay primitives 与 legacy reference-only exclusion
- `OpenEmotion/openemotion/proto_self_v2/initiative_self_context.py` 现已把 `runtime_summary.initiative_self_context` 与 `runtime_summary.initiative_context` 通过唯一 bounded consumer path 接进 `proto_self_v2`
- `KernelOutputV2` 与 trace 现已新增 `initiative_self_delta / initiative_proposal_candidates / commitment_execution_snapshot / initiative_policy_hints / host_proactive_candidate / initiative_audit_entries / initiative_writeback_candidate / trace_payload.initiative_context`
- `OpenEmotion/tests/mvp20/test_initiative_proto_self_integration.py` 已验证 proposal-only discipline、legacy-not-consumed 与 bounded context/trace 输出
- `EgoCore/app/runtime_v2/proto_self_runtime.py` 现已把 `initiative_self_context / initiative_context` 注入正式 runtime 主链，并把 initiative outputs 以 gated bounded writeback 形式挂回宿主上下文
- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k initiative` 已验证 current runtime mainline wiring、proposal-only discipline 与 required gate 保持不变
- `LEGACY_REFERENCE_REGISTER.md` 现已把 `WP7` host proactive substrate 明确冻结为 `host_execution_substrate_reference_only / host_substrate_only`，并明确旧 transport / outbox 证据不能冒充 `WP15` initiative proof
- `OpenEmotion/tools/verify_mvp20_mainline_wiring.py` 现已能静态证明 current runtime initiative consumer 存在，同时 `WP7` proactive substrate 与旧 roadmap 材料保持 reference-only / host-substrate-only
- `OpenEmotion/tests/mvp20/test_mvp20_mainline_reference_demotion.py` 现已验证 no-second-truth demotion 与 current runtime consumer status
- `OpenEmotion/tests/mvp20/test_initiative_causal_formal_proof.py` 现已通过 4 组 paired intervention/control 与 1 组 wording-only no-effect guard，证明 initiative / commitment continuity proposals 会改变 bounded downstream weighting，而不是只改文本
- `OpenEmotion/tools/run_mvp20_causal_validation.py` 现已生成 `OpenEmotion/artifacts/mvp20/mvp20_causal_validation_current.md/.json`，当前 causal report 口径为 `V3/E3`
- `OpenEmotion/tests/mvp20/test_controlled_observation.py` 现已验证 `MVP20` single controlled observation report shape、`allow_writeback` gate、`behavioral_authority_none` 与 `V4/E4` claim ceiling
- `OpenEmotion/tools/run_mvp20_controlled_observation.py` 现已生成 `OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_current.md/.json`，当前只证明首个 controlled runtime-mainline `V4/E4` single observation
- `OpenEmotion/scenarios/mvp20_observation_bank/*` 现已提供 3 条 `repo_authored` batch scenarios，用于 MVP20 repeated controlled observation aggregate
- `OpenEmotion/tests/mvp20/test_controlled_observation_batch.py` 已把 batch controlled observation 的最小 contract 固定成回归测试
- 当前 batch controlled observation 结果为：
  - `status = pass`
  - `verification_level = V5`
  - `evidence_level = E5`
  - `report_count = 3`
  - `accepted_count = 3`
  - `proposal_only_discipline_count = 3`
  - `behavioral_authority_none_count = 3`
- 这证明当前 formal owner + current runtime mainline 已在 repeated controlled observation 轴上拿到 initiative proposal-only writeback 的 `V5/E5` aggregate；当前 closeout、`maintenance_mode`、QA baseline 与 completion artifact 现已冻结，但这仍不证明 authority 放开

## 维护态入口

- QA baseline：`WP15_QA_BASELINE.md`
- maintenance ledger：`MAINTENANCE_LEDGER.md`
- completion artifact：`OpenEmotion/artifacts/mvp20/MVP20_COMPLETION_CURRENT.md`

后续任何 `WP15` maintenance 结论，都必须引用当前 completion artifact 与 QA baseline，不能重新把 `WP15` 写回 implementation / observation_started。

## 当前不做

- 不宣称超出当前 authority freeze 的任何实现结论
- 不 reopen `WP7~WP14`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 tool authority
- 不放开 broader transport claims

## 执行入口

- authority：`Tasks/MVP20_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- task cards：`cards/`
- subagent assignment：`SUBAGENT_ASSIGNMENT.md`
