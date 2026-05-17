# v7 Stage 8.2 - Live LLM Answer Draft Admission - STATUS

## Current milestone

- name: Live LLM answer draft admission
- owner: Codex
- state: local_pass
- type: lab-only implementation

## Current state

- activation: active
- main_chain_status: lab_only
- completion_class: deterministic_pass
- candidate_vs_proof: deterministic proof required; live LLM remains optional

## Completed work

- Added canonical command categories for basic math, LLM-open question answer drafts, fresh external information boundaries, and session-local answer-only preference.
- Added `LLMAnswerDraft` admission records and validation for source decision hash, no-action evidence, fresh-data/tool flags, forbidden action claims, and claim-ceiling violations.
- Added opt-in shell answer rendering with `--llm-expression-provider fake|live`; CLI default attempts live and reports explicit deterministic fallback when live credentials are unavailable.
- Added repo config resolution for live answer admission: `ego_desktop_lab` reads `EgoCore/config/llm.yaml` `use_cases.chat` provider/model/base_url/api_key_env while keeping secrets environment-only.
- Added Stage 8.2 stage acceptance samples and inserted Stage 8.2 into the v7 stage runner sequence before Stage 9.
- Refreshed `docs/codex/tasks/TASK_LANE_INDEX.md` after adding this task package.

## Verification

- `python3 -m py_compile ego_desktop_lab/*.py ego_desktop_lab/tests/test_llm_answer_admission_v7_82.py` -> pass
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_llm_answer_admission_v7_82.py ego_desktop_lab/tests/test_llm_shadow_admission_v7_81.py -q` -> `16 passed`
- `python3 -m ego_desktop_lab.stage_acceptance --stage v7-stage-82 --out /tmp/ego_stage82_stage_result.json` -> `PASS`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q` -> `336 passed`
- `scripts/run_verify.sh fast` -> pass
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-* docs/codex/tasks/TASK_LANE_INDEX.md` -> pass

## Evidence paths

- `/tmp/ego_stage82_stage_result.json`
- `/tmp/ego_stage82_stage_result.md`

## Open risks

- Live LLM quality is not proven unless an operator runs with credentials.
- The deterministic fake provider proves admission mechanics only.
- Weather, news, price, file, shell, browser, and desktop requests remain unavailable unless a later permissioned tool stage adds them.

## Next step

Operator can now test answer admission with `python3 -m ego_desktop_lab.shell --text '1+1=几?' --llm-expression-admitted --llm-expression-provider fake` or with live credentials using the default live provider. Next stage remains blocked until operator accepts this lab-only behavior.
