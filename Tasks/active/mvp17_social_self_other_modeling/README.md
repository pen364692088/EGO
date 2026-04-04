# MVP17 Social Self / Other-Modeling 执行包

```yaml
task_id: L3-20260403-MVP17-SSOM
created_at: "2026-04-03T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: maintenance_mode
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP17_task_plan.md"
predecessor: "WP11/MVP16"
same_subject_line: true
not_parallel_track: true
scope: "WP12 / MVP17 Social Self / Other-Modeling"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP12/MVP17` 的 formal owner 落到 `OpenEmotion/openemotion/social_self/*`，并把 `trust / commitment / repair` 的 proposal-only contract 正式接到 `proto_self_v2`。

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
- bounded proto-self social contract
- EgoCore runtime social bridge
- historical social / relation materials demotion
- subagent-ready task decomposition

## 当前状态

- formal owner：`T10 completed`
- proto_self_v2 contract：`T20 completed`
- EgoCore runtime bridge：`T30 completed`
- legacy demotion / compat map：`T40 completed`
- causal validation：`T50 completed`
- single controlled observation：`T60 completed`
- batch controlled observation / aggregate：`T70 completed`
- 主链接线：`formal_owner_writeback_stable`
- 启用状态：`controlled_mainline_observation`
- 当前 blocker：`none on the formal owner + proposal-only social writeback + controlled observation axis`
- 当前最小动作：`maintenance verification only; do not expand WP12 scope without a new authority package`

## T10 已证实内容

- `OpenEmotion/openemotion/social_self/*` 已成为 phase 1 的唯一 formal owner 落点
- owner state 已覆盖 `relation_memory / other_model_state / trust_state / commitment_state / repair_state / social_boundary_state / governance_ledger`
- owner store、revision log、replay 与 proposal-only governance 已有最小测试通过
- 旧 social surfaces 仍只作为 reference-only / input-only，不构成 current formal owner

## T20 已证实内容

- `proto_self_v2` 已能消费 `runtime_summary.social_self_context` 与 `runtime_summary.social_context`
- `KernelOutputV2` 已发出锁定的 `social_self_delta / relation_update_candidates / trust_commitment_snapshot / social_policy_hints / repair_proposal_candidates / social_writeback_candidate`
- trace payload 已镜像 `social_context`
- social outputs 仍保持 `proposal_only + behavioral_authority = none`
- legacy `relationship_context` / `emotiond.state.bond_trust` 不会被误当成正式 social contract 输入

## T30 已证实内容

- `RuntimeV2ProtoSelfRuntime` 已把 `social_self_context` 与 `social_context` 注入当前 runtime 主链
- `social_self` proposal-only writeback 已能通过当前 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 主线回到 formal owner store
- `social_writeback_candidate` 在宿主侧仍被锁定为 `proposal_only + behavioral_authority = none + required_gate = social_writeback_gate`
- `state.proto_self_context` 已记录 `social_self_delta / relation_update_candidates / trust_commitment_snapshot / social_policy_hints / repair_proposal_candidates / social_writeback_candidate / social_writeback`
- EgoCore 定向 social bridge 测试已通过，且同文件全量 runtime bridge 回归通过

## T40 已证实内容

- historical social / relation surfaces 已在 `LEGACY_REFERENCE_REGISTER.md` 中完成逐项 demotion，当前只允许 `reference-only` 或 `input-only`
- 旧 `relationship_context / social_chat_handler / repair_context_manager / openemotion_bridge / emotiond.{api,db,state,models,other_minds,persistence,offline_rollouts,memory_legacy}` 现仅以 `LEGACY_REFERENCE_REGISTER.md` 中登记的 `reference-only / input-only` 身份存在，不再构成当前 `WP12` formal owner 或 current-runtime proof
- `OpenEmotion/tools/verify_mvp17_mainline_wiring.py` 已验证：formal owner 路径存在、当前 runtime 主链仍读取 `social_self` bounded contract、legacy register 完整且所列 historical surfaces 仍存在
- `OpenEmotion/tests/mvp17/test_mainline_reference_demotion.py` 已验证 no-second-truth 约束与 current-runtime social consumer 的唯一性

