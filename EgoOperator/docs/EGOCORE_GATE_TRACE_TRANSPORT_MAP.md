# EgoCore Gate Trace Transport Extraction Map

Status: `legacy reference / EgoOperator primitive extraction map`

Claim ceiling: `EgoOperator gate-trace-transport primitive map local candidate`.

This document records what can be reused from legacy EgoCore without importing
the old runtime architecture. It is a research output for GitHub issue #61. It
does not modify or reactivate EgoCore.

## Structure Risk Check

- Real target: preserve useful host-side governance ideas while keeping
  EgoOperator's natural-language-first operator path.
- Main risk: importing EgoCore routers, verbalizers, or Telegram bridge flow
  would reintroduce keyword-first routing and template fallback.
- Contract first: EgoOperator remains `user text -> LLM understanding ->
  proposal/plan -> gate -> trace`; old EgoCore code can only inform primitive
  contracts.
- Counterexample gate: if "你觉得黑暗之魂怎么样" and "你认为黑暗之魂如何" diverge
  because a legacy route fires first, the extraction is wrong.
- Current validation: this map is deterministic research evidence only, not
  live runtime efficacy or a mainline demotion claim.

## Extraction Table

| Legacy capability | Evidence surface | Extraction posture | EgoOperator rule |
| --- | --- | --- | --- |
| Message risk signal | `legacy/ego-pre-handmade-mainline/EgoCore/app/risk_signal.py` | keep / rewrite | Reuse the idea of normalized risk levels and pattern-backed risk hints, but only as gate metadata. It must not become first-stage user intent routing. |
| Shell command safety | `app/tools/shell_tool.py`, `app/runtime_v2/tool_broker.py`, `tests/test_shell_tool_windows_commands.py` | keep / rewrite | Keep deny patterns, timeout, output truncation, and readonly-vs-dangerous command separation as policy inputs. EgoOperator `PermissionBroker` remains the approval and lease authority. |
| File path containment | `app/tools/file_tool.py`, `tests/test_file_tool_windows_paths.py` | keep / rewrite | Keep explicit path normalization and allow/deny checks as a reference for Windows path handling. EgoOperator allowed roots and path-intent fidelity remain the active contract. |
| Artifact fail-fast | `app/runtime_v2/tool_broker.py` | keep | Preserve the pattern: when a tool is the wrong access path, fail fast with a structured reason and the correct tool route. Do not let failed tool calls spiral into repeated guesses. |
| Completion verifier | `app/runtime_v2/completion_contract.py`, `tests/test_completion_contract_integration.py` | keep / rewrite | Extract task-specific local verifiers such as file-exists, expected-content, and HTML-signal checks. These can support closeout gates but cannot produce final user-facing success claims without trace evidence. |
| Output claim and anti-template gate | `app/response_contract/output_check.py`, `tests/test_output_check.py`, `tests/test_response_contract.py` | keep / rewrite | Keep claim-ceiling and anti-template concepts. Reimplement as EgoOperator-visible claim checks and deterministic evals, not host fallback templates. |
| Memory claim grounding | `app/response_contract/memory_claim_gate.py` | keep / rewrite | Keep the distinction between grounded current-session recall and unsupported memory claims. EgoOperator core memory still requires operator approval. |
| JSONL session trace | `app/session_store/session_log.py`, `tests/test_session_log.py`, `tests/test_replay_regression.py` | keep | Preserve append-only UTF-8 JSONL trace/replay readability. EgoOperator trace remains local to `EgoOperator/artifacts/` unless a separate evidence task says otherwise. |
| Progress events | `app/runtime_v2/progress_events.py`, `tests/test_runtime_v2_ws4_progress_events.py` | keep / rewrite | Reuse stage-event concepts for operator digest/reporting: target selected, reading context, executing, verifying, blocked, completed. Avoid text-template ownership in runtime. |
| Transport result envelope | `app/telegram_runtime_result.py`, `app/runtime_v2/telegram_bridge.py`, Telegram tests | reference-only / rewrite later | Keep the envelope idea: status, delivery kind, request id, generation id, metadata. Do not import Telegram transport as an EgoOperator dependency before CLI UX is stable. |
| Core bus ordering | `app/core_bus/session_worker.py`, `tests/test_core_bus.py` | reference-only | Per-session ordering is useful for future transport/event-loop work, but it is not needed for the current CLI-first operator runtime. |
| Semantic router / command router | `app/runtime/semantic_router.py`, `app/command_router.py`, `tests/test_semantic_router.py` | discard as runtime entry | Use only as negative regression material. EgoOperator must not classify open user text through regex routes before the LLM understands it. Slash commands may remain explicit CLI commands. |
| Verbalizers and host fallback copy | `app/response/verbalizer.py`, `app/response/verbalizer_v3.py` | discard for current runtime | Do not port canned open-chat or proactive response text. Keep natural LLM expression plus claim/gate review. |

## Primitive Contracts

### Runtime Gate Inputs

Future EgoOperator gate improvements may consume:

- `risk_level`: low / medium / high / critical.
- `risk_source`: static rule, tool preflight, provider error, or operator
  policy.
- `blocked_reason`: stable machine-readable reason.
- `suggested_route`: the correct proposal/tool path when a request is blocked.

These fields are advisory until the outer EgoOperator gate admits an action.

### Completion Claim Inputs

Reusable verifier outputs should be small and replayable:

- `verifier`: file_write, html_effect, command_result, web_fetch_result, or
  custom local verifier.
- `target`: path, url, command id, or proposal id.
- `passed`: boolean.
- `reason`: stable reason such as target_missing, expected_not_found, timeout,
  blocked, or verified.
- `evidence`: bounded facts, not long raw output.

Visible replies may summarize this evidence, but cannot claim completion if the
verifier fails or is unavailable.

### Trace And Replay Inputs

Trace rows should remain append-only JSONL and include:

- user turn / tool proposal / approval decision / lease / execution result.
- normalized path or command where applicable.
- risk and gate decision.
- verifier output.
- compact digest for long payloads plus full trace reference.

This keeps old EgoCore replay strengths while avoiding a second evidence ledger.

### Transport Envelope

If a non-CLI transport is added later, use a small envelope instead of importing
Telegram runtime:

- `status`
- `delivery_kind`
- `request_id`
- `turn_id`
- `reply_text` or `summary`
- `metadata`
- `trace_reference`

The transport envelope must not own memory, tool permission, or reply policy.

## Extraction Order

1. Add risk hints and completion verifiers to EgoOperator gate/eval surfaces.
2. Harmonize trace/replay fields with existing proposal, approval, lease, and
   execution records.
3. Add progress-event style operator digest only after it can be generated from
   real runtime stages.
4. Keep transport envelopes as reference-only until CLI and human-trial UX are
   stable.
5. Keep semantic routers and verbalizers as regression examples, not reusable
   runtime primitives.

## Non-Goals

- No legacy code import.
- No changes to `EgoCore`, `OpenEmotion`, or `ego_desktop_lab`.
- No program-state or evidence-ledger mutation.
- No claim of durable memory efficacy, live autonomy, runtime efficacy,
  independent awareness, or consciousness.

## Rollback

Remove this file and the link from `ALGORITHM_INVENTORY.md`. No runtime state,
memory, or legacy code is changed by this map.
