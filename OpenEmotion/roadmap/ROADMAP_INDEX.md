# ROADMAP_INDEX.md

> OpenEmotion / emotiond 路线图导航页
> 这是人和 agent 的统一导航入口；执行细节以 `ROADMAP_STATE.json` 与当前阶段文档为准。

---

## 总读取顺序

1. `OpenEmotion/POLICIES/MASTER_AUTONOMOUS_MISSION.md`
2. `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
3. `OpenEmotion/roadmap/ROADMAP_STATE.json`
4. `OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`
5. `OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md`
6. `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
7. `OpenEmotion/roadmap/ROADMAP_INDEX.md`

说明：

- 当前正式阶段判定优先服从统一判定层，不直接从 handoff 或 README 推断。
- `ROADMAP_STATE.json` 当前不包含 `current_doc` / `required_docs[]` 字段，不再把这两个不存在的字段写成默认入口。

---

## 统一判定入口

- 统一规则：`OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`
- 总路线图：`OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md`
- 当前阶段重算：`OpenEmotion/roadmap/SELF_AWARE_CURRENT_STATE_RECOMPUTE_20260328.md`
- 机器可读状态：`OpenEmotion/roadmap/self_aware_normalized_state.json`
- cycle 理论对齐：`OpenEmotion/roadmap/CYCLE_IS_ALL_YOU_NEED_ALIGNMENT_20260328.md`
- cycle 理论机器状态：`OpenEmotion/roadmap/cycle_theory_alignment_state.json`
- Step03A 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_03A_EXECUTION_REPORT_20260328.md`
- Step03A review：`OpenEmotion/roadmap/SELF_AWARE_STEP_03A_REVIEW_20260328.md`
- Step03 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_03_EXECUTION_REPORT_20260328.md`
- Step03 review：`OpenEmotion/roadmap/SELF_AWARE_STEP_03_REVIEW_20260328.md`
- Step04 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_04_EXECUTION_REPORT_20260328.md`
- Step04 review：`OpenEmotion/roadmap/SELF_AWARE_STEP_04_REVIEW_20260328.md`
- Step05 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_05_EXECUTION_REPORT_20260329.md`
- Step05A 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_05A_EXECUTION_REPORT_20260329.md`
- Step05A review：`OpenEmotion/roadmap/SELF_AWARE_STEP_05A_REVIEW_20260329.md`
- Step05B 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_05B_EXECUTION_REPORT_20260329.md`
- Step05B review：`OpenEmotion/roadmap/SELF_AWARE_STEP_05B_REVIEW_20260329.md`
- Step05C 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_05C_EXECUTION_REPORT_20260329.md`
- Step05C review：`OpenEmotion/roadmap/SELF_AWARE_STEP_05C_REVIEW_20260329.md`
- Step06 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_06_EXECUTION_REPORT_20260329.md`
- Step06 review：`OpenEmotion/roadmap/SELF_AWARE_STEP_06_REVIEW_20260329.md`
- Step04A 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_04A_EXECUTION_REPORT_20260328.md`
- Step04A review：`OpenEmotion/roadmap/SELF_AWARE_STEP_04A_REVIEW_20260328.md`
- Step04B 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_04B_EXECUTION_REPORT_20260328.md`
- Step04B review：`OpenEmotion/roadmap/SELF_AWARE_STEP_04B_REVIEW_20260328.md`
- Step04E 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_04E_EXECUTION_REPORT_20260329.md`
- Step04F 执行报告：`OpenEmotion/roadmap/SELF_AWARE_STEP_04F_EXECUTION_REPORT_20260329.md`
- Step04F review：`OpenEmotion/roadmap/SELF_AWARE_STEP_04F_REVIEW_20260329.md`
- 逐步任务：
  - `Tasks/active/SELF_AWARE_STEP_00_normalization_layer.md`
  - `Tasks/active/SELF_AWARE_STEP_01_current_state_recompute.md`
  - `Tasks/active/SELF_AWARE_STEP_02_version_specs.md`
  - `Tasks/active/SELF_AWARE_STEP_03A_cycle_theory_alignment.md`
  - `Tasks/active/SELF_AWARE_STEP_03_mvp12_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_04_mvp13_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_04A_behavioral_influence_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_04B_self_model_authority_resolution.md`
  - `Tasks/active/SELF_AWARE_STEP_04C_mvp13_contract_convergence.md`
  - `Tasks/active/SELF_AWARE_STEP_04D_behavioral_influence_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_04E_owner_backed_decision_surface.md`
  - `Tasks/active/SELF_AWARE_STEP_04F_behavioral_influence_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_05_mvp14_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_05A_drive_authority_resolution.md`
  - `Tasks/active/SELF_AWARE_STEP_05B_drive_mainline_wiring.md`
  - `Tasks/active/SELF_AWARE_STEP_05C_drive_behavioral_influence_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_06_mvp15_formal_proof.md`
  - `Tasks/active/SELF_AWARE_STEP_06A_reflection_mainline_resolution.md`
  - `Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md`
  - `Tasks/active/SELF_AWARE_STEP_08_admission_review.md`

## Phase Navigation

### MVP11.5 — SRAP Stabilization + Intent Alignment
- 主入口：`OpenEmotion/docs/archive/mvp11/MVP11_5_STAGE_OVERVIEW.md`
- 当前重点：`T07.3 Mixed Layer 2 Stabilization Rerun`
- 当前状态：still in SHADOW
- 进入条件：T07.2 completed; checker hardening + contract tightening landed
- 离开条件：完成 mixed Layer 2 基线重建，并满足 readiness criteria
- 建议读取顺序：
  1. `OpenEmotion/docs/archive/mvp11/MVP11_5_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/archive/mvp11/T07_3_MIXED_LAYER2_RERUN.md`
  3. `OpenEmotion/docs/archive/mvp11/MVP11_5_READINESS_CRITERIA.md`
  4. `OpenEmotion/roadmap/versions/MVP11_5.spec.yaml`

### MVP12 — Developmental Core Sandbox
- 主入口：`OpenEmotion/docs/archive/mvp12/MVP12_STAGE_OVERVIEW.md`
- 目标：建立发育核沙盒，只生成内部候选，不拿最终行为权
- 进入条件：MVP11.5 completed + Gate A/B/C pass + state updated
- 离开条件：developmental core cycle 可追踪、可 replay、sandbox integrity 成立
- 前置方向守门：`OpenEmotion/roadmap/CYCLE_IS_ALL_YOU_NEED_ALIGNMENT_20260328.md`
- 建议读取顺序：
  1. `OpenEmotion/roadmap/CYCLE_IS_ALL_YOU_NEED_ALIGNMENT_20260328.md`
  1. `OpenEmotion/docs/archive/mvp12/MVP12_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/archive/mvp12/DEVELOPMENTAL_CORE_ARCHITECTURE.md`
  3. `OpenEmotion/docs/archive/mvp12/INTERNAL_CYCLE_RUNTIME.md`
  4. `OpenEmotion/docs/archive/mvp12/SANDBOX_GOVERNANCE.md`
  5. `OpenEmotion/docs/archive/mvp12/MVP12_EXIT_CRITERIA.md`
  6. `OpenEmotion/roadmap/versions/MVP12.spec.yaml`

### MVP13 — Persistent Self-Model
- 主入口：`OpenEmotion/docs/mvp13/MVP13_STAGE_OVERVIEW.md`
- 目标：建立跨时间持续、结构化、可审计的 self-model
- 进入条件：`MVP12` component-level formal proof 已发布，且不得把该结论包装成 `Stage 3 passed`
- 离开条件：self-model persistence / replayability / drift governance 达标，且 `behavioral influence` 正式证明完成
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp13/MVP13_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp13/PERSISTENT_SELF_MODEL_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp13/SELF_MODEL_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp13/SELF_MODEL_UPDATE_POLICY.md`
  5. `OpenEmotion/docs/mvp13/IDENTITY_INVARIANTS_AND_DRIFT_POLICY.md`
  6. `OpenEmotion/docs/mvp13/MVP13_EXIT_CRITERIA.md`
  7. `OpenEmotion/roadmap/versions/MVP13.spec.yaml`
  8. `OpenEmotion/roadmap/SELF_AWARE_STEP_04_EXECUTION_REPORT_20260328.md`
  9. `OpenEmotion/roadmap/SELF_AWARE_STEP_04A_EXECUTION_REPORT_20260328.md`
  10. `OpenEmotion/roadmap/SELF_AWARE_STEP_04B_EXECUTION_REPORT_20260328.md`
  11. `OpenEmotion/roadmap/SELF_AWARE_STEP_04C_EXECUTION_REPORT_20260328.md`
  12. `OpenEmotion/roadmap/SELF_AWARE_STEP_04C_REVIEW_20260328.md`
  13. `OpenEmotion/roadmap/SELF_AWARE_STEP_04D_EXECUTION_REPORT_20260329.md`
  14. `OpenEmotion/roadmap/SELF_AWARE_STEP_04E_EXECUTION_REPORT_20260329.md`
  15. `OpenEmotion/roadmap/SELF_AWARE_STEP_04F_EXECUTION_REPORT_20260329.md`
  16. `OpenEmotion/roadmap/SELF_AWARE_STEP_04F_REVIEW_20260329.md`
  17. `OpenEmotion/roadmap/SELF_AWARE_STEP_05_EXECUTION_REPORT_20260329.md`
  18. `OpenEmotion/roadmap/SELF_AWARE_STEP_05A_EXECUTION_REPORT_20260329.md`
  19. `Tasks/active/SELF_AWARE_STEP_05_mvp14_formal_proof.md`
  20. `Tasks/active/SELF_AWARE_STEP_05A_drive_authority_resolution.md`
  21. `OpenEmotion/roadmap/SELF_AWARE_STEP_05B_EXECUTION_REPORT_20260329.md`
  22. `OpenEmotion/roadmap/SELF_AWARE_STEP_05B_REVIEW_20260329.md`
  23. `Tasks/active/SELF_AWARE_STEP_05B_drive_mainline_wiring.md`
  24. `Tasks/active/SELF_AWARE_STEP_05C_drive_behavioral_influence_formal_proof.md`

