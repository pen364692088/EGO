# MVP17 Social Self / Other-Modeling 执行包

```yaml
task_id: L3-20260403-MVP17-SSOM
created_at: "2026-04-03T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: owner_package_in_place
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP17_task_plan.md"
predecessor: "WP11/MVP16"
same_subject_line: true
not_parallel_track: true
scope: "WP12 / MVP17 Social Self / Other-Modeling"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP12/MVP17` 的 formal owner 落到 `OpenEmotion/openemotion/social_self/*`，并在不接主链的前提下先完成 `trust / commitment / repair` proposal-only owner 基础设施。

## 当前正式 owner target

- `OpenEmotion/openemotion/social_self/*`

## 当前正式主链 target

`social owner -> bounded social projection / proposals -> proto_self_runtime / proto_self_adapter / proto_self_v2 -> governed downstream weighting and social writeback candidate path`

## 当前锁定口径

- `MVP17` 是 `WP12`，接在 `WP11/MVP16` 后，不是新的主体线
- phase 1 只做 `trust / commitment / repair`
- `other-modeling` 当前只允许 bounded state / role continuity 语义，不做泛化心智解读
- `EgoCore/app/response/relationship_context.py`、`EgoCore/app/handlers/social_chat_handler.py`、`EgoCore/app/runtime/repair_context_manager.py`、`EgoCore/app/bridges/openemotion_bridge.py`、`OpenEmotion/emotiond/db.py`、`OpenEmotion/emotiond/state.py`、`OpenEmotion/emotiond/api.py` 只作为 reference-only / input-only 历史 surfaces
- `WP11` 保持 `maintenance_mode`
- `WP11` 新增样本只进对应 maintenance ledger，不回灌为 `WP11` scope reopen
- provider `429/401` 继续标注为外部预算层风险，不回灌为 `WP11` blocker

## 当前范围

- authority / contract freeze
- formal owner package target
- bounded proto-self social contract target
- EgoCore runtime social bridge target
- historical social / relation materials demotion
- subagent-ready task decomposition

## 当前状态

- formal owner：`T10 completed`
- 主链接线：`not_started`
- 启用状态：`formal_owner_only`
- 当前 blocker：`runtime intake and proto_self contract are not connected yet`
- 当前最小动作：`T20_PROTO_SELF_CONTRACT_INTEGRATION`

## T10 已证实内容

- `OpenEmotion/openemotion/social_self/*` 已成为 phase 1 的唯一 formal owner 落点
- owner state 已覆盖 `relation_memory / other_model_state / trust_state / commitment_state / repair_state / social_boundary_state / governance_ledger`
- owner store、revision log、replay 与 proposal-only governance 已有最小测试通过
- 旧 social surfaces 仍只作为 reference-only / input-only，不构成 current formal owner

## 当前不做

- 放开 live autonomy
- 放开 OpenEmotion direct reply authority
- 放开 broader transport claims
- autonomous social outreach
- unbounded other-model mind-reading
- 把 `WP11` maintenance ledger 重新解释成 `WP12` readiness
- 把 historical roadmap / archive social materials 直接当成当前 `WP12` formal proof

## 执行入口

- authority：`Tasks/MVP17_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- task cards：`cards/`
