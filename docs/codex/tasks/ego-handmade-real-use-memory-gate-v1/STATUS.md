# Ego Handmade Real Use Memory Gate v1 - STATUS

## Current Milestone

- name: `real_use_memory_gate_v1`
- owner: `Codex`
- state: `local_candidate_pass`
- type: `bounded_candidate`

## Current Authority Snapshot

- formal mainline remains `subject_system_v1_governed_proactivity`
- `Ego_handmade` is candidate-only
- no `EgoCore`, `OpenEmotion`, `ego_desktop_lab`, program-state, or
  evidence-ledger change is authorized

## Completion Criteria

- candidate memories do not automatically become core memory
- hot context injects pinned / repeatedly used / task-relevant candidate memory
- archived or forgotten memory does not enter prompt context
- CLI memory management commands work
- real-use gate runs at least 10 practical scenarios and writes local reports
- targeted tests, syntax checks, and scoped diff check pass

## Current Result

Local real-use memory gate candidate pass.

## Evidence

- `python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py` passed.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests/test_operator_cut.py Ego_handmade/tests/test_memory_system.py Ego_handmade/tests/test_extracted_primitives.py Ego_handmade/tests/test_operator_comparison.py Ego_handmade/tests/test_permission_gates.py Ego_handmade/tests/test_real_use_memory_gate.py` passed: `47 passed`.
- `python3 Ego_handmade/real_use_gate.py --out Ego_handmade/artifacts/real_use_gate/latest` passed with status `local_candidate_pass`.
- `git diff --check -- Ego_handmade docs/codex/tasks/ego-handmade-real-use-memory-gate-v1` passed.

The real-use gate currently covers 11 deterministic scenarios: opinion chat,
auto candidate memory, hot-memory recall, explicit core memory, file read,
blocked file write, Python debugging, long-task breakdown, blocked web fetch,
archived-memory non-use, and initiative-boundary explanation.

## Claim Boundary

This proves only `Ego_handmade real-use memory gate local candidate pass`. It
does not prove formal long-term memory efficacy, EGO mainline replacement, live
autonomy, runtime efficacy, stable user benefit, or consciousness.