### MVP14 — Endogenous Drives + Self-Maintenance
- 主入口：`OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
- 目标：让内部状态以结构性压力的方式影响优先级与自我维持
- 进入条件：MVP13 behavioral influence formal proof completed，且 self-model authority 已统一
- 注：在当前路线中，`MVP13` 相关 authority 与 behavioral proof 已完成；`MVP14` 也已完成 `drive authority resolution -> bounded mainline wiring -> drive behavioral influence formal proof`，因此后续唯一主线已切到 `MVP15 formal proof`
- 离开条件：drive system / maintenance runtime / governance integrity 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp14/ENDOGENOUS_DRIVES_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp14/DRIVE_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp14/SELF_MAINTENANCE_RUNTIME.md`
  5. `OpenEmotion/docs/mvp14/DRIVE_GOVERNANCE_AND_PRIORITY_POLICY.md`
  6. `OpenEmotion/docs/mvp14/MVP14_EXIT_CRITERIA.md`
  7. `OpenEmotion/roadmap/versions/MVP14.spec.yaml`
  8. `OpenEmotion/roadmap/SELF_AWARE_STEP_05C_EXECUTION_REPORT_20260329.md`
  9. `OpenEmotion/roadmap/SELF_AWARE_STEP_05C_REVIEW_20260329.md`

