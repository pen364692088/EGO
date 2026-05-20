# EgoOperator Algorithm Inventory

Status: `replacement candidate / operator cut`

Claim ceiling: `EgoOperator replacement candidate with extracted primitives`.

This inventory records what is worth extracting from `EgoCore`, `OpenEmotion`,
and `ego_desktop_lab` without importing their runtime architecture. The
operator path remains:

`user text -> LLM understanding -> candidate response/plan -> gate`

No item below authorizes demoting, archiving, or modifying the old projects.

## Structure Risk Check

- Real target: improve operator experience and preserve natural-language
  understanding, not merely reorganize folders.
- Main risk: copying old route/template/schema layers would reintroduce the
  same semantic flattening that made paraphrases fail.
- Contract first: primitives must be readonly or gate-owned; LLM proposes,
  outer gate admits side effects, and trace records what happened.
- Counterexample gate: if adding primitives makes "你觉得黑暗之魂怎么样" and
  "你认为黑暗之魂如何" diverge, the extraction is wrong.
- Current validation: local tests can only prove candidate-local primitive
  wiring and paraphrase harness behavior, not formal replacement.

## EgoCore Extraction

### Keep

- Safety gate as final admission for tools, files, commands, network, memory
  writes, and claim ceiling.
- Workspace path containment before file read/write.
- UTF-8 JSONL trace and replay-readable audit records.
- Tool execution boundary: model proposes tool calls; runtime decides and
  executes.
- Output claim checker concept: visible claims must not exceed evidence.

### Rewrite

- Transport ideas such as Telegram/CLI profiles, but only after the operator
  candidate passes local gates.
- Trace/replay formatting can be simplified into EgoOperator-local JSONL.
- Team/subagent dispatch can remain isolated worker reports, not shared state.

### Discard

- Chat keyword routing before LLM understanding.
- Template fallback answers for open-ended user meaning.
- Complex proactive main-chain behavior in this operator cut.
- Any path where a tool or subagent mutates lead memory/todo directly.

### Reference-Only

- Formal EGO program-state and evidence governance.
- Existing Telegram production launcher details.
- Mainline acceptance ledger and old live evidence.

## OpenEmotion Extraction

### Keep

- Self-model snapshot as readonly context.
- Appraisal signal as candidate context, never as reply owner.
- Memory salience as bounded prompt context, not canonical memory mutation.
- Reflection proposal as optional reasoning support.
- Initiative candidate as a proposal only.

### Rewrite

- Subject signals are represented in `primitives/subject_context.py` as a
  small readonly snapshot.
- Any core-memory proposal must be written to candidate updates or surfaced to
  the operator, not auto-promoted.

### Discard

- Direct state mutation from subject context.
- Visible reply ownership by a lower-level subject signal.
- Any rule that compresses the latest user message into a keyword route before
  the LLM reads it.

### Reference-Only

- Proto-self internals and developmental memory details.
- Formal `subject_system_v1_governed_proactivity` live evidence chain.

## ego_desktop_lab Extraction

### Keep

- Paraphrase suite design for checking stable understanding.
- Deterministic replay idea.
- Operator report format for scenario comparison.
- Corpus/eval harness concepts for natural Q&A, tool refusal recovery, and
  long-task breakdown.

### Rewrite

- Eval harnesses become local primitive tests under `EgoOperator/tests/`.
- Lab reports should compare candidate behavior; they must not become runtime
  routing tables.

### Discard

- Lab shell as production runtime.
- Semantic router as the first step of user-message handling.
- Template matching as a substitute for natural-language response generation.

### Reference-Only

- Existing lab scenario notes and previous acceptance docs.

## Current Primitive Layout

- `primitives/subject_context.py`: readonly self/appraisal/reflection context.
- `primitives/runtime_gate.py`: local gate and claim-ceiling contract.
- `primitives/evals.py`: paraphrase and operator-behavior eval primitives.

## Executable Legacy Primitive Inventory

This section is the #59 research output. It classifies concrete legacy
capabilities by extraction posture. It does not move, edit, or reactivate legacy
code.

### EgoCore

Detailed gate/trace/transport mapping lives in
[`EGOCORE_GATE_TRACE_TRANSPORT_MAP.md`](EGOCORE_GATE_TRACE_TRANSPORT_MAP.md).

| Capability | Evidence surface | Classification | EgoOperator extraction rule |
| --- | --- | --- | --- |
| Runtime tool boundary and command/file tests | `legacy/ego-pre-handmade-mainline/EgoCore/tests/test_shell_tool_windows_commands.py`, `tests/test_file_tool_windows_paths.py`, `tests/test_llm_client_tool_calls.py` | keep | Keep the idea of runtime-owned execution and Windows-path handling, but keep EgoOperator's transaction approval and content-hash lease as authority. |
| Completion / output claim contract | `tests/test_completion_contract_integration.py`, `tests/test_output_check.py`, `tests/test_response_contract.py` | keep | Extract as local claim-ceiling and completion-result checks; do not import old response templates. |
| Trace/session logging | `tests/test_session_log.py`, `tests/test_replay_regression.py`, dashboard session export tests | keep | Preserve append-only replayability and UTF-8 trace readability in EgoOperator JSONL. |
| Telegram transport and process launchers | `app/telegram_*`, `tests/test_telegram_*`, launcher docs | reference-only | Keep as fallback/live-reference material only; do not make transport a blocker for EgoOperator CLI UX. |
| Semantic router / request classifier | `app/command_router.py`, `tests/test_semantic_router.py`, `tests/test_request_classifier_host_override.py` | discard | Do not reintroduce keyword-first routing before LLM understanding. Use only as negative regression material. |
| Proactive subject-system bridge | `tests/test_subject_system_v1_*`, `tests/test_proactive_*` | rewrite | If reused, expose only proposal/gate/trace primitives. Do not port the old proactive main chain wholesale. |

