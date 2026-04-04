# MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity 执行包

```yaml
task_id: L3-20260404-MVP20-HGIC
created_at: "2026-04-04T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: authority_frozen
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP20_task_plan.md"
predecessor: "WP14/MVP19"
same_subject_line: true
not_parallel_track: true
scope: "WP15 / MVP20 Host-Governed Self-Directed Initiative / Commitment Continuity"
claim_ceiling: "authority_frozen / task_package_ready only"
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

- 执行包状态：`authority_frozen`
- authority freeze：`completed`
- `T00_AUTHORITY_FREEZE`：`completed`
- `T10` formal owner：`pending`
- `T20` proto_self_v2 contract：`pending`
- `T30` EgoCore runtime bridge：`pending`
- `T40` legacy demotion / compat map：`pending`
- `T50` causal validation：`pending`
- `T60` single controlled observation：`pending`
- `T70` batch controlled observation / aggregate：`pending`
- `T80` closeout / QA baseline：`pending`
- `T90` subagent assignment sync：`completed`
- 主链接线：`planning_only_no_current_runtime_consumer`
- 启用状态：`not_enabled`
- 当前 blocker：`none at authority-freeze scope`
- 当前最小动作：`T10_FORMAL_OWNER_PACKAGE`

## 当前已证实内容

- `Tasks/MVP20_task_plan.md` 已冻结 `WP15` 的 formal owner、authority source、IO contract、`WP7~WP14` boundary freeze 与 locked non-releases
- `contracts/INITIATIVE_CAPABILITY_OWNERSHIP.md` 已锁定 `WP15` 只拥有 initiative semantics / commitment continuity，不拥有 host execution substrate 或 upstream owner state
- `contracts/INITIATIVE_IO_CONTRACT.md` 已锁定：
  - formal intake 只来自 `WP14` integration、`WP8~WP13` upstream contexts、maintenance / resource / delivery / idle 与 host `initiative_context`
  - outputs 只允许 proposal-only / advisory / gated writeback candidates
  - `host_proactive_candidate` 只是 governed candidate，不得直接触发 delivery / transport
- `LEGACY_REFERENCE_REGISTER.md` 已把 `WP7` proactive tools、runtime proactive substrate 与旧 roadmap 材料登记为 technical reference / host substrate reference
- `SUBAGENT_ASSIGNMENT.md` 与 `cards/T00..T90` 已把 worker mapping、write scope 与后续实现顺序收成可执行 package

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
