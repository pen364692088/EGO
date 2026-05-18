# Ego Handmade Operator Runtime Contract v1 - STATUS

## Current Milestone

- name: `operator_runtime_contract_v1`
- owner: `Codex`
- state: `local_candidate_pass`
- type: `bounded_candidate`

## Current Authority Snapshot

- formal mainline remains `subject_system_v1_governed_proactivity`
- `Ego_handmade` is candidate-only
- no `EgoCore`, `OpenEmotion`, `ego_desktop_lab`, program-state, or
  evidence-ledger change is authorized

## Completion Criteria

- runtime mode status is visible in CLI
- default `approve` mode uses file-write proposals, not direct writes
- approved file writes require one-shot lease path/hash match
- denied, mismatched, overwrite, or out-of-allowlist writes do not mutate files
- subagents cannot directly call write/command/network tools
- targeted tests, syntax checks, and scoped diff check pass

## Current Result

Local operator runtime contract candidate pass.

## Evidence

- `python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py Ego_handmade/human_operator_trial.py` passed.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests/test_permission_gates.py Ego_handmade/tests/test_operator_runtime_contract.py` passed: `18 passed`.
- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests/test_operator_cut.py Ego_handmade/tests/test_memory_system.py Ego_handmade/tests/test_extracted_primitives.py Ego_handmade/tests/test_operator_comparison.py Ego_handmade/tests/test_permission_gates.py Ego_handmade/tests/test_real_use_memory_gate.py Ego_handmade/tests/test_human_operator_trial.py Ego_handmade/tests/test_operator_runtime_contract.py` passed: `63 passed`.
- `printf '/tools\n/approvals\nexit\n' | AGENT_MEMORY=1 LLM_PROVIDER=none python3 Ego_handmade/agent_base.py` showed runtime mode `approve`, `propose_file_write`, pending approvals, and subagent side effects disabled.
- `git diff --check -- Ego_handmade docs/codex/tasks/ego-handmade-operator-runtime-contract-v1` passed.

The implemented v1 covers file-write transactions: proposal, approval/reject,
edit path, one-shot lease, path/hash match, overwrite gate, write allowlist,
trusted-workspace low-risk auto lease, and trace-visible pending approvals.
`run_command` and `web_fetch` remain conservative and are not widened in this
file-write transaction slice.

## Claim Boundary

This task can produce only `Ego_handmade operator runtime contract local
candidate pass`. It does not prove formal long-term memory efficacy, EGO
mainline replacement, live autonomy, runtime efficacy, stable user benefit, or
consciousness.
