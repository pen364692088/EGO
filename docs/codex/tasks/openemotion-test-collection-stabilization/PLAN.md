# OpenEmotion Test Collection Stabilization - PLAN

## Task summary

这是一个实现 / 验证层的 bugfix slice。目标是只修当前 `OpenEmotion test suite` 暴露出的 16 个 collection/import blocker，先把 full verify 从“测不起来”推进到“能真实执行更深测试面”。

## Milestones

### Milestone 1: Repair dependency and import surface

- scope: 修 `yaml` / `numpy` 依赖缺口与 `integrations.openclaw` 导入缺口，确保对应测试与脚本能完成 import/collection
- files / areas likely touched:
  - `OpenEmotion/pyproject.toml`
  - `OpenEmotion/integrations/**`
- acceptance:
  - 当前 `yaml` / `numpy` / `integrations` 导致的 collection errors 消失
- validation:
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest tests/test_user_affect.py tests/test_self_report_interpreter.py tests/test_auto_tune_v0.py tests/test_auto_tune_v0_1.py tests/test_auto_tune_v0_2.py tests/test_auto_tune_v0_3.py tests/test_eval_suite_v2_1.py tests/test_eval_suite_v2_2.py tests/test_eval_suite_v2_3.py tests/test_mvp4_eval.py tests/test_e2e_replay.py tests/test_causal_evidence.py tests/test_us641_knob_registry.py --collect-only -q`
- rollback note: 若依赖补齐后引入更大环境漂移，回退到上一 slice 的 runtime bootstrap 提交基线

### Milestone 2: Repair legacy drives collection compatibility

- scope: 修 `emotiond.drives` 对 MVP10 legacy tests 的最小兼容面，不破坏 MVP14 package exports
- files / areas likely touched:
  - `OpenEmotion/emotiond/drives/__init__.py`
  - `OpenEmotion/tests/mvp10/test_drives_generation.py`
  - `OpenEmotion/tests/mvp10/test_intervention_freeze_valence.py`
  - `OpenEmotion/tests/mvp10/test_valence_policy_chain.py`
- acceptance:
  - 三个 MVP10 collection errors 消失
  - MVP14 package-level imports 不被破坏
- validation:
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest tests/mvp10/test_drives_generation.py tests/mvp10/test_intervention_freeze_valence.py tests/mvp10/test_valence_policy_chain.py tests/mvp14/test_drive_infra.py tests/mvp14/test_drive_integration.py tests/mvp14/test_e2e_gate_b.py -q`
- rollback note: 若 package-level兼容层影响 MVP14 tests，回退到前一提交并改为更窄的 test-side compatibility import

## Progress

- current_status: conditionally_complete
- current_milestone: Milestone 2
- milestone_state: 16 个 collection/import blocker 已清零；full verify 失败面已下沉到 `56 failed / 28 errors` 的更深行为/集成错误

## Decision log

- 2026-03-29: 先修 collection/import 根因，再回到 full verify；不在本 slice 内处理更深的行为失败
- 2026-03-29: `yaml` 作为 runtime-imported 依赖进入主依赖；`numpy` 仅由 tests 使用，进入 `dev` 依赖
- 2026-03-29: `emotiond.drives` 维持 MVP14 owner，不把 package-level `DriveType` 切回 legacy；legacy compatibility 只通过附加 alias 和局部 test import 收口
- 2026-03-29: legacy `drives.py` 的兼容加载改为单例 helper，避免 `valence_policy`、`interventions`、`emotiond.drives` 各自加载导致 enum/class 身份分裂
- 2026-03-29: `integrations/openclaw` 除 classifier bridge 外补 `schemas/user_affect.schema.json`，把 path contract 一起补齐

## Surprises / discoveries

- `emotiond/drives.py` 与 `emotiond/drives/` 并存，导致 `from emotiond.drives import ...` 在不同年代的测试里语义冲突
- `tests/test_user_affect.py` 依赖的是 `legacy/openclaw` 里的 classifier，但当前仓库没有 repo-root `integrations.openclaw` 兼容包
- 如果 compatibility layer 自己独立 import legacy 模块，会出现相同值但不同 enum/class identity 的运行期失败；这轮已通过 shared loader 收束

## Outcomes / retrospective

- 本轮已证明：
  - 16 个失败面都属于 collection/import 层，而不是新的 health/bootstrap 问题
- 已通过最小 collection gate，430 个相关测试节点可以正常收集
- 兼容子集已通过：`161 passed`
- 最新 `full` rerun 中，`OpenEmotion test suite` 不再报这 16 个 collection/import 错误
- 还没证明：
  - OpenEmotion 全量 pytest 是否可进一步收敛到通过；当前已暴露 `56 failed / 28 errors / 35 skipped` 的更深失败面
- 下一步最小闭环动作：
  - 单开下一条 OpenEmotion pytest stabilization slice，按新失败面分组处理 teardown/tempfile、daemon/live-fixture、MVP10 behavior、documentation/assertion、outcome capture 缺口