### OpenEmotion

Detailed subject primitive mapping lives in
[`OPENEMOTION_SUBJECT_PRIMITIVE_MAP.md`](OPENEMOTION_SUBJECT_PRIMITIVE_MAP.md).

| Capability | Evidence surface | Classification | EgoOperator extraction rule |
| --- | --- | --- | --- |
| Self-model schema and snapshots | `emotiond/self_model/*`, `schemas/self_model.schema.json`, `core/self_model.py` | keep | Keep as readonly operational self-model context; never as consciousness proof or direct state authority. |
| Appraisal / emotion labels / response intent contracts | `emotiond/appraisal.py`, `emotiond/emotion_labels.py`, `schemas/response_intent_contract.v1.schema.json` | keep | Extract bounded affect signals and response-intent hints as candidate context only. |
| Episodic/narrative memory surfaces | `emotiond/memory/*`, `emotiond/episodic_memory.py`, `emotiond/narrative_memory.py` | rewrite | Use for salience and candidate-memory ideas; EgoOperator core memory still requires operator approval. |
| Reflection engines and adapters | `emotiond/reflection*`, `emotiond/meta_cognition.py` | rewrite | Reflection can propose next checks or self-description cautions, not mutate memory/state or decide replies. |
| Developmental cycle / intrinsic motivation | `emotiond/developmental_core/*`, `emotiond/intrinsic_motivation.py` | reference-only | Useful for long-term research; too heavy for the current operator runtime cut. |
| emotiond daemon as authority source | `emotiond/api.py`, `emotiond/daemon.py`, `POLICIES/SELF_REPORT_ALIGNMENT.md` | discard for EgoOperator runtime | Do not add a second daemon/state owner to EgoOperator. Keep only as historical authority-boundary reference. |

### ego_desktop_lab

| Capability | Evidence surface | Classification | EgoOperator extraction rule |
| --- | --- | --- | --- |
| Permissioned runtime action and gates | `permissioned_runtime_action.py`, `gate.py`, `tests/test_permissioned_runtime_action_v7.py`, `tests/test_high_risk_action_blocked.py` | keep | Keep proposal/admission/test style, mapped into EgoOperator's existing permission broker. |
| LLM proposal cannot mutate core state | `tests/test_llm_proposal_cannot_modify_state.py`, `tests/test_llm_plan_must_pass_gate.py`, `tests/test_llm_can_propose_plan_but_gate_can_block.py` | keep | Treat as a core invariant for all future EgoOperator planning/active-layer work. |
| Failure classification and repair/reframe loops | `root_cause.py`, `goal_reframe.py`, `tests/test_continue_repair_loop_triggers_reframe.py`, `tests/test_repeated_repair_triggers_goal_split.py` | keep | Extract as Autopilot/EgoOperator repair gates: repeated failures should trigger reframe, not endless micro-fixes. |
| Experience memory / strategy learning | `experience_memory.py`, `strategy_memory.py`, `tests/test_experience_memory_v7.py`, `tests/test_repair_success_updates_strategy_memory.py` | rewrite | Use as candidate-learning design input; do not auto-promote learning into core memory. |
| Decision/operator report views | `decision_view.py`, `console.py`, report builder exports in `__init__.py` | keep | Keep operator digest/report patterns; avoid importing the lab shell as runtime. |
| Semantic intelligence / semantic policy router | `semantic_intelligence.py`, `semantic_policy.py`, `semantic_provider.py`, `console.py` | discard as runtime entry | Useful for eval/reporting, but not as first-layer runtime routing. |
| Live shadow / human trial harness | `live_shadow_*`, `tests/test_live_shadow_human_trial_v7.py` | reference-only | Keep as evaluation inspiration; do not present lab shadow as real provider/human pass. |

### Extraction Order

1. Keep strengthening EgoOperator's existing gates/reports before importing any
   subject or learning primitive.
2. Extract failure-reframe and operator-report patterns next because they reduce
   development-loop waste without changing user-visible self claims.
3. Extract memory/appraisal/reflection only as candidate context with explicit
   operator approval or reviewer gates.
4. Leave transport, daemon, semantic-router, and old proactive-chain mechanics as
   reference-only until a separate Stage Card says otherwise.

## Next Gate

Run the 20-case Dark Souls paraphrase gate and the five-scenario operator
comparison. Only if `EgoOperator` stays better on experience, explainability,
side-effect control, and trace readability should a separate
`ego-mainline-demotion-v1` task be opened.
