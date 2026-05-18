# Task Lane Index

> AUTO-GENERATED FILE. Do not edit by hand.
> Derived from `docs/PROGRAM_STATE_UNIFIED.yaml` plus repo-tracked lane rules in `scripts/codex/route_convergence_common.py`.
> This file is a route map, not a second authority source.
> If this file disagrees with `docs/PROGRAM_STATE_UNIFIED.yaml`, trust `docs/PROGRAM_STATE_UNIFIED.yaml` and regenerate route-convergence views.

## Lane Rules

- Exactly one lane may be `active_default`.
- `supporting_active` may help the current default track, but may not replace the execution owner.
- `parked` lanes keep authority/task-package readiness without competing for default execution priority.
- `closed_evidence` records completed/frozen proof surfaces that no longer compete as current implementation tracks.
- `reference_only` is the default fallback for historical, diagnostic, or exploratory directories that are not current route owners.

## Lane Counts

| lane | count |
|---|---:|
| `active_default` | 1 |
| `supporting_active` | 5 |
| `parked` | 1 |
| `closed_evidence` | 17 |
| `reference_only` | 55 |

## Active Default

| entry | kind | workstream | paths | why |
|---|---|---|---|---|
| EgoOperator Human Operator Trial v2 | `codex_task` | `ego_operator_first_transition` | `docs/codex/tasks/ego-operator-human-operator-trial-v2/` | Current EgoOperator human-observation gate; records whether the operator-first runtime is actually usable in continuous Chinese operator work. Current workstream status: `human_operator_trial_v2_protocol_ready__real_provider_recheck_pending`. |

## Supporting Active

| entry | kind | workstream | paths | why |
|---|---|---|---|---|
| Provider/Runtime/OpenEmotion E2E Gate | `codex_task` | `provider_runtime_openemotion_e2e_gate` | `docs/codex/tasks/provider-runtime-openemotion-e2e-gate/` | Real-channel supporting gate for the current mainline; supports Stage 1 truth but is not a competing route. Current workstream status: `pass`. |
| Repo Cleanup Route Convergence | `codex_task` | `repo_cleanup_route_convergence` | `docs/codex/tasks/repo-cleanup-route-convergence/` | Supporting cleanup lane for route index, hygiene gate, and Stage 1 evidence convergence; must not replace the active default track. Current workstream status: `supporting_active`. |
| Repo Mainline Clarity v1 | `codex_task` | n/a | `docs/codex/tasks/repo-mainline-clarity-v1/` | Supporting repo-view slice for mainline onboarding, surface-map clarity, and staged operational-exhaust hygiene; must not replace the active default track. |
| Telegram Subject Mainline Audit | `codex_task` | `live_subject_ingress_observation` | `docs/codex/tasks/telegram-subject-mainline-audit/` | Supporting audit slice for Stage 1 subject-ingress accounting and live evidence discipline. Current workstream status: `partial`. |
| Unified Host Contract Correctness | `codex_task` | `unified_host_contract_correctness` | `docs/codex/tasks/unified-host-contract-correctness/` | Frozen predecessor tranche that still supports Stage 1 equivalent-entry reasoning. Current workstream status: `pass`. |

## Parked

| entry | kind | workstream | paths | why |
|---|---|---|---|---|
| WP17 / MVP22 Authority Refs | `authority_refs` | `wp17_bounded_continuity_lane` | `Tasks/MVP22_task_plan.md`<br>`Tasks/active/mvp22_long_horizon_self_continuity/STATUS.md` | Authority-frozen bounded continuity lane; preserved but parked behind the active default track. |

## Closed Evidence

