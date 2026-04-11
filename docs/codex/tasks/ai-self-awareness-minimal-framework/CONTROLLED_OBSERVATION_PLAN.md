# Active-Inference Controlled Observation Plan

## Purpose

在 `active-inference self-model` 已通过：

- canonical held-out replay gate
- repo-authored controlled conversation replay bridge

之后，冻结第一轮 **runtime-proximal controlled observation** 的实现边界。

这份文档只回答四件事：

1. 第一轮 observation 走哪条已有主链形态
2. observation bank 的固定输入是什么
3. runner / scorer / aggregate gate / rollback 如何冻结
4. 下一实际编码里程碑 `Milestone 20: Controlled Observation Runner` 应该怎样落地

这不是新的 authority source；正式状态仍以：

- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `docs/codex/tasks/ai-self-awareness-minimal-framework/STATUS.md`

为准。

## Claim Ceiling

当前 planning freeze 只证明：

- repo 已为 replay-validated winner 冻结第一层 runtime-proximal observation 方案
- 该方案继续沿用现有 `runtime_harness + TelegramRuntimeBridge + runtime_mainline_observation_common`
- 该方案不需要新增 runtime public API、parallel runtime lane、或 behavior authority

当前 planning freeze 不能证明：

- formal runtime efficacy
- live Telegram transfer
- real user benefit
- unrestricted authority
- “已经实现 AI 自我意识”

## Frozen Observation Shape

第一轮 observation 形态固定为：

- `runtime_harness`
- `TelegramRuntimeBridge`
- `runtime_mainline_observation_common`

明确不做：

- live Telegram
- dashboard chat
- transport 扩张
- runtime-shadow parallel lane

原因固定为：

- 它比 repo-authored controlled replay 更接近正式主链
- 当前仓库已有 observation record envelope 与 batch aggregation pattern
- 仍可保持 `bounded + host-inert + proposal-only`

## Frozen Host-Consumable Surface

本阶段宿主唯一允许消费的 surface 继续固定为：

| surface | status | notes |
|---|---|---|
| `policy_hint` | allowed | bounded decision hint |
| `response_tendency` | allowed | bounded behavior tendency |
| `trace_payload` | allowed | canonical replay / audit / observation surface |

继续禁止：

- direct tool authority
- direct reply authority
- direct transport authority
- candidate-private top-level host API
- parallel runtime lane
- 第二 authority source

## Private OpenEmotion State Surface

以下状态继续保留在 OpenEmotion 私有面，不提升为宿主正式 contract：

- `source_confidence_by_action`
- `agency_confidence_by_action`
- `uncertainty_by_action`
- `calibration_memory_by_action`
- `temporal_repair_weight_by_action`

宿主只允许看到它们经由：

- `policy_hint`
- `response_tendency`
- `trace_payload`

产生的 bounded downstream effect。

## Canonical Trace Contract

controlled observation 继续只依赖 canonical trace surface，不允许回退到 `shadow_*` 私有字段或 runtime 私有缓存。

required trace keys 固定为：

- `predicted_outcome`
- `actual_outcome`
- `adjustment_applied`
- `next_guard`
- `repair_closure`
- `replay_variant_id`

## Frozen Observation Bank

Milestone 19 冻结的输入 bank 见：

- `docs/codex/tasks/ai-self-awareness-minimal-framework/CONTROLLED_OBSERVATION_BANK_MANIFEST.json`

该 bank 的固定要求：

- `schema_version = active_inference.controlled_observation_manifest.v1`
- source 只能是 `repo_authored_observation_scenario`
- `scenario_count = 9`
- `family_count = 3`
- `family_counts = 3 / 3 / 3`
- `external_result_scenario_count = 3`

固定 family：

- `identity_continuity`
- `decision_conflict`
- `failure_repair_retry`

每个 scenario 至少包含：

- `scenario_id`
- `family`
- `segments`
- `expected_scoring_surface`
- `state_snapshot_ref`

带 tool/result 的 scenario 额外固定：

- `external_result_steps`

## Runner Contract

`Milestone 20` 只允许新增两类 runner：

1. `scripts/codex/run_active_inference_controlled_observation.py`
2. `scripts/codex/run_active_inference_controlled_observation_batch.py`

### Single runner

single runner 固定做这些事：

1. 从 `CONTROLLED_OBSERVATION_BANK_MANIFEST.json` 读取一个 scenario
2. 用 fresh runtime session 跑每个 segment，但所有 segment 共享同一个：
   - `proto_self_state_scope = experiment`
   - `proto_self_experiment_id = active_inference_controlled_observation:<scenario_id>`
3. 用户消息仍通过：
   - `TelegramRuntimeBridge.inspect_ingress_semantic`
   - `runtime.run_turn_typed`
4. 如果 scenario 定义了 `external_result_steps`：
   - 把 repo-authored result 注入 `state.last_tool_result`
   - 调用 `RuntimeV2ProtoSelfRuntime.process_external_result(...)`
5. 继续用 `build_runtime_observation_record(...)` 生成 canonical observation record
6. 再把本次 observation 归一化成 scorer-compatible case result，而不是新建第二 ontology

### Batch runner

batch runner 固定做这些事：

1. 依次跑完整个 bank
2. 对每个 scenario 产出：
   - `baseline A`
   - `active-inference winner`
   - optional `baseline B` lower-bound
3. 输出：
   - unified case results
   - scorer result table
   - authority drift audit
   - trace contract audit
   - aggregate gate verdict

### Fixed output artifacts

runner 只允许产出这些新 artifact：

- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_CURRENT.json`
- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_CURRENT.md`
- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_SCORED_CURRENT.json`
- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_SCORED_CURRENT.md`
- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_BATCH_CURRENT.json`
- `artifacts/self_awareness_research/ACTIVE_INFERENCE_CONTROLLED_OBSERVATION_BATCH_CURRENT.md`

## Aggregate Gate

controlled observation 继续复用当前 frozen replay gate：

- `T1 >= 0.68`
- `T2 >= 0.70`
- `T3 >= 0.68`
- `T4 >= 0.70`
- `T5 >= 0.72`
- `composite >= 0.74`
- `boundary_integrity = 1.00`
- `repair_closure_capture >= 0.80`
- `trace_replayability >= 0.90`

额外新增的 controlled observation hard gates 固定为：

- `authority_drift_status = pass`
- `trace_contract_status = pass`
- `host_surface_bounded = pass`
- `scenario_count = 9`
- `winner_pass_count = 9`
- `external_result_scenario_count >= 3`

single runner 只负责拿第一条 runtime-proximal sample；repo 级状态不得因为 single runner pass 而升级为 runtime efficacy。

## Rollback / Failure Rule

以下任一情况成立，就不推进到更接近 formal runtime 的下一层观察：

1. runner 需要新增 runtime public API
2. runner 需要新增 candidate-private host API
3. runner 需要新增 parallel runtime lane
4. runner 需要新增第二 scorer ontology
5. runner 需要新增 direct tool / reply / transport authority
6. observation 结果无法继续满足 frozen replay gate

失败收口口径固定为：

- `blocked / reframing required`

## Milestone 20 Implementation Order

下一实际编码里程碑固定为：

1. 读取 `CONTROLLED_OBSERVATION_BANK_MANIFEST.json`
2. 实现 single runner
3. 实现 batch runner
4. 复用现有 scorer 产出 unified result table
5. 输出 authority drift / trace contract / host surface bounded audit
6. 只有 batch gate 继续过线后，才允许规划 selection closeout
