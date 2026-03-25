# MVP13 — Persistent Self-Model

## Task ID
MVP13

## Status
booting

## Objective
创建持久化自我模型，能够跨会话/周期/时间存活。

---

## MVP13 Exit Criteria

| # | Criteria | Target | Status |
|---|----------|--------|--------|
| 1 | Persistence across sessions | ✅ | ⏳ |
| 2 | Structural integrity (schema) | ✅ | ⏳ |
| 3 | Replayability of revisions | ✅ | ⏳ |
| 4 | Identity continuity | ✅ | ⏳ |
| 5 | Drift governance | ✅ | ⏳ |
| 6 | self_model_load_success | ≥ 99% | ⏳ |
| 7 | invariant_violation_count | 0 | ⏳ |

---

## Existing Implementation

已有 `emotiond/self_model.py`:
- ValueWeights (connection, honesty, safety, growth)
- CapabilityBelief
- 需要扩展为持久化 + 审计日志

---

## T01: Self-Model Infrastructure

### T01.1: Extended Schema
基于 `docs/mvp13/SELF_MODEL_STATE_SCHEMA.md`:
- identity_core
- stable_constraints
- behavioral_tendencies
- active_tensions
- long_horizon_orientations
- capability_model
- continuity_trace
- revision_history

### T01.2: Persistence Layer
- 创建 `emotiond/self_model/persistence.py`
- 自我模型持久化到磁盘
- 跨会话加载

### T01.3: Update Rules
- 创建 `emotiond/self_model/updates.py`
- 审计日志记录
- 可重放的修订

---

## Constraints

- Self-model must be structured, not purely textual
- Updates must be audit-logged
- Changes must be replayable
- Identity invariants must be preserved
- Evidence-backed outputs

---

## Allowed Write Targets

- `emotiond/self_model/`
- `artifacts/mvp13/`
- `tests/mvp13/`
