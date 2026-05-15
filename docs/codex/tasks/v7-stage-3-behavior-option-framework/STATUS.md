# v7 Stage 3 - Behavior Option Framework - STATUS

## Current milestone

- name: Canonical Event / Plan Contract
- owner: Codex
- state: local_pass
- type: implementation

## Current state

- activation: active
- current_layer: ego_desktop_lab lab-only behavior option framework
- main_chain_status: not connected to runtime
- completion_class: reviewer_operator_acceptance_pass
- candidate_vs_proof: bounded_lab_proof

## Completed work

- Task package created.
- Stage 2 / 2.1 unlock gate passed with operator-readable chat-corpus acceptance cases.
- Milestone 1 implemented a lab-only registered behavior option contract over existing intentions without changing policy ranking, runtime authority, tool use, scheduler, or gate ownership.
- Behavior options now expose registered option id, option type, affordance, allowed actions, expected effect, risk, cost, permission class, rollback note, proposal-only status, gate status, and no-action boundary.
- Adversarial probes found and closed one registry-contract gap: a mismatched `affordance + proposed_action` pair such as `continue_goal + file_delete` is now filtered before it can become a registered behavior option.
- DecisionView formatting now exposes debug refs, including `recomputed_decision=false`, so the operator report remains read-only.
- Milestone 2 implemented a lab-only kernel selection restriction: `selected_intention` remains the policy trace, but operator-facing `selected_behavior_option` can only come from a registered behavior option.
- Kernel results now expose `selection_restriction`, including candidate/behavior option relationship, filtered candidate ids, and localization for `unregistered_affordance` or `action_not_allowed_for_affordance`.
- Reviewer/operator acceptance passed: the generated operator report exposes selected intention, selected behavior option, selection restriction, gate, no-action boundary, debug refs with `recomputed_decision=false`, and claim ceiling in one read-only surface.
- Stage 3.1 added a lab-only canonical contract for `AgencyEvent`, `PerceptionFrame`, and thin `BehaviorPlan`, so future companion/perception work has to enter through event/perception frames and registered behavior options rather than ad hoc natural-language state mutation.
- Stage 2.1 chat-corpus parsing now emits `AgencyEvent -> PerceptionFrame`; negated repair feedback such as `不要修复计划，也不用重新拆目标` no longer creates a negative continue experience.
- `AgencyDecisionView` now renders event, perception, and behavior-plan sections read-only, without recomputing selection or gate decisions.

## Last experiment

- question: can Stage 3 expose canonical input/perception/plan surfaces before Stage 4 adds relational companion behavior?
- framing: add lab-only contracts and verify stable chat-corpus perception, negation control, registered option plan wrapping, unregistered plan refusal, and DecisionView readability.
- result: local_pass
- evidence_upgraded: no

## What was learned

- Option work depends on stable experience/kernel scoring.
- Stage 3 must not continue Stage 2 parser/report tuning unless the operator gate regresses.
- The first Stage 3 cut must make option contracts auditable without duplicating policy scoring.
- Unregistered affordances can be filtered at the behavior-option layer without mutating kernel policy ranking.
- Dangerous proposed actions remain blocked because permission class and gate status are derived from the existing deterministic gate table.
- Registered affordances also require an allowed proposed action, so malformed action-affordance pairs cannot inherit a misleading option contract.
- Kernel selection can report a policy-selected intention that has no registered behavior option without silently treating it as executable or selected.
- `candidate_options` remain raw policy trace while `behavior_options` are registered/filtered; `selection_restriction` now makes that relationship explicit.
- Operator readability required one observation-only closeout: `AgencyDecisionView` now renders a distinct `Selected Intention` section and full selected behavior option JSON.
- Event/perception/plan contract should exist before Stage 4, otherwise relation hints or expression strategies could become an untracked side entrance into kernel state.
- A deterministic negation guard is required even for lab chat-corpus probes; keyword-only feedback parsing is too weak for operator acceptance.

## What was ruled out

- LLM planner in this stage.
- Tool use, scheduler, runtime bridge, and permission expansion in this stage.

## Next framing

Stage 3.1 canonical event/plan contract is local-passing. Next decision is whether to plan Stage 4 (`Relational Companion Layer`) against these contracts; Stage 4 is not automatically unlocked by this pass.

## Last validation results

