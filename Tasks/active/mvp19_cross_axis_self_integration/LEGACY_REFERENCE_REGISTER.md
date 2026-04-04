# WP14 / MVP19 Legacy Reference Register

## Purpose

登记 `WP14` 启动前仓内已有的 cross-axis integration、upstream authority 与 roadmap 材料。它们可以作为参考输入、迁移线索或对照证据，但不能直接充当新的 `WP14` authority、formal owner、或 formal proof。

## Technical Reference, Not Authority

以下文件可作为 technical reference，但与 `Tasks/MVS_task_plan.md + Tasks/MVP19_task_plan.md` 冲突时，不拥有 `WP14` 裁决权：

- `Tasks/MVP13_task_plan.md`
- `Tasks/MVP14_task_plan.md`
- `Tasks/MVP15_task_plan.md`
- `Tasks/MVP16_task_plan.md`
- `Tasks/MVP17_task_plan.md`
- `Tasks/MVP18_task_plan.md`
- `OpenEmotion/roadmap/VersionRoadmap.md`
- `Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md`
- `Tasks/active/SELF_AWARE_STEP_08_admission_review.md`
- `Tasks/active/SELF_AWARE_STEP_08A_real_developmental_evidence_closure.md`
- `Tasks/active/SELF_AWARE_STEP_08B_admission_retry_review.md`
- `OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md`
- `OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`

这些历史材料在 `WP14` 中最多只能承担：

- technical reference
- historical comparison
- migration clue
- reference-only or input-only boundary reminder

它们不得承担：

- `WP14` formal owner
- `WP14` current-mainline proof
- `WP14` authority override
- `WP14` fallback arbitration source

## Upstream Authority, Read-only To WP14

以下 owner surfaces 仍是各自 upstream phase 的 formal owner；`WP14` 只能读取它们的冻结 outputs，不能把它们降格成 fallback，也不能把它们升格成 `WP14` 自身 formal owner：

- `OpenEmotion/openemotion/self_model/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.self_model_context` and `WP8` confidence / identity / known-unknowns constraints
- `OpenEmotion/openemotion/endogenous_drives/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.endogenous_drive_context`, `candidate_bias_terms`, `priority_snapshot`, and `self_maintenance_candidate`
- `OpenEmotion/openemotion/reflective_self/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.reflective_self_context`, `revision_proposal_candidates`, `confidence_adjustment_hints`, and `maintenance_priority_hints`
- `OpenEmotion/openemotion/developmental_self/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.developmental_self_context`, `developmental_proposal_candidates`, `developmental_priority_hints`, and `developmental_continuity_snapshot`
- `OpenEmotion/openemotion/social_self/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.social_self_context`, `relation_update_candidates`, `repair_proposal_candidates`, `social_policy_hints`, and `trust_commitment_snapshot`
- `OpenEmotion/openemotion/embodied_self/*`
  - classification: `upstream_authority_read_only`
  - allowed role: provide `runtime_summary.embodied_self_context`, `consequence_update_candidates`, `repair_or_stabilize_proposal_candidates`, `embodied_policy_hints`, and `resource_boundary_snapshot`

这些 surfaces 在 `WP14` 中最多只允许承担：

- frozen read surface
- bounded proposal input
- historical comparison
- replay / observation baseline
- no-second-truth boundary reference

它们不得承担：

- `WP14` formal owner state
- `WP14` fallback owner
- `WP14` current-mainline closeout proof
- `WP14` authority override

Plain-language guard:

- WP14 formal owner state must remain exclusive to `OpenEmotion/openemotion/selfhood_integration/*`
- WP14 fallback owner is forbidden for every upstream authority surface

## Current Authority Reminder

- `Tasks/MVS_task_plan.md` 是顶层裁决
- `Tasks/MVP19_task_plan.md` 是 `WP14` phase-detail authority
- `Tasks/active/mvp19_cross_axis_self_integration/*` 是当前执行包

Current formal owner reminder:

- `OpenEmotion/openemotion/selfhood_integration/*` is the only formal owner target
- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` is the only current-mainline target

## No-Second-Truth Reminder

- `WP14` 只能整合 upstream proposals，不能把 upstream owner packages 重新解释成自己的 owner
- `WP14` 不能把 self-aware 历史 step 文档、roadmap、或旧执行报告升格成 current-runtime authority
- 当前 no-second-truth verifier 应以 `OpenEmotion/tools/verify_mvp19_mainline_wiring.py` 为准
