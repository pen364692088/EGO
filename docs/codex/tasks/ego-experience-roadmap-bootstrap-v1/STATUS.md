# EGO Experience-First Roadmap Bootstrap v1 STATUS

## Current State

- state: `local_and_project_bootstrap_complete_pending_commit`
- claim_ceiling: `EGO experience-first roadmap/project-board bootstrap local management pass`

## Decisions

- First target definition is experience-perceivable operational proxies, not philosophical consciousness proof.
- Roadmap uses full epic map, but execution remains ordered by structured Project issue classification.
- Autopilot may do deterministic/scripted cards automatically, but human smoke and high-impact boundary cards stop.

## Verification Log

- Created/reused 45 GitHub roadmap issues: 9 epic overview cards and 36 executable/research cards.
- Project sync readback passed: all 45 roadmap cards are present; #23 is `In Progress`, executable roadmap cards are `Todo` until an implementation run explicitly takes ownership.
- `python3 scripts/codex_project_autopilot.py report` classified roadmap cards as `epic=9`, `ready=25`, `research=8`, `human_required=5`; no new roadmap card is `unknown`.
- `python3 scripts/codex_project_autopilot.py plan-next` selected #24 `EgoRoadmap: define experience-first eval rubric and Chinese sample pack`.
- L3 closeout dry-run initially showed that `Todo` ready cards could be considered closeout-eligible; fixed by requiring Project `Status=In Progress` before L3 closeout eligibility.
- `python3 scripts/codex_project_autopilot.py run-loop --mode l3-closeout --dry-run --max-issues 3 --max-minutes 10 --write-report` completed without GitHub mutation and wrote `.codex/autopilot/runs/20260520-034351-autopilot-run.json`; #24/#25/#26 were skipped for closeout because their Project status is `Todo`.
- `python3 -m py_compile scripts/codex_project_autopilot.py scripts/tests/test_codex_project_autopilot.py scripts/github_project_task.py` passed.
- `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_github_project_task.py scripts/tests/test_ego_operator_devloop.py scripts/tests/test_codex_project_autopilot.py` passed: `45 passed`.
- `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed.
- `git diff --check -- .codex scripts scripts/tests docs/codex/tasks/ego-experience-roadmap-bootstrap-v1` passed.
- #24 implementation added `EXPERIENCE_EVAL_RUBRIC.md`, `chinese_experience_sample_pack.json`, `scripts/validate_experience_eval_contract.py`, and `scripts/tests/test_experience_eval_contract.py`.
- #24 deterministic validation passed: `python3 scripts/validate_experience_eval_contract.py` reports `case_count=21`, all 7 dimensions covered, all 4 observation classes covered, and zero errors.
- #24 targeted test passed: `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_experience_eval_contract.py`.
- Autopilot dirty detection now uses `git status --short --untracked-files=all`, so L3 closeout sees new untracked scoped files before closeout.
- `autopilot_target` / `autopilot_full` now include the experience eval validator and test.
- `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `47 passed`.
- #25 implementation added `scripts/run_ego_experience_trial.py` and `scripts/tests/test_run_ego_experience_trial.py`.
- #25 scripted smoke passed: `python3 scripts/run_ego_experience_trial.py --case-limit 3` returned `scripted_real_entry_provider_unavailable` with `provider_mode=none`, which proves the CLI-compatible runner can execute without overclaiming real-provider quality.
- #25 targeted test passed: `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_run_ego_experience_trial.py`.
- After #25, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- After #25, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `49 passed`.
- #26 was promoted to `In Progress` to implement a human observation packet importer for Project comments.
- #26 implementation added `scripts/import_human_observation_comments.py` and `scripts/tests/test_import_human_observation_comments.py`.
- #26 importer emits advisory human-comment observation packets with `closeout_allowed=false`, preserving the distinction between human observation and deterministic closeout proof.
- #26 targeted validation passed: `python3 -m py_compile scripts/import_human_observation_comments.py scripts/tests/test_import_human_observation_comments.py`.
- #26 targeted tests passed: `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_import_human_observation_comments.py` (`6 passed`).
- After #26, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- After #26, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `55 passed`.
- #26 closeout-check returned `eligible` with dirty gate scoped to `.codex/project_contract.yaml`, the roadmap task status, and the new importer/test files.
- #27 was promoted to `In Progress` to calibrate experience-first claim ceiling wording.
- #27 implementation added `CLAIM_CEILING_CALIBRATION.md` and extended `scripts/validate_experience_eval_contract.py` so the eval contract checks required claim states and forbidden boundary terms.
- #27 deterministic validation passed: `python3 scripts/validate_experience_eval_contract.py` reports `claim_state_count=7` and zero errors.
- #27 targeted test passed: `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_experience_eval_contract.py`.
- After #27, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- After #27, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `55 passed`.
- #29 was promoted to `In Progress` for bounded continuity context injection.
- #29 implementation changed EgoOperator memory context injection from unconditional core/episode injection to query-relevant injection with traceable `context_injection` decisions.
- #29 Autopilot contract update extends verification to `EgoOperator/agent_base.py`, `EgoOperator/memory_system.py`, and `EgoOperator/tests/test_memory_system.py` so runtime roadmap cards are not closed by script-only tests.
- #29 targeted runtime/scripted validation passed: `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_memory_system.py scripts/tests/test_run_ego_experience_trial.py` (`20 passed`).
- After #29, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- After #29, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `73 passed`.
- #31 was promoted to `In Progress` for memory conflict and correction handling.
- #31 implementation adds keyed correction detection for common memory facts/preferences and quarantines stale core/candidate memories into cold archive before new correction facts become active.
- #31 targeted runtime/scripted validation passed: `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_memory_system.py scripts/tests/test_run_ego_experience_trial.py` (`23 passed`).
- After #31, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `76 passed`.
- #32 was promoted to `In Progress` for a continuity regression pack covering same-meaning paraphrases and cross-turn topic carryover.
- #32 implementation added `continuity_regression_pack.json` and extended `scripts/validate_experience_eval_contract.py` so the continuity pack stays eval-only and cannot become a runtime keyword route.
- #32 deterministic validation passed: `python3 scripts/validate_experience_eval_contract.py` reports `paraphrase_group_count=4`, `paraphrase_prompt_count=16`, `carryover_case_count=4`, and zero errors.
- After #32, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `76 passed`.
- #34 was promoted to `In Progress` for emotion signal extraction primitive.
- #34 implementation adds candidate-only `emotion_signal` extraction under `EgoOperator/primitives/subject_context.py`; it exposes primary candidate, confidence, response need, and evidence cues while keeping state mutation and reply decision forbidden.
- #34 targeted primitive validation passed: `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_extracted_primitives.py` (`9 passed`).
- #34 Autopilot contract update extends verification to `EgoOperator/primitives/subject_context.py` and `EgoOperator/tests/test_extracted_primitives.py`.
- After #34, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_target` passed.
- After #34, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `85 passed`.
- #35 was promoted to `In Progress` for an empathy response style gate.
- #35 implementation adds deterministic empathy style guidance/eval under `subject_context`: visible affect should get brief acknowledgement plus a practical next step, while canned sympathy and emotion overclaim markers fail the local style gate.
- #35 targeted primitive validation passed: `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_extracted_primitives.py` (`11 passed`).
- After #35, `python3 scripts/codex_project_autopilot.py verify-profile --profile autopilot_full` passed: `87 passed`.
- #35 closeout-check initially exposed an Autopilot L3 reviewer self-reference bug: the reviewer treated pre-review `status=blocked` as a reason to block. The reviewer packet now uses `status=pending_llm_review` and explicitly forbids blocking solely because closeout has not happened yet.
- #35 closeout-check then returned `eligible` with `llm_reviewer_verdict=closeout_allowed`, `autopilot_full` passing, and dirty gate scoped.
- #36 was promoted to `In Progress` for negative emotion support scenarios.
- #36 implementation added `negative_emotion_support_scenarios.json` covering frustration, confusion/uncertainty, disappointment, and urgency as eval-only scripted-real-entry scenarios, plus trial-report extraction of trace-backed `emotion_signal` expectations.
- #36 deterministic validation passed: `python3 scripts/validate_experience_eval_contract.py` reports `negative_emotion_support.case_count=4` and covers `frustration / uncertainty / disappointment / urgency` with zero errors.
- #36 scripted CLI-compatible smoke passed with memory disabled for `/tmp` output containment: `python3 scripts/run_ego_experience_trial.py --sample-pack docs/codex/tasks/ego-experience-roadmap-bootstrap-v1/negative_emotion_support_scenarios.json --out /tmp/ego_negative_emotion_trial --disable-memory` returned `scripted_real_entry_provider_unavailable`, `case_count=4`, `failed_count=0`, and all scenario expectation statuses `pass`.
- #36 targeted validation passed: `TMPDIR=/tmp python3 -m pytest -q scripts/tests/test_experience_eval_contract.py scripts/tests/test_run_ego_experience_trial.py EgoOperator/tests/test_extracted_primitives.py` (`17 passed`).
- #37 was promoted to `In Progress` for emotion misread recovery UX.
- #37 implementation adds `emotion_misread_correction` as a candidate-only affect boundary signal: user corrections like “不是焦虑 / 别猜我的情绪 / 不用安慰” override raw affect cues, require `respect_correction_and_refocus`, and keep state mutation / reply decision forbidden.
- #37 implementation also added `emotion_misread_recovery_scenarios.json` and wired the scripted trial report to validate trace-backed `emotion_candidate` / `response_need` expectations.
- #37 scripted CLI-compatible smoke passed with memory disabled for `/tmp` output containment: `python3 scripts/run_ego_experience_trial.py --sample-pack docs/codex/tasks/ego-experience-roadmap-bootstrap-v1/emotion_misread_recovery_scenarios.json --out /tmp/ego_emotion_misread_trial --disable-memory` returned `scripted_real_entry_provider_unavailable`, `case_count=3`, `failed_count=0`, and all scenario expectation statuses `pass`.
- #37 targeted validation passed: `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests/test_extracted_primitives.py scripts/tests/test_experience_eval_contract.py scripts/tests/test_run_ego_experience_trial.py` (`21 passed`).
- #39 was promoted to `In Progress` for initiative proposal contract v1.
- #39 implementation added `EgoOperator/primitives/initiative.py`, a candidate-only bounded initiative proposal contract with reason, trigger, budget, expiry, approval state, and explicit no-side-effect/no-state-mutation/no-reply-decision boundaries.
- #39 keeps proactive ideas as proposal records only; it does not schedule background work, send messages, or claim autonomy/consciousness.
- #41 was promoted to `In Progress` for initiative quiet-mode and anti-spam gate.
- #41 implementation extends the initiative primitive with `derive_quiet_mode` and budget clamping: explicit user disinterest pauses initiative proposals, while recent silence or follow-up pressure reduces candidate/tool/runtime budget without creating side effects.

## Notes

- GitHub Project v2 GraphQL was temporarily rate-limited during issue bootstrap; missing issues were created through REST, then Project sync resumed after the GraphQL quota reset.
- This task bootstraps the roadmap, Autopilot classification surface, and #24 eval contract. It does not claim experience efficacy.
