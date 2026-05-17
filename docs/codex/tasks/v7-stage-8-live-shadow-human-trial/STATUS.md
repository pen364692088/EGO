# v7 Stage 8 - Live Shadow Human Trial - STATUS

## Current milestone

- name: Sample Pack Contract
- owner: Codex + operator
- state: blocked
- type: implementation + observation

## Current state

- activation: locked
- current_layer: live shadow observation
- main_chain_status: shadow_only
- completion_class: sample_pack_contract_ready__blocked_unknown
- candidate_vs_proof: proof_pending

## Completed work

- Task package created.
- Stage runner now recognizes Stage 8 as an explicit UNKNOWN blocker instead of an unsupported stage.
- Added lab-only live-shadow human trial sample-pack contract.
- Added JSONL loader/validator and trial runner for operator-provided copied runtime event summaries.
- Added report CLI: `python3 -m ego_desktop_lab.shell --live-shadow-samples <jsonl> --live-shadow-report <path>`.
- Stage acceptance now checks the default live-shadow sample pack path and returns UNKNOWN until a valid 30+ sample pack exists.

## Last experiment

- question: can Stage 8 define and validate the real-sample contract without fabricating samples?
- framing: yes; implement the sample-pack runner but keep the default StageResult UNKNOWN until real human samples exist.
- result: UNKNOWN
- evidence_upgraded: no

## Open risks

- Fabricated or synthetic samples would make Stage 8 meaningless.
- Shadow reports may be mistaken for runtime influence.
- A test fixture with 30 rows proves the runner mechanics only; it is not admitted as human trial evidence.

## Next step

Collect at least 30 real human shadow samples at `ego_desktop_lab/corpora/live_shadow_human_trial_v7.jsonl` or pass an explicit JSONL path to the CLI, then rerun Stage 8 acceptance.

## Commands run / evidence

- `python3 -m ego_desktop_lab.stage_runner --out /tmp/ego_v7_stage_runner_result.json`
- `python3 -m py_compile ego_desktop_lab/live_shadow_human_trial.py ego_desktop_lab/stage_acceptance.py ego_desktop_lab/shell.py ego_desktop_lab/tests/test_live_shadow_human_trial_v7.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_live_shadow_human_trial_v7.py ego_desktop_lab/tests/test_stage_acceptance_v7_46.py -q`
- `python3 -m ego_desktop_lab.stage_acceptance --stage v7-stage-8 --out /tmp/ego_stage8_stage_result.json`
