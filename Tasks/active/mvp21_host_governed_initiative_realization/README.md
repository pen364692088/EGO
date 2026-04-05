# MVP21 Host-Governed Initiative Realization / Proactive Delivery Mediation 执行包

```yaml
task_id: L3-20260405-MVP21-HGIRM
created_at: "2026-04-05T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: proto_self_contract_complete
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP21_task_plan.md"
predecessor: "WP15/MVP20"
same_subject_line: true
not_parallel_track: true
scope: "WP16 / MVP21 Host-Governed Initiative Realization / Proactive Delivery Mediation"
claim_ceiling: "T20 complete only"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP16/MVP21` 的 formal owner target 冻结到 `OpenEmotion/openemotion/initiative_realization/*`，并把 `WP15` 的 initiative proposal outputs、`WP7` 的 proactive runtime substrate、以及 `WP8~WP15` 的 frozen read surfaces 全部收成可执行 authority package。当前已完成 formal owner package与 `proto_self_v2` bounded contract，下一步是把它接到 EgoCore runtime 主链。

## 当前正式 owner target

- `OpenEmotion/openemotion/initiative_realization/*`

## 当前正式主链 target

`initiative_self / selfhood_integration / host proactive hint surfaces -> initiative realization owner / bounded realization proposals -> proto_self_runtime / proto_self_adapter / proto_self_v2 -> governed host-lane mediation and initiative_realization_writeback_candidate path`

## 当前锁定口径

- `MVP21` 是 `WP16`，接在 `WP15/MVP20` 后，不是新的主体线
- phase 1 只冻结 realization / fulfillment / readiness semantics、bounded `controlled_delivery_candidate` 与 `WP7~WP15` boundary freeze
- `EgoCore` 继续保留 runtime / scheduler / proactive delivery / outbox / transport、outward response contract、ask / wait / block / escalate、trace / replay / gate / audit / maintenance ledger、real-world execution / risk adjudication 的最终权威
- `WP7` proactive runtime chain 继续只是 host execution substrate / evidence reference；不是 `WP16` 的 semantic owner
- `WP8~WP15` 都保持 maintenance / frozen upstreams；`WP16` 只能读取冻结 surfaces，不能重写 upstream owner state
- `WP16` 当前不放开 live autonomy、OpenEmotion direct reply authority、tool authority、broader transport claims、或任何 direct reply / tool / transport / authority escalation

## 当前范围

- authority / contract freeze
- formal initiative realization owner package target
- bounded proto-self realization contract target
- EgoCore runtime realization bridge target
- `WP7` proactive runtime substrate freeze
- `WP8~WP15` upstream boundary freeze
- legacy / compat / roadmap register
- subagent-ready task decomposition

## 当前状态

- 执行包状态：`proto_self_contract_complete`
- authority freeze：`completed`
- `T00_AUTHORITY_FREEZE`：`completed`
- `T10` formal owner：`completed`
- `T20` proto_self_v2 contract：`completed`
- `T30` EgoCore runtime bridge：`pending`
- `T40` legacy demotion / compat map：`pending`
- `T50` causal validation：`pending`
- `T60` single controlled observation：`pending`
- `T70` batch controlled observation / aggregate：`pending`
- `T80` closeout / QA baseline：`pending`
- `T90` subagent assignment sync：`completed`
- 主链接线：`openemotion_proto_self_contract_only`
- 启用状态：`authority_owner_and_proto_self_only`
- 当前 blocker：`none on the WP16 proto-self-contract axis`
- 当前最小动作：`T30_EGOCORE_RUNTIME_BRIDGE`

## 当前已证实内容

- `Tasks/MVP21_task_plan.md` 已冻结 `WP16` 的 formal owner、authority source、IO contract、`WP7~WP15` boundary freeze 与 locked non-releases
- `contracts/REALIZATION_CAPABILITY_OWNERSHIP.md` 已锁定 `WP16` 只拥有 semantic readiness / fulfillment / realization interpretation，不拥有 host proactive execution substrate、outbox / transport substrate 或 upstream owner state
- `contracts/REALIZATION_IO_CONTRACT.md` 已锁定：
  - formal intake 只来自 `initiative_self`、`initiative_context`、`selfhood_integration_context`、maintenance / resource / delivery / idle 与 host `host_proactive_context`
  - outputs 只允许 proposal-only / advisory / gated writeback candidates
  - `controlled_delivery_candidate` 与 `host_lane_hints` 只是 governed candidates，不得直接触发 delivery / outbox / transport
- `LEGACY_REFERENCE_REGISTER.md` 已把 `WP7` proactive runtime / outbox / transport surfaces 与旧 roadmap 材料登记为 technical reference / host substrate reference
- `SUBAGENT_ASSIGNMENT.md` 与 `cards/T00..T90` 已把 worker mapping、write scope 与后续实现顺序收成可执行 package
- `OpenEmotion/openemotion/initiative_realization/*` 已形成 formal owner package，覆盖 realization state、delivery readiness state、commitment fulfillment state、initiative realization candidate、controlled delivery candidate、realization ledger，以及 store / replay / governance / updater / bounded projection
- `OpenEmotion/tests/mvp21/test_realization_owner_infra.py` 已通过 `6 passed` 的定向 owner infra 验证
- `OpenEmotion/openemotion/proto_self_v2/initiative_realization_context.py` 已形成唯一 realization contract consumer 路径
- `OpenEmotion/openemotion/proto_self_v2/kernel.py`、`schemas.py` 与 `trace_types.py` 已发出 bounded realization outputs / trace mirror
- `OpenEmotion/tests/mvp21/test_realization_proto_self_integration.py` 与回归套件已通过 `8 passed` 的定向 proto-self contract 验证

## 当前不做

- 不宣称超出当前 authority freeze 的任何实现结论
- 不 reopen `WP7~WP15`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 tool authority
- 不放开 broader transport claims
- 不创建 `WP17` docs

## 执行入口

- authority：`Tasks/MVP21_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- task cards：`cards/`
- subagent assignment：`SUBAGENT_ASSIGNMENT.md`