## T50 已证实内容

- `OpenEmotion/tests/mvp17/test_social_causal_formal_proof.py` 已通过 4 组 paired intervention/control proof
- 当前已证明：
  - negative trust drift 会抬高 guarded social weighting
  - commitment breach 会抬高 commitment / repair guard
  - boundary caution 会改变 bounded boundary weighting
  - 仅 social event wording 改写而无结构化指标变化时，不会制造假的 downstream behavioral proof
- `OpenEmotion/tools/run_mvp17_causal_validation.py` 已生成当前 causal proof artifacts：
  - `OpenEmotion/artifacts/mvp17/mvp17_causal_validation_current.json`
  - `OpenEmotion/artifacts/mvp17/mvp17_causal_validation_current.md`
- 当前 causal report 为 `status = pass`、`verification_level = V3`、`evidence_level = E3`、`pair_count = 4`、`passed_count = 4`

## T60 已证实内容

- `OpenEmotion/tests/mvp17/test_controlled_observation.py` 已通过，证明当前 controlled observation runner 会保留 `social_writeback_gate = allow_writeback`、`proposal_only_discipline_consistent = true`、`behavioral_authority_none = true` 与 `replay_valid = true`
- `OpenEmotion/tools/run_mvp17_controlled_observation.py` 已生成当前 single-sample controlled mainline artifact：
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_current.json`
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_current.md`
- 当前 single controlled observation report 为 `status = pass`、`verification_level = V4`、`evidence_level = E4`
- 当前已证明：formal social owner writeback 已被真实 current runtime mainline 单样本观测到，且 writeback 仍保持 `proposal_only + behavioral_authority = none`
- 当前仍未证明：重复样本稳定性、batch aggregate `E5`、maintenance mode、live autonomy、OpenEmotion direct reply authority、broader transport claims

## T70 已证实内容

- `OpenEmotion/tests/mvp17/test_controlled_observation_batch.py` 已通过，证明 scenario bank、batch runner 与 aggregate 逻辑满足 `report_count / accepted_count / proposal_only_discipline_count / behavioral_authority_none_count` 的 `E5` 判据
- `OpenEmotion/scenarios/mvp17_observation_bank/*` 已新增 3 组 repo-authored observation scenarios，覆盖：
  - `boundary_caution_repair_hold`
  - `commitment_breach_strict_repair`
  - `trust_drop_guarded_repair`
- `OpenEmotion/tools/run_mvp17_controlled_observation_batch.py` 已生成当前 aggregate artifacts：
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_batch_current.json`
  - `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_batch_current.md`
- 当前 batch controlled observation report 为 `status = pass`、`verification_level = V5`、`evidence_level = E5`
- 当前已证明：formal social owner writeback 已在 repeated scenario-bank controlled observation 下达到稳定 aggregate，且全程保持 `proposal_only + behavioral_authority = none`
- 当前仍未证明：live autonomy、OpenEmotion direct reply authority、broader transport claims

## T80 已证实内容

- `Tasks/active/mvp17_social_self_other_modeling/WP12_QA_BASELINE.md` 已冻结为 `WP12` 维护态 QA 基线
- `OpenEmotion/artifacts/mvp17/MVP17_COMPLETION_CURRENT.md` 与 `.json` 已记录正式 closeout 口径
- `Tasks/active/mvp17_social_self_other_modeling/MAINTENANCE_LEDGER.md` 已成为后续新增样本与维护态 intake 的唯一台账
- 当前正式口径已收平为：`WP12/MVP17` 已在 formal owner + proposal-only social writeback + controlled observation 轴上进入 `maintenance_mode`
- 当前仍未证明：live autonomy、OpenEmotion direct reply authority、broader transport claims

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
- QA baseline：`WP12_QA_BASELINE.md`
- maintenance ledger：`MAINTENANCE_LEDGER.md`
- contracts：`contracts/`
- task cards：`cards/`
