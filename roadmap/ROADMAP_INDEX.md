# ROADMAP_INDEX.md

> OpenEmotion / emotiond 路线图导航页  
> 这是人和 agent 的统一导航入口；执行细节以 `ROADMAP_STATE.json` 与当前阶段文档为准。

---

## 总读取顺序

1. `OpenEmotion/POLICIES/MASTER_AUTONOMOUS_MISSION.md`
2. `OpenEmotion/roadmap/ROADMAP_STATE.json`
3. `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
4. `OpenEmotion/roadmap/ROADMAP_INDEX.md`
5. `ROADMAP_STATE.json.current_doc`
6. `ROADMAP_STATE.json.required_docs[]`

---

## Phase Navigation

### MVP11.5 — SRAP Stabilization + Intent Alignment
- 主入口：`OpenEmotion/docs/mvp11/MVP11_5_STAGE_OVERVIEW.md`
- 当前重点：`T07.3 Mixed Layer 2 Stabilization Rerun`
- 当前状态：still in SHADOW
- 进入条件：T07.2 completed; checker hardening + contract tightening landed
- 离开条件：完成 mixed Layer 2 基线重建，并满足 readiness criteria
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp11/MVP11_5_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp11/T07_3_MIXED_LAYER2_RERUN.md`
  3. `OpenEmotion/docs/mvp11/MVP11_5_READINESS_CRITERIA.md`
  4. `OpenEmotion/docs/mvp11/LAYER_REPORTING_POLICY.md`

### MVP12 — Developmental Core Sandbox
- 主入口：`OpenEmotion/docs/mvp12/MVP12_STAGE_OVERVIEW.md`
- 目标：建立发育核沙盒，只生成内部候选，不拿最终行为权
- 进入条件：MVP11.5 completed + Gate A/B/C pass + state updated
- 离开条件：developmental core cycle 可追踪、可 replay、sandbox integrity 成立
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp12/MVP12_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp12/DEVELOPMENTAL_CORE_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp12/INTERNAL_CYCLE_RUNTIME.md`
  4. `OpenEmotion/docs/mvp12/SANDBOX_GOVERNANCE.md`
  5. `OpenEmotion/docs/mvp12/MVP12_EXIT_CRITERIA.md`

### MVP13 — Persistent Self-Model
- 主入口：`OpenEmotion/docs/mvp13/MVP13_STAGE_OVERVIEW.md`
- 目标：建立跨时间持续、结构化、可审计的 self-model
- 进入条件：MVP12 completed
- 离开条件：self-model persistence / replayability / drift governance 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp13/MVP13_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp13/PERSISTENT_SELF_MODEL_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp13/SELF_MODEL_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp13/SELF_MODEL_UPDATE_POLICY.md`
  5. `OpenEmotion/docs/mvp13/IDENTITY_INVARIANTS_AND_DRIFT_POLICY.md`
  6. `OpenEmotion/docs/mvp13/MVP13_EXIT_CRITERIA.md`

### MVP14 — Endogenous Drives + Self-Maintenance
- 主入口：`OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
- 目标：让内部状态以结构性压力的方式影响优先级与自我维持
- 进入条件：MVP13 completed
- 离开条件：drive system / maintenance runtime / governance integrity 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp14/ENDOGENOUS_DRIVES_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp14/DRIVE_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp14/SELF_MAINTENANCE_RUNTIME.md`
  5. `OpenEmotion/docs/mvp14/DRIVE_GOVERNANCE_AND_PRIORITY_POLICY.md`
  6. `OpenEmotion/docs/mvp14/MVP14_EXIT_CRITERIA.md`

### MVP15 — Reflective Self / Counterfactual Self
- 主入口：`OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
- 目标：建立受治理的自我反思与反事实自我评估
- 进入条件：MVP14 completed
- 离开条件：reflection proposals、counterfactual evaluation、replayability 达标
- 建议读取顺序：
  1. `OpenEmotion/docs/mvp15/MVP15_STAGE_OVERVIEW.md`
  2. `OpenEmotion/docs/mvp15/REFLECTIVE_SELF_ARCHITECTURE.md`
  3. `OpenEmotion/docs/mvp15/REFLECTION_STATE_SCHEMA.md`
  4. `OpenEmotion/docs/mvp15/COUNTERFACTUAL_SELF_EVALUATION.md`
  5. `OpenEmotion/docs/mvp15/REFLECTIVE_GOVERNANCE_POLICY.md`
  6. `OpenEmotion/docs/mvp15/MVP15_EXIT_CRITERIA.md`

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

---

## Common Anti-Drift Rules

- 任何阶段都先证明结构和因果，再允许语言和表现
- 任何阶段都不得绕过 Governor / Gate / replay discipline
- 恢复执行时不得凭“记忆”直接跳任务，必须回到 state + handoff
- 如果阶段文档缺失，以 `blocked` 处理，不得自行虚构完成状态