### MVP15 — Reflective Self / Counterfactual Self
- 主入口：`OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
- 目标：建立受治理的自我反思与反事实自我评估
- 进入条件：MVP14 completed
- 注：当前路线里，`MVP15` 已完成基础 infra 与 shadow artifact 诊断，但 Step06 已确认正式主链仍是 `reflection_shadow`，缺少 writeback / downstream consumer；因此下一步不是直接 causal proof，而是 `Step06A`
- 离开条件：reflection proposals、counterfactual evaluation、replayability 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp15/REFLECTIVE_SELF_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp15/REFLECTION_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp15/COUNTERFACTUAL_SELF_EVALUATION.md`
  5. `OpenEmotion/docs/mvp15/REFLECTIVE_GOVERNANCE_POLICY.md`
  6. `OpenEmotion/docs/mvp15/MVP15_EXIT_CRITERIA.md`
  7. `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
  8. `OpenEmotion/roadmap/SELF_AWARE_STEP_06_EXECUTION_REPORT_20260329.md`
  9. `Tasks/active/SELF_AWARE_STEP_06A_reflection_mainline_resolution.md`

### MVP16 — Open Developmental Self
- 主入口：`OpenEmotion/docs/mvp16/MVP16_STAGE_OVERVIEW.md`
- 目标：形成长期、开放、受治理的发展连续性
- 进入条件：MVP15 completed
- 离开条件：long-horizon continuity、governed growth、identity preservation 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp16/MVP16_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp16/OPEN_DEVELOPMENTAL_SELF_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp16/DEVELOPMENTAL_CONTINUITY_SCHEMA.md`
  4. `OpenEmotion/docs/mvp16/OPEN_ENDED_GROWTH_POLICY.md`
  5. `OpenEmotion/docs/mvp16/IDENTITY_STABILITY_AND_EXPANSION_GOVERNANCE.md`
  6. `OpenEmotion/docs/mvp16/MVP16_EXIT_CRITERIA.md`
  7. `OpenEmotion/roadmap/versions/MVP16.spec.yaml`

---

## Common Anti-Drift Rules

- 任何阶段都先证明结构和因果，再允许语言和表现
- 任何阶段都不得绕过 Governor / Gate / replay discipline
- 恢复执行时不得凭“记忆”直接跳任务，必须回到 state + handoff
- 如果阶段文档缺失，以 `blocked` 处理，不得自行虚构完成状态
- 当前正式阶段判断若与 handoff/README 冲突，以统一判定层为准
- 不得把 Stage1/self-report/storage-only 线冒充成 cycle-theory formal proof
