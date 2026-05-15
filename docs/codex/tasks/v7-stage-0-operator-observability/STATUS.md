# v7 Stage 0 - Operator Observability - STATUS

## Current milestone

- name: Report Contract
- owner: Codex implementer subagent, reviewed by main Codex
- state: local_pass
- type: implementation

## Current state

- activation: active
- current_layer: ego_desktop_lab lab-only observability
- main_chain_status: not connected to runtime
- completion_class: local_slice_verified
- candidate_vs_proof: local_proof_only

## Completed work

- Added a lab-only Stage 0 operator observability report surface that reads
  existing `AgencyDecisionView`, `RootCauseTrace`, and `FailureTicket`.
- Added a single-command entry via `python3 -m ego_desktop_lab.shell
  --operator-report <path>`.
- Added focused tests for required report sections and the command entry.
- Completed the human-usability closeout: the report now shows explicit
  before/after selected goals, selected-intention change, rank/priority deltas,
  prediction error delta, and a concrete `continue_failure` replay probe.

## Last experiment

- question: can Stage 0 expose boundary / viability / prediction / ranking /
  gate / plasticity / root cause without recomputing selection or gate?
- framing: reuse existing lab decision/result surfaces and only normalize them
  into an operator-readable report.
- result: local_pass
- evidence_upgraded: no

## What was learned

- Stage 0 must precede kernel/companion/skill work.
- The existing `SelfMaintainingAgencyCycleResult -> AgencyDecisionView ->
  RootCauseTrace / FailureTicket` chain is sufficient for a first operator
  report without adding a second decision source.
- The first human check exposed an operator-usability gap: before/after selected
  goals and the exact replay target must be explicit, not inferred from
  Plasticity plus Ranking.

## What was ruled out

- Runtime integration in this stage.
- Formal evidence promotion in this stage.
- Recomputing selected option, policy, or gate inside the report layer.
- Advancing to Stage 1 before the report directly says
  `before=continue_or_verify_unfinished_goal` and
  `after=repair_or_replan_goal`.

## Next framing

Keep later stages blocked on reviewer/verifier confirmation; this stage only
proves local lab observability.
Stage 1 may now be activated as implementation-ready, but Stage 1 proof has not
started.

## Last validation results

- mode: local implementation verification
- result: pass
- summary: `python3 -m py_compile ego_desktop_lab/*.py`,
  `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest
  ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`, and
  `git diff --check -- ego_desktop_lab
  docs/codex/tasks/v7-stage-0-operator-observability` all passed locally.

## Decisions made

- Only Stage 0 is active.
- Later stages are locked until reviewer/verifier gate passes.
- The report entry stays under `ego_desktop_lab.shell` instead of introducing a
  separate runtime-connected command surface.

## Open risks

- This is still lab-only and does not prove runtime efficacy, live user
  benefit, or any real-channel behavior.
- Root-cause localization remains bounded to existing trace/ticket fields; when
  those fields are absent, the report stays at `unknown`.

## Next step

Hand off for review/verifier judgement on whether the Stage 0 operator report is
sufficient before any Stage 1+ work.

## Commands run / evidence

- `python3 -m py_compile ego_desktop_lab/*.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `python3 -m ego_desktop_lab.shell --operator-report /tmp/ego_stage0_operator_report.md`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-0-operator-observability`