- mode: Stage 3.1 canonical event/plan contract
- result: pass
- summary: New canonical contract tests, Stage 1/2/3/root-cause regression tests, full lab tests, and scoped diff check passed locally.

## Decisions made

- Stage 3 locked until Stage 2 passes.
- Stage 3 activated after the Stage 2.1 chat-corpus operator acceptance gate passed.
- First implementation milestone is registry contract only; do not implement LLM planner, tool use, scheduler, runtime bridge, or permission expansion.
- Stage 3 Milestone 1 local pass does not unlock Stage 4 and does not prove planner autonomy, tool autonomy, runtime efficacy, live user benefit, consciousness, or alive status.
- Stage 3 Milestone 2 local pass still does not unlock Stage 4 automatically; reviewer/operator acceptance is the next gate.
- Stage 3 reviewer/operator acceptance passes the Stage 3 exit gate but still does not prove Stage 4 relational behavior or any runtime/live benefit claim.
- Stage 3.1 local pass fixes canonical event/perception/plan surfaces before Stage 4, but still does not prove relational behavior, planner autonomy, tool autonomy, runtime efficacy, live user benefit, consciousness, or alive status.

## Open risks

- Registry must remain non-scoring metadata and must not drift into a second policy source; `allowed_actions` is a contract-shape guard, not a second gate.
- Selection restriction remains lab-only. It does not change the underlying policy selection formula and does not authorize tool/runtime action.
- Future planner work must consume registered options and cannot write memory/state or bypass gate directly.
- Future relational companion work must emit event/perception inputs and surface plans; it cannot directly mutate kernel state, experience memory, gate decisions, or canonical selected behavior.

## Next step

Decide whether to plan Stage 4 (`Relational Companion Layer`) against `AgencyEvent / PerceptionFrame / BehaviorPlan`. Do not implement Stage 4 without a separate task packet and acceptance plan.

## Commands run / evidence

- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_negative.md --experience-chat-case-report /tmp/ego_stage2_gate_negative_report.md`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_no_feedback.md --experience-chat-case-report /tmp/ego_stage2_gate_no_feedback_report.md`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_unrelated.md --experience-chat-case-report /tmp/ego_stage2_gate_unrelated_report.md`
- `python3 -m py_compile ego_desktop_lab/behavior_options.py ego_desktop_lab/agency_kernel.py ego_desktop_lab/agency_decision_view.py ego_desktop_lab/tests/test_behavior_options_v7.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_behavior_options_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py ego_desktop_lab/tests/test_experience_memory_v7.py ego_desktop_lab/tests/test_experience_chat_case_v7_2.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_behavior_options_v7.py ego_desktop_lab/tests/test_dual_track_lab_spine_v7.py ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `python3 -m py_compile ego_desktop_lab/agency_kernel.py ego_desktop_lab/behavior_options.py ego_desktop_lab/agency_decision_view.py ego_desktop_lab/tests/test_behavior_options_v7.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_behavior_options_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py ego_desktop_lab/tests/test_experience_memory_v7.py ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
- `python3 - <<'PY' ... build_v7_agency_kernel_shell_report(Path("/tmp/ego_stage3_operator_acceptance.md")) ... PY`
- `rg -n "Selected Option|Selection Restriction|Selected Intention|selected_intention|registered_option_id|allowed_actions|restriction_active|gate_status|no_action_executed|recomputed_decision|Claim Ceiling" /tmp/ego_stage3_operator_acceptance.md`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY' ... restricted-path acceptance probe ... PY`
- `python3 -m py_compile ego_desktop_lab/agency_contracts.py ego_desktop_lab/agency_kernel.py ego_desktop_lab/agency_decision_view.py ego_desktop_lab/shell.py ego_desktop_lab/tests/test_canonical_event_plan_contract_v7_31.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_canonical_event_plan_contract_v7_31.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_behavior_options_v7.py ego_desktop_lab/tests/test_experience_chat_case_v7_2.py ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py ego_desktop_lab/tests/test_experience_memory_v7.py ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage31_negated_case.md --experience-chat-case-report /tmp/ego_stage31_negated_case_report.md`
- `rg -n "feedback_class|experience_applied|selected_changed|ranking_changed|Agency Event|Perception Frame|no_action_executed" /tmp/ego_stage31_negated_case_report.md`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