| entry | kind | workstream | paths | why |
|---|---|---|---|---|
| Active-Inference Mainline Activation | `codex_task` | `active_inference_mainline_activation` | `docs/codex/tasks/active-inference-mainline-activation/` | Frozen dashboard-only bounded predecessor tranche; preserve as closed evidence, not the active default route. Current workstream status: `closed_evidence__dashboard_stage1_3_frozen`. |
| AI Self-Awareness Minimal Framework | `codex_task` | `ai_self_awareness_research` | `docs/codex/tasks/ai-self-awareness-minimal-framework/` | Selection closeout and MVS demotion authority live here; this is closed research evidence, not the current runtime owner. Current workstream status: `selection_closed_handoff`. |
| Ego Mainline Demotion v1 | `codex_task` | `ego_operator_first_transition` | `docs/codex/tasks/ego-mainline-demotion-v1/` | Previous operator-first transition record; superseded by the EgoOperator rename/docs-safety task while preserving legacy demotion evidence. Current workstream status: `human_operator_trial_v2_protocol_ready__real_provider_recheck_pending`. |
| EgoOperator Rename + Docs Safety v1 | `codex_task` | `ego_operator_first_transition` | `docs/codex/tasks/ego-operator-rename-docs-safety-v1/` | Previous EgoOperator naming and reader-safety transition record; superseded by the human operator trial v2 task as the active observation owner. Current workstream status: `human_operator_trial_v2_protocol_ready__real_provider_recheck_pending`. |
| MVS-Aligned Compact Closed Evidence | `authority_refs` | n/a | `docs/codex/tasks/ai-self-awareness-minimal-framework/SELECTION_CLOSEOUT.md`<br>`docs/codex/tasks/ai-self-awareness-minimal-framework/MVS_ALIGNED_COMPACT_PROTOTYPE_DESIGN.md` | Closed evidence only; selection closeout keeps it out of the default implementation track. |
| Repo Authority Cleanup | `codex_task` | `repo_authority_cleanup` | `docs/codex/tasks/repo-authority-cleanup/` | Repo/integration boundary cleanup is closed out and no longer competes for current execution ownership. Current workstream status: `closeout-complete`. |
| Runtime Proximal Basic Standard Admission Planning | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-basic-standard-admission-planning/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Basic Standard Admission Runner Implementation | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-basic-standard-admission-runner-implementation/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Host Consumption Causal Planning | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-host-consumption-causal-planning/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Host Consumption Runner Implementation | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-host-consumption-runner-implementation/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Low Cue Ownership Planning | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-low-cue-ownership-planning/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Low Cue Ownership Runner Implementation | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-low-cue-ownership-runner-implementation/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Post Stronger Admission Planning | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-post-stronger-admission-planning/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Post Stronger Selection Coherence Runner Implementation | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-post-stronger-selection-coherence-runner-implementation/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Stronger Admission Planning | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-stronger-admission-planning/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Runtime Proximal Stronger Admission Runner Implementation | `codex_task` | n/a | `docs/codex/tasks/runtime-proximal-stronger-admission-runner-implementation/` | Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders. |
| Subject System v1 Governed Proactivity | `codex_task` | `subject_system_v1_governed_proactivity` | `docs/codex/tasks/subject-system-v1-governed-proactivity/` | Legacy pre-EgoOperator governed-proactivity evidence; preserved for reference and fallback, not the active default route. Current workstream status: `legacy_reference__pre_ego_operator_evidence_preserved`. |

## Reference Only

