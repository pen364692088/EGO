# WP9 / MVP14 Drive Authority Source

## Top-Level Authority

- `Tasks/MVS_task_plan.md`

## Phase-Detail Authority

- `Tasks/MVP14_task_plan.md`

## Version / Scope Authority

- `OpenEmotion/roadmap/versions/MVP14.spec.yaml`

## Technical Reference Inputs

- `OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp14/ENDOGENOUS_DRIVES_ARCHITECTURE.md`
- `OpenEmotion/docs/mvp14/DRIVE_STATE_SCHEMA.md`
- `OpenEmotion/docs/mvp14/DRIVE_GOVERNANCE_AND_PRIORITY_POLICY.md`
- `OpenEmotion/docs/mvp14/SELF_MAINTENANCE_RUNTIME.md`

## Formal Owner Target

- `OpenEmotion/emotiond/drives/*`

## Bounded Compatibility Surface

- `OpenEmotion/emotiond/drive_adapter.py`

## Measurement / Reference Surfaces

- `OpenEmotion/emotiond/drive_homeostasis.py`
- `OpenEmotion/emotiond/homeostasis.py`

## Authority Resolution Rules

- 若 `Tasks/MVS_task_plan.md` 与任何下级文档冲突，以 `Tasks/MVS_task_plan.md` 为准
- 若 `Tasks/MVP14_task_plan.md` 与技术参考冲突，以 `Tasks/MVP14_task_plan.md` 为准
- `drive_adapter.py`、`drive_homeostasis.py`、`homeostasis.py` 的实现现状不自动改变 formal owner 判断
- 未经新的 authority freeze，不得把旧 `SELF_AWARE_STEP_05*` 任务单重新升格为正式裁决源
