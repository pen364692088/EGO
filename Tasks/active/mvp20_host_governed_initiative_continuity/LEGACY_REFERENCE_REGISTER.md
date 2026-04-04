# WP15 / MVP20 Legacy Reference Register

## Purpose

登记 `WP15` 启动前仓内已有的 proactive / initiative substrate、upstream authority 与 roadmap 材料。它们可以作为参考输入、迁移线索或对照证据，但不能直接充当新的 `WP15` authority、formal owner、或 formal proof。

## Technical Reference, Not Authority

以下文件可作为 technical reference，但与 `Tasks/MVS_task_plan.md + Tasks/MVP20_task_plan.md` 冲突时，不拥有 `WP15` 裁决权：

- `Tasks/MVP12_task_plan.md`
- `Tasks/MVP13_task_plan.md`
- `Tasks/MVP14_task_plan.md`
- `Tasks/MVP15_task_plan.md`
- `Tasks/MVP16_task_plan.md`
- `Tasks/MVP17_task_plan.md`
- `Tasks/MVP18_task_plan.md`
- `Tasks/MVP19_task_plan.md`
- `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
- `OpenEmotion/roadmap/VersionRoadmap.md`

这些历史材料在 `WP15` 中最多只能承担：

- technical reference
- historical comparison
- migration clue
- reference-only or host-substrate boundary reminder

## Host Proactive Substrate, Reference-only To WP15 Semantics

以下 surfaces 仍是宿主 proactive execution substrate；`WP15` 只能把它们当作 host-governed execution reference 或 future bridge surface，不能把它们升格为 `WP15` semantic owner：

- `EgoCore/app/runtime_v2/initiative_arbiter.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/app/runtime_v2/initiative_scheduler.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/app/runtime_v2/proactive_delivery.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/app/runtime_v2/proactive_outbox.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/app/runtime_v2/proactive_outbox_drain.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/app/runtime_v2/proactive_telegram_policy.py`
  - classification: `host_execution_substrate_reference_only`
- `EgoCore/tools/run_mvp12_proactive_followup.py`
- `EgoCore/tools/run_mvp12_idle_scheduler.py`
- `EgoCore/tools/run_mvp12_controlled_delivery.py`
- `EgoCore/tools/run_mvp12_proactive_outbox.py`
- `EgoCore/tools/run_mvp12_proactive_outbox_drain.py`
- `EgoCore/tools/run_mvp12_telegram_proactive_transport.py`
- `EgoCore/tools/run_mvp12_host_governed_proactive_telegram_cycle.py`

Plain-language guard:

- WP15 formal owner state must remain exclusive to `OpenEmotion/openemotion/initiative_self/*`
- host proactive execution substrate is not a fallback semantic owner
- host proactive evidence is not initiative proof until `WP15` current-mainline wiring exists

## Upstream Authority, Read-only To WP15

以下 owner surfaces 仍是各自 upstream phase 的 formal owner；`WP15` 只能读取它们的冻结 outputs：

- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/openemotion/endogenous_drives/*`
- `OpenEmotion/openemotion/reflective_self/*`
- `OpenEmotion/openemotion/developmental_self/*`
- `OpenEmotion/openemotion/social_self/*`
- `OpenEmotion/openemotion/embodied_self/*`
- `OpenEmotion/openemotion/selfhood_integration/*`

这些 surfaces 在 `WP15` 中最多只允许承担：

- frozen read surface
- bounded proposal input
- historical comparison
- replay / observation baseline
- no-second-truth boundary reference

它们不得承担：

- `WP15` formal owner state
- `WP15` fallback owner
- `WP15` current-mainline closeout proof
- `WP15` authority override

## Current Authority Reminder

- `Tasks/MVS_task_plan.md` 是顶层裁决
- `Tasks/MVP20_task_plan.md` 是 `WP15` phase-detail authority
- `Tasks/active/mvp20_host_governed_initiative_continuity/*` 是当前执行包

Current formal owner reminder:

- `OpenEmotion/openemotion/initiative_self/*` is the only formal owner target
- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` is the only current-mainline target

## No-Second-Truth Reminder

- `WP15` 不能把 `WP7` proactive substrate 重新解释成自己的 owner
- `WP15` 不能把 roadmap、旧执行报告、或 proactive transport evidence 升格成 current-runtime authority
- 后续 no-second-truth verifier 应以 `OpenEmotion/tools/verify_mvp20_mainline_wiring.py` 为准
