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

## Notes

- GitHub Project v2 GraphQL was temporarily rate-limited during issue bootstrap; missing issues were created through REST, then Project sync resumed after the GraphQL quota reset.
- This task bootstraps the roadmap, Autopilot classification surface, and #24 eval contract. It does not claim experience efficacy.
