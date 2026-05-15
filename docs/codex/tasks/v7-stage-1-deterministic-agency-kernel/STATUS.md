# v7 Stage 1 - Deterministic Agency Kernel - STATUS

## Current milestone

- name: Cycle Trace Contract
- owner: future Codex implementer subagent
- state: local_pass
- type: implementation

## Current state

- activation: active
- current_layer: ego_desktop_lab lab-only agency kernel
- main_chain_status: not connected to runtime
- completion_class: local_slice_verified
- candidate_vs_proof: local_proof_only

## Completed work

- Task package created.
- Acceptance and validation gates defined.
- Stage 0 operator observability reached `local_pass` and completed the
  human-usability closeout needed to start Stage 1.
- Added deterministic transition contract fields:
  `selected_transition`, `ranking_transition_by_goal`, and
  `pressure_transition`.
- Hardened replay tests for negative outcome, verify success, no outcome,
  deterministic repeatability, and gate invariance.

## Last experiment

- question: can outcome feedback change next-cycle ranking deterministically
  without changing policy logic or bypassing gate?
- framing: expose readable transition fields on the existing lab-only agency
  facade, then verify replay behavior.
- result: local_pass
- evidence_upgraded: no

## What was learned

- Kernel work waited for operator observability; Stage 1 implementation now has
  a local deterministic transition proof.
- Stage 1 can prove lab-only viability-to-ranking coupling without introducing
  a second kernel authority or changing policy selection logic.

## What was ruled out

- Running Stage 1 in parallel with Stage 0.
- Claiming deterministic agency-kernel proof from Stage 0 report readability
  alone.
- Advancing to Stage 2 automatically; experience memory remains locked until a
  reviewer explicitly accepts this Stage 1 local pass.

## Next framing

Review Stage 1 local proof before deciding whether to unlock Stage 2 experience
memory.

## Last validation results

- mode: local implementation verification
- result: pass
- summary: `python3 -m py_compile ego_desktop_lab/*.py`,
  `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
  ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py -q`,
  `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
  ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`,
  `python3 -m ego_desktop_lab.shell --operator-report
  /tmp/ego_stage0_operator_report.md`, `TMPDIR=/tmp
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`, and
  `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*` passed.

## Decisions made

- Stage 1 activated only after Stage 0 reached local_pass and human-usability
  closeout.
- Stage 1 remains lab-only; it does not unlock Stage 2 automatically and does
  not update formal repo state/evidence.

## Open risks

- Existing tests may pass without exposing enough trace.
- proof gap: human reviewer still needs to decide whether local transition
  proof is sufficient to start Stage 2.

## Next step

Hold at reviewer gate; do not start Stage 2 until explicitly requested.

## Commands run / evidence

- Stage 0 gate evidence: `python3 -m ego_desktop_lab.shell --operator-report /tmp/ego_stage0_operator_report.md`
- `python3 -m py_compile ego_desktop_lab/*.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `python3 -m ego_desktop_lab.shell --operator-report /tmp/ego_stage0_operator_report.md`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
