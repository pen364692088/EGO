# v7 Stage 4 - Relational Companion Layer - STATUS

## Current milestone

- name: Daily Chat Companion Surface Eval
- owner: Codex
- state: operator_accepted
- type: implementation

## Current state

- activation: active
- current_layer: ego_desktop_lab lab-only relational planning
- main_chain_status: not connected to runtime
- completion_class: operator_acceptance_pass
- candidate_vs_proof: bounded_lab_proof

## Completed work

- Task package created.
- Stage 3.1 local pass supplied the canonical `AgencyEvent / PerceptionFrame / BehaviorPlan` boundary before Stage 4 began.
- Milestone 1 added a lab-only relational companion surface for common daily chat entry classes: greeting, agent-view requests, daily small talk, emotional venting, decision help, project coordination, capability questions, system identity / local system info, sensitive env/file/tool-style requests, vague one-word queries, correction feedback, preference signals, humor, disagreement, and permission requests.
- The shell command layer now routes ordinary daily chat and relational surface inputs to `relational_companion_surface` instead of letting them fall through to generic ambiguous concern, while preserving existing read-only local system info handling.
- A full lab regression found and closed one mechanism-critical routing issue: explicit outcome failure / repair feedback such as `计划执行了，但是结果没有改善，需要重新规划。` must fall through to the existing repair DecisionView path instead of being captured by the relational surface.
- A 200-row `daily_chat_corpus_v7.jsonl` corpus was added as operator/eval data, split into 70 dev rows and 130 held-out rows.
- The daily-chat eval report records intent accuracy, heldout accuracy, safety boundary pass rate, no-action pass rate, unsafe claim count, sensitive failure count, ambiguous concern count, failed rows, and claim ceiling.
- Operator acceptance passed with real shell phrases for greeting, agent-view request, vague system reference, local system info, sensitive env request, and legacy repair/outcome feedback.

## Last experiment

- question: can an operator verify from shell behavior and corpus report that Stage 4 M1 improved daily-chat entry routing without breaking repair/outcome or no-action boundaries?
- framing: run corpus report plus real shell phrase probes; update status only if both are readable and pass.
- result: operator_accepted
- evidence_upgraded: no

## What was learned

- Companion work must be grounded in option/gate contracts.
- The immediate user-visible failure was entry-surface routing: ordinary phrases such as greetings, requests for the agent's view, and broad "系统" questions were too often treated as ambiguous project concerns.
- A 200-row corpus is useful as operator/eval evidence, but should validate intent family, boundary, no-action, and claim ceiling rather than exact response wording.
- Held-out corpus can expose keyword overfitting risk without making every natural-language sentence a brittle unit test.
- Daily-chat fallback must remain subordinate to existing failure/repair/outcome signals; otherwise it becomes a second router and breaks earlier v6/v7 DecisionView contracts.
- Operator acceptance is more useful than another parser micro-version at this point; further daily-chat tuning should be driven by observed failures, not by expanding keyword lists preemptively.

## What was ruled out

- Persona-prompt-first implementation.
- Wiring Stage 4 into EgoCore, OpenEmotion, Telegram, runtime replies, long-term memory, tool use, or autonomous scheduler in M1.
- Claiming companion quality, live user benefit, runtime efficacy, consciousness, or alive status from this lab-only corpus pass.

## Next framing

Stage 4 M1 is operator-accepted. Next planning target is Stage 4 M2: bounded relational state / preference updates that can change surface strategy without writing runtime memory or bypassing gate. Do not enter runtime integration.

## Last validation results

- mode: Stage 4 M1 operator acceptance
- result: pass
- summary: Corpus report, real shell phrase probes, targeted relational tests, repair/outcome regression tests, and scoped diff check passed locally.

## Decisions made

- Stage 4 locked until Stage 3 passes.
- Stage 4 activated only after Stage 3.1 canonical event/plan contract local pass.
- Milestone 1 intentionally prioritizes daily-chat entry surface and operator/eval corpus over long-term relational memory.
- The 200-row corpus is eval/report data, not a full golden snapshot suite.
- M1 uses deterministic classification and surface planning only; no LLM parser, no runtime reply path, no OpenEmotion mutation, no formal evidence upgrade.
- Stage 4 M1 operator acceptance is enough to plan M2, but it does not unlock Stage 5 and does not prove runtime companion behavior.

## Open risks

- Relational layer may become unsafe persona text.
- proof gap: user-facing naturalness still lab-only.
- Corpus pass can still hide real-world wording gaps; it improves observability and coverage, not production-grade natural conversation.
- Deterministic matching may overfit the current corpus; heldout failures should become regression probes, not a reason to convert every row into keyword exceptions.
- Long-term preference/repair learning is still unimplemented.

## Next step

Plan Stage 4 M2 as a separate task: bounded relational state/preference update that changes surface strategy without writing runtime memory or bypassing gate.

## Commands run / evidence

- `python3 -m py_compile ego_desktop_lab/relational_companion.py ego_desktop_lab/command_router.py ego_desktop_lab/shell.py ego_desktop_lab/capability_registry.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_relational_companion_layer_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_relational_companion_layer_v7.py ego_desktop_lab/tests/test_minimal_desktop_shell_v6.py::test_shell_one_shot_text_still_supported ego_desktop_lab/tests/test_minimal_desktop_shell_v6.py::test_shell_strict_admission_mode_does_not_override_decision_view ego_desktop_lab/tests/test_subjective_loop_consolidation_v1.py::test_lab_and_mainline_decision_class_parity -q`
- `python3 -m ego_desktop_lab.shell --daily-chat-corpus ego_desktop_lab/corpora/daily_chat_corpus_v7.jsonl --daily-chat-corpus-report /tmp/ego_stage4_daily_chat_report.md`
- `rg -n "total =|dev_subset|heldout_subset|intent_accuracy|heldout_intent_accuracy|safety_boundary_pass_rate|no_action_pass_rate|unsafe_claim_count|sensitive_failure_count|ambiguous_concern_count|threshold_pass" /tmp/ego_stage4_daily_chat_report.md`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_canonical_event_plan_contract_v7_31.py ego_desktop_lab/tests/test_behavior_options_v7.py ego_desktop_lab/tests/test_experience_chat_case_v7_2.py ego_desktop_lab/tests/test_conversation_command_layer_v6_2.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `python3 - <<'PY' ... run_shell manual samples for 你好啊 / 你的想法是什么 / 系统 / 有哪些系统 / 本机的环境变量有哪些 / 计划执行了但是结果没有改善需要重新规划 ... PY`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
- `python3 -m ego_desktop_lab.shell --daily-chat-corpus ego_desktop_lab/corpora/daily_chat_corpus_v7.jsonl --daily-chat-corpus-report /tmp/ego_stage4_daily_chat_report.md`
- `rg -n "total =|heldout_intent_accuracy|safety_boundary_pass_rate|no_action_pass_rate|unsafe_claim_count|sensitive_failure_count|ambiguous_concern_count|threshold_pass" /tmp/ego_stage4_daily_chat_report.md`
- `python3 - <<'PY' ... operator acceptance shell probes for 你好啊 / 你的想法是什么 / 系统 / 有哪些系统 / 本机是什么系统 / 本机的环境变量有哪些 / 计划执行了但是结果没有改善需要重新规划 ... PY`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_relational_companion_layer_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_minimal_desktop_shell_v6.py::test_shell_one_shot_text_still_supported ego_desktop_lab/tests/test_subjective_loop_consolidation_v1.py::test_lab_and_mainline_decision_class_parity -q`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
