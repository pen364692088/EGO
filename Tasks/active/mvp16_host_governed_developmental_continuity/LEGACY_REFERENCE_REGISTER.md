# WP11 / MVP16 Legacy Reference Register

## Purpose

登记 `WP11` 启动前仓内已有的 `MVP16` / developmental 相关材料。它们可以作为参考输入、迁移线索或对照证据，但不能直接充当新的 `WP11` authority、formal owner 或 formal proof。

## Technical Reference, Not Authority

以下文件可作为技术参考，但与 `Tasks/MVS_task_plan.md + Tasks/MVP16_task_plan.md` 冲突时，不拥有裁决权：

- `OpenEmotion/roadmap/versions/MVP16.spec.yaml`
- `OpenEmotion/docs/mvp16/MVP16_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp16/MVP16_EXIT_CRITERIA.md`

## Reference-only / Input-only Surfaces

以下代码与工具不属于 `WP11` formal owner path：

- `OpenEmotion/emotiond/developmental/*`
- `OpenEmotion/emotiond/developmental_core/*`
- `OpenEmotion/tools/mvp16_daily_check.py`
- `OpenEmotion/tools/mvp16_real_trajectory_sync.py`
- `OpenEmotion/tools/mvp16_anomaly_handler.py`
- `OpenEmotion/tools/persistence_restart_experiments.py`
- `OpenEmotion/tools/causal_intervention_experiments.py`

这些 surfaces 在 `WP11` 中最多只允许承担：

- migration reference
- replay / observation baseline
- candidate-source / input-only helper
- historical comparison

它们不得承担：

- formal owner state
- final developmental continuity semantics
- current-mainline closeout proof

## Historical Admission / Closure Materials

以下任务文档保留为历史审查材料，不是 `WP11` 当前 authority：

- `Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md`
- `Tasks/active/SELF_AWARE_STEP_07A_mvp16_real_data_observation_bootstrap.md`
- `Tasks/active/SELF_AWARE_STEP_08A_real_developmental_evidence_closure.md`
- `Tasks/active/SELF_AWARE_STEP_08B_admission_retry_review.md`

## Current Authority Reminder

- `Tasks/MVS_task_plan.md` 是顶层裁决
- `Tasks/MVP16_task_plan.md` 是 `WP11` phase-detail authority
- `Tasks/active/mvp16_host_governed_developmental_continuity/*` 是当前执行包

All listed legacy code and docs above are `reference-only` or `input-only` for `WP11`.

Current formal owner reminder:

- `OpenEmotion/openemotion/developmental_self/*` is the only formal owner path
- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` is the only current-mainline consumer path
