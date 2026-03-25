# CORE_CHAIN_AUDIT.md

## Audit mode
Verification-only. No feature claims accepted without code path or rerun evidence.

## Executive answers to required Q1–Q4

### Q1. 新 self-model 是否已经真实进入 emotiond 主运行链？

**Answer:** No clear evidence that the new MVP13 self-model stack is the active main-chain implementation.

#### Evidence
- `emotiond/core.py:42` imports from `emotiond.self_model`
- actual runtime callsites in `emotiond/core.py` use:
  - `get_self_model_v0(target)` at lines `951`, `1178`, `1393`, `1911`
- legacy implementation exists in `emotiond/self_model/legacy.py`
- new MVP13 package files exist:
  - `emotiond/self_model/schema.py`
  - `emotiond/self_model/persistence.py`
  - `emotiond/self_model/updates.py`
  - `emotiond/self_model/integration.py`
- but no audited `core.py` call to those new modules was found in the main path grep

#### Required answer
- Main chain currently calls: **legacy `self_model_v0` path**
- New self-model status: **implemented but main-chain authenticity insufficient; likely side-path / unwired relative to audited core path**
- Does self-model affect later decision? **Legacy v0 bias does affect later decision path; new MVP13 persistence/update stack not yet shown to causally affect audited main path**

#### Interim verdict
**模块已实现，但主链真实性不足，不能按已完成因果能力验收。**

---

### Q2. 新 reflection engine 是否已经真实替代旧 reflection/self-report 链？

**Answer:** No.

#### Evidence
- `emotiond/core.py:22` imports `run_reflection` from `emotiond.reflection`
- `emotiond/core.py:1004` executes `run_reflection(...)`
- old runtime module exists at `emotiond/reflection.py`
- new module exists at `emotiond/reflection_engine/*`
- no audited `core.py` call into `emotiond/reflection_engine` found

#### Required answer
- Main chain actually runs: **old MVP-8 reflection path**
- New reflection proposal / counterfactual / approval chain called? **No audited main-chain evidence found**
- Current “reflection” is: **text/report mechanism in main chain, not yet evidenced as future-behavior-changing mechanism**

#### Interim verdict
**模块已实现，但主链真实性不足，不能按已完成因果能力验收。**

---

### Q3. drives / homeostasis 是否已经进入主决策因果链？

**Answer:** Only old homeostasis path is evidenced in audited core. New MVP14 drives package has not yet been shown to drive main-chain ranking/decision.

#### Evidence
- `emotiond/core.py:67` imports from old `emotiond.drive_homeostasis`
- `emotiond/core.py:1056-1065` constructs old `DriveState()` and uses modulation from old path
- new package exists at `emotiond/drives/*`
- no audited `emotiond/core.py` reference to `emotiond.drives.integration` or `get_drive_manager()` was found

#### Required answer
- drive bias in audited main chain: **old path only evidenced**
- changing new drives/homeostatic signal changes main-chain behavior? **Not yet evidenced**
- current state appears closer to: **new package has state/module presence, but not proven main-chain influence**

#### Interim verdict
**当前更接近可观测内部状态，而非有效驱动系统。**

---

### Q4. MVP16 daily observation 是否读取真实长期状态，还是默认初始化值？

**Answer:** Current daily observation reads reset/default state, not proven long-horizon accumulated runtime state.

#### Evidence
- `tools/mvp16_daily_check.py` calls `reset_developmental_manager()` in:
  - `check_continuity()`
  - `check_metrics()`
  - `check_invariants()`
- `emotiond/developmental/manager.py` default initialization sets:
  - `continuity_score = 0.8`
  - `growth_rate = 0.5`
  - `identity_stability = 1.0`
  - `governance_compliance = 1.0`
- no persistence read path was evidenced in the developmental manager
- no cross-day accumulated developmental state load path found in the audited daily check path

#### Required answer
- daily check resets manager? **Yes**
- metrics source? **Fresh in-memory manager defaults after reset**
- from real runtime accumulation or default/empty state? **Default/empty state dominated**

#### Interim verdict
**当前 MVP16 观测结果不能作为长期连续性已被验证的充分证据。**

---

## High-risk inconsistencies
1. Master mission file still declares default lock at MVP11.5.
2. Roadmap state declares MVP16 observation.
3. Handoff declares MVP16 completed.
4. Observation result says PASS while daily check resets state and reads default metrics.

## Main-chain authenticity summary
- self-model: legacy path evidenced; new MVP13 path not proven main-chain live
- reflection: old path live; new MVP15 engine not proven live
- drives/homeostasis: old path live; new MVP14 package not proven live
- developmental continuity: tooling-only evidence; runtime continuity not proven
