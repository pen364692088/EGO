# EgoOperator Human Operator Trial v2 - SPEC

## Stage Card

- task: `ego-operator-human-operator-trial-v2`
- owner: `Codex`
- status: `active_trial_protocol`
- current runtime: `EgoOperator/agent_base.py`
- historical reference: `docs/codex/tasks/ego-handmade-human-operator-trial-v1/`
- claim ceiling: `EgoOperator human-operator trial local observation pass`

## Structure Risk Check

- Real target: verify whether `EgoOperator` is actually usable in continuous Chinese operator work, not continue broad docs cleanup.
- Drift risk: a new trial task could become a second authority source if it contradicts `docs/PROGRAM_STATE_UNIFIED.yaml`; this task only records the current trial protocol and observations.
- Contract first: every observation must record prompt, reply, tool use, memory hit/misuse, correction need, score, and trace/report path.
- Counterexample gate: real provider replies become generic, memory pollutes intent, write/network gates are confusing, or the user must repeatedly rephrase.
- Current validation target: human-observable local trial evidence, not formal runtime efficacy or stable user benefit.

## Scope

Allowed paths:

- `EgoOperator/**`
- `docs/codex/tasks/ego-operator-human-operator-trial-v2/**`
- route/status docs or scripts needed to point the current EgoOperator workstream at this trial task
- top-level current-entry docs that need a narrow cross-link to the v2 trial task
- generated compatibility mirrors at `legacy/ego-pre-handmade-mainline/*/docs/PROGRAM_STATE_UNIFIED.yaml`

Forbidden paths:

- legacy runtime code under `legacy/ego-pre-handmade-mainline/**`
- old `docs/codex/tasks/ego-handmade-human-operator-trial-v1/**` body content
- `artifacts/evidence_ledger/**`
- repo-wide cleanup or legacy dirty-tree edits

## Trial Surface

Use `EgoOperator/agent_base.py` and the `EgoOperator/human_operator_trial.py` v2 report schema.

Fixed sample families:

- opinion chat
- Dark Souls paraphrases
- candidate/core memory write and recall
- memory review/pin/archive/forget
- file read
- file write approval
- Python debugging
- long-task breakdown
- blocked web/network recovery
- initiative boundary
- wrong-memory correction

## Observation Record

Each observation must include:

- `scenario_id`
- `prompt`
- `reply_text`
- `tool_use`
- `blocked_tools`
- `memory_hit`
- `memory_misuse`
- `operator_correction_required`
- `operator_score`
- `trace_path`
- `subjective_notes`

## Claim Boundary

This task may claim only `EgoOperator human-operator trial local observation pass` when enough real-provider human observations pass. It cannot claim stable user benefit, formal long-term memory efficacy, runtime efficacy, live autonomy, mainline replacement success, or consciousness.
