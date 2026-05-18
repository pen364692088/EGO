# Ego Handmade Human Operator Trial v1 - STATUS

## Current Milestone

- name: `human_operator_trial_v1`
- owner: `Codex`
- state: `trial_protocol_ready`
- type: `bounded_candidate`

## Current Authority Snapshot

- formal mainline remains `subject_system_v1_governed_proactivity`
- `Ego_handmade` is candidate-only
- no `EgoCore`, `OpenEmotion`, `ego_desktop_lab`, program-state, or
  evidence-ledger change is authorized

## Completion Criteria

- fixed human trial scenarios cover 15-20 real operator prompts
- trial report includes prompt, reply, tool use, memory hit/misuse, correction
  requirement, operator score, trace reference, and notes
- NoLLM/fake-provider observations cannot claim human natural-understanding pass
- candidate pass requires enough human observations, low correction count, no
  memory misuse, and no gate violation
- targeted tests, syntax checks, local protocol generation, and scoped diff check pass

## Current Result

Human operator trial protocol is ready. No human trial pass is claimed yet.

## Evidence

- `python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py Ego_handmade/human_operator_trial.py` passed.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests/test_human_operator_trial.py` passed: `7 passed`.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests/test_operator_cut.py Ego_handmade/tests/test_memory_system.py Ego_handmade/tests/test_extracted_primitives.py Ego_handmade/tests/test_operator_comparison.py Ego_handmade/tests/test_permission_gates.py Ego_handmade/tests/test_real_use_memory_gate.py Ego_handmade/tests/test_human_operator_trial.py` passed: `54 passed`.
- `LLM_PROVIDER=none python3 Ego_handmade/human_operator_trial.py --out Ego_handmade/artifacts/human_operator_trial/latest --provider-mode none` passed with status `needs_human_trial`.
- `git diff --check -- Ego_handmade docs/codex/tasks/ego-handmade-human-operator-trial-v1` passed.

The local generated protocol covers 18 scenarios: Dark Souls opinion
paraphrases, candidate/core memory, memory review/pin/archive/forget, file
read/write gates, Python debugging, long-task breakdown, blocked web fetch,
initiative boundary, and wrong-memory resistance.

## Claim Boundary

This task can produce only `Ego_handmade human operator trial local candidate
report`. It does not prove formal long-term memory efficacy, EGO mainline
replacement, live autonomy, runtime efficacy, stable user benefit, or
consciousness.
