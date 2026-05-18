# Ego Handmade Human Operator Trial v1 - PLAN

## Implementation

- Add a candidate-local human trial harness in `Ego_handmade`.
- Define fixed real-use scenarios for opinion paraphrases, memory promotion,
  memory management, file gates, debugging, long-task planning, tool refusal
  recovery, and initiative boundaries.
- Support JSONL observation import and generate local JSON/Markdown reports.
- Keep automated scoring honest: real-provider human notes can become candidate
  pass; NoLLM/fake notes remain smoke only.

## Verification

- Syntax-check `agent_base.py`, `memory_system.py`, `real_use_gate.py`, and the
  human trial harness.
- Run the existing Ego_handmade targeted tests plus the new human trial tests.
- Generate a local protocol/report artifact under ignored
  `Ego_handmade/artifacts/human_operator_trial/`.
- Run scoped `git diff --check`.

## Closeout

- Update `STATUS.md` with evidence and claim boundary.
- Commit and push only scoped changes under `Ego_handmade/**` and this task
  directory.