| entry | kind | workstream | paths | why |
|---|---|---|---|---|
| Autopilot Doctor Auth Check | `codex_task` | n/a | `docs/codex/tasks/autopilot-doctor-auth-check/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Autopilot Ego Reconnect Smoke | `codex_task` | n/a | `docs/codex/tasks/autopilot-ego-reconnect-smoke/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Autopilot Smoke | `codex_task` | n/a | `docs/codex/tasks/autopilot-smoke/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Codex Harness Hardening | `codex_task` | n/a | `docs/codex/tasks/codex-harness-hardening/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| E4 Shadow H1 Formal Mainline Sampling | `codex_task` | n/a | `docs/codex/tasks/e4-shadow-h1-formal-mainline-sampling/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Ego Handmade Human Operator Trial V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-human-operator-trial-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Ego Handmade Operator Comparison V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-operator-comparison-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Ego Handmade Operator Cut V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-operator-cut-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Ego Handmade Operator Permission Gates V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-operator-permission-gates-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Ego Handmade Operator Runtime Contract V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-operator-runtime-contract-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Ego Handmade Real Use Memory Gate V1 | `codex_task` | n/a | `docs/codex/tasks/ego-handmade-real-use-memory-gate-v1/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Egocore Pytest Suite Stabilization | `codex_task` | n/a | `docs/codex/tasks/egocore-pytest-suite-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| H1 Canonical Promotion Prep | `codex_task` | n/a | `docs/codex/tasks/h1-canonical-promotion-prep/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| H1 Canonical Shadow Patch | `codex_task` | n/a | `docs/codex/tasks/h1-canonical-shadow-patch/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| H1 Preflight Same Surface Unblock | `codex_task` | n/a | `docs/codex/tasks/h1-preflight-same-surface-unblock/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Identify Public Causal Driver For Mvs Trial 2 | `codex_task` | n/a | `docs/codex/tasks/identify-public-causal-driver-for-mvs-trial-2/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Interface Layer Consolidation | `codex_task` | n/a | `docs/codex/tasks/interface-layer-consolidation/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Live Chat Subjective Variability | `codex_task` | n/a | `docs/codex/tasks/live-chat-subjective-variability/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Llm In Loop Whole Chain Sampling | `codex_task` | n/a | `docs/codex/tasks/llm-in-loop-whole-chain-sampling/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Mandatory Subject Ingress All Turns | `codex_task` | n/a | `docs/codex/tasks/mandatory-subject-ingress-all-turns/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Mvs H1 External Eval Corpus | `codex_task` | n/a | `docs/codex/tasks/mvs-h1-external-eval-corpus/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Mvs H1 External Raw Extraction Replay | `codex_task` | n/a | `docs/codex/tasks/mvs-h1-external-raw-extraction-replay/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Mvs H1 External Replay Execution | `codex_task` | n/a | `docs/codex/tasks/mvs-h1-external-replay-execution/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Mvs V1 + Controlled Proactivity Sandbox | `codex_task` | n/a | `docs/codex/tasks/MVS v1 + Controlled Proactivity Sandbox/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Openemotion Candidate Hash Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-candidate-hash-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Daemon Lifecycle Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-daemon-lifecycle-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Env Health Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-env-health-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Live Integration Fixture Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-live-integration-fixture-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Mvp10 Replay Determinism Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-mvp10-replay-determinism-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Mvp11 Replay Tempfile Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-mvp11-replay-tempfile-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Outcome Capture Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-outcome-capture-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Readme Contract Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-readme-contract-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion Test Collection Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-test-collection-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Openemotion V6K2 Whitelist Alert Stabilization | `codex_task` | n/a | `docs/codex/tasks/openemotion-v6k2-whitelist-alert-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Proto Self Seed Host Evidence Stabilization | `codex_task` | n/a | `docs/codex/tasks/proto-self-seed-host-evidence-stabilization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Proto Self Seed Real Rollout | `codex_task` | n/a | `docs/codex/tasks/proto-self-seed-real-rollout/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Simulated Shadow H1 Mainline Sampling | `codex_task` | n/a | `docs/codex/tasks/simulated-shadow-h1-mainline-sampling/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
| Subjective Loop V1 Product Cut | `codex_task` | n/a | `docs/codex/tasks/subjective-loop-v1-product-cut/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 0 Operator Observability | `codex_task` | n/a | `docs/codex/tasks/v7-stage-0-operator-observability/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 1 Deterministic Agency Kernel | `codex_task` | n/a | `docs/codex/tasks/v7-stage-1-deterministic-agency-kernel/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 10 Permissioned Tool Desktop Sandbox | `codex_task` | n/a | `docs/codex/tasks/v7-stage-10-permissioned-tool-desktop-sandbox/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 2 Experience Memory | `codex_task` | n/a | `docs/codex/tasks/v7-stage-2-experience-memory/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 3 Behavior Option Framework | `codex_task` | n/a | `docs/codex/tasks/v7-stage-3-behavior-option-framework/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 4 Relational Companion Layer | `codex_task` | n/a | `docs/codex/tasks/v7-stage-4-relational-companion-layer/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 45 Continuity Runtime Scaffold | `codex_task` | n/a | `docs/codex/tasks/v7-stage-45-continuity-runtime-scaffold/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 46 Blackbox Stage Gate Harness | `codex_task` | n/a | `docs/codex/tasks/v7-stage-46-blackbox-stage-gate-harness/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 5 Computer Skill Sandbox | `codex_task` | n/a | `docs/codex/tasks/v7-stage-5-computer-skill-sandbox/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 6 Runtime Shadow Bridge | `codex_task` | n/a | `docs/codex/tasks/v7-stage-6-runtime-shadow-bridge/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 7 Permissioned Runtime Action | `codex_task` | n/a | `docs/codex/tasks/v7-stage-7-permissioned-runtime-action/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 8 Live Shadow Human Trial | `codex_task` | n/a | `docs/codex/tasks/v7-stage-8-live-shadow-human-trial/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 81 Llm Semantic Expression Shadow Admission | `codex_task` | n/a | `docs/codex/tasks/v7-stage-81-llm-semantic-expression-shadow-admission/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 82 Live Llm Answer Draft Admission | `codex_task` | n/a | `docs/codex/tasks/v7-stage-82-live-llm-answer-draft-admission/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 83 Context Aware Llm Answer Followup | `codex_task` | n/a | `docs/codex/tasks/v7-stage-83-context-aware-llm-answer-followup/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| V7 Stage 9 Proposal Only Runtime Integration | `codex_task` | n/a | `docs/codex/tasks/v7-stage-9-proposal-only-runtime-integration/` | No current authority promotes this task as an active or parked route; keep it as reference-only by default. |
| Wp12 Maintenance Institutionalization | `codex_task` | n/a | `docs/codex/tasks/wp12-maintenance-institutionalization/` | Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only. |
