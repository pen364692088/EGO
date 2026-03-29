# OpenEmotion Test Collection Stabilization - STATUS

## Current milestone

- name: Milestone 2 - Repair legacy drives collection compatibility
- owner: Codex
- state: completed

## Current state

- current_layer: implementation / verification
- main_chain_status: OpenEmotion full verify 已越过 collection/import 层；当前失败面已下沉到更深的行为、daemon/live-fixture 与 teardown 问题
- completion_class: conditionally_complete

## Completed work

- 已建立独立 long-run task slice：`docs/codex/tasks/openemotion-test-collection-stabilization/`
- 已确认 16 个失败面分为：
  - 依赖/导入缺口：`yaml`、`numpy`、`integrations.openclaw`
  - legacy drives 兼容缺口：`DriveLevel`、`DriveCandidate`、`Drives`、`drives_from_valence`
- `OpenEmotion/pyproject.toml` 已补 `PyYAML` 与 `numpy`
- 已新增 `OpenEmotion/integrations/openclaw/classifiers/user_affect.py` 兼容桥
- 已新增 `OpenEmotion/integrations/openclaw/schemas/user_affect.schema.json` 兼容 schema
- `emotiond.drives` 已补 legacy alias exports
- legacy `drives.py` 已通过 `emotiond/_legacy_drives.py` 单例 helper 共享给 `emotiond.drives`、`valence_policy`、`science.interventions`
- 三个 MVP10 测试已切到显式 legacy `DriveType` alias，避免破坏 MVP14 package owner
- 针对原 16 个失败源的 `--collect-only` 已通过，`430 tests collected`
- 兼容回归子集已通过，`161 passed`

## Last validation results

- mode: targeted collection gate + full verify rerun
- result: slice goal reached; full verify still failed, but no longer at collection/import layer
- summary:
  - compatibility subset:
    - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/mvp10/test_drives_generation.py OpenEmotion/tests/mvp10/test_intervention_freeze_valence.py OpenEmotion/tests/mvp10/test_valence_policy_chain.py OpenEmotion/tests/mvp14/test_drive_infra.py OpenEmotion/tests/mvp14/test_drive_integration.py OpenEmotion/tests/mvp14/test_e2e_gate_b.py OpenEmotion/tests/test_user_affect.py -q`
    - `161 passed, 2 warnings in 0.43s`
  - targeted gate:
    - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest ... --collect-only -q`
    - `430 tests collected in 0.84s`
  - `python3 scripts/codex/verify_repo.py --mode full`
    - `EgoCore pytest suite`: success
    - `OpenEmotion full typecheck`: success
    - `OpenEmotion testbot PR subset`: success
    - `OpenEmotion test suite`: exit `1`
    - latest OpenEmotion failure surface: `56 failed, 4483 passed, 35 skipped, 28 errors`

## Decisions made

- 先修 import surface，再修 legacy drives compatibility
- 不回退上一 slice 的 verifier runtime/bootstrap 逻辑
- `yaml` 进主依赖，`numpy` 进 `dev` 依赖
- `emotiond.drives` 保持 MVP14 owner，不把 package-level `DriveType` 切回 legacy
- compatibility layer 统一通过 shared legacy loader 导出，避免 enum/class identity 分裂
- `integrations.openclaw` 的兼容目标不仅是 import surface，也包括测试直接依赖的 schema path

## Open risks

- 当前已暴露新的真实失败面，后续 slice 需要重新分组而不是继续把它们当作 import 问题处理
- Windows Python runtime 下仍有 tempfile teardown / daemon lifecycle 类错误，可能和文件句柄释放时序有关

## Next step

- 单开下一条 OpenEmotion pytest stabilization slice，优先处理：
  - `tests/mvp11/test_replay_backward_compat.py` 的 tempfile/handle teardown errors
  - `tests/test_daemon_lifecycle.py` 与 `tests/test_live_integration_fixture.py` 的 live daemon failures
  - `tests/test_outcome_capture_integration.py` 的 module/endpoint 缺口
  - README / documentation assertions 与若干 replay/self-report failures

## Commands run / evidence

- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/verify_repo.py --mode full`
- `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest tests/ -q`
- `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/mvp10/test_drives_generation.py OpenEmotion/tests/mvp10/test_intervention_freeze_valence.py OpenEmotion/tests/mvp10/test_valence_policy_chain.py OpenEmotion/tests/mvp14/test_drive_infra.py OpenEmotion/tests/mvp14/test_drive_integration.py OpenEmotion/tests/mvp14/test_e2e_gate_b.py OpenEmotion/tests/test_user_affect.py -q`
- `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego\OpenEmotion && .venv\Scripts\python.exe -m pip install --no-build-isolation -e .[dev]"`
- `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/mvp10/test_drives_generation.py OpenEmotion/tests/mvp10/test_intervention_freeze_valence.py OpenEmotion/tests/mvp10/test_valence_policy_chain.py OpenEmotion/tests/test_auto_tune_v0.py OpenEmotion/tests/test_auto_tune_v0_1.py OpenEmotion/tests/test_auto_tune_v0_2.py OpenEmotion/tests/test_auto_tune_v0_3.py OpenEmotion/tests/test_causal_evidence.py OpenEmotion/tests/test_e2e_replay.py OpenEmotion/tests/test_eval_suite_v2_1.py OpenEmotion/tests/test_eval_suite_v2_2.py OpenEmotion/tests/test_eval_suite_v2_3.py OpenEmotion/tests/test_mvp4_eval.py OpenEmotion/tests/test_self_report_interpreter.py OpenEmotion/tests/test_us641_knob_registry.py OpenEmotion/tests/test_user_affect.py --collect-only -q`
- authority refs:
  - `OpenEmotion/pyproject.toml`
  - `OpenEmotion/emotiond/drives/__init__.py`
  - `OpenEmotion/emotiond/drives.py`
  - `OpenEmotion/tests/mvp10/test_drives_generation.py`
  - `OpenEmotion/tests/test_user_affect.py`
