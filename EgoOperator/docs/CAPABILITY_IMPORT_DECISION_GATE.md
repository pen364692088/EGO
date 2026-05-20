# Capability Import Decision Gate

Status: `EgoOperator primitive import contract / research closeout gate`

Issue: `#67 Research: reusable capability import decision gate`

Claim ceiling: `EgoOperator capability-import decision gate local candidate`.

This document defines how legacy or external capabilities may move from
research scans into EgoOperator implementation issues. It does not import any
runtime code, dependencies, providers, or memory stores.

## Structure Risk Check

- Real target: convert research findings into safe implementation candidates,
  not keep accumulating scans or import dependencies by enthusiasm.
- Main risk: a useful pattern becomes a second runtime, second memory authority,
  hidden semantic router, or unsupported evidence claim.
- Contract first: every imported capability must pass primitive, gate, trace,
  feedback, eval, and rollback checks before an implementation issue is opened.
- Counterexample gate: if a capability can change reply, memory, tool execution,
  or task status without EgoOperator's proposal/gate/trace path, it must be
  rejected or rewritten.
- Current validation: document/reviewer gate only; it cannot prove the imported
  capability works in real user operation.

## Inputs

Eligible inputs:

- Legacy maps:
  - `OPENEMOTION_SUBJECT_PRIMITIVE_MAP.md`
  - `EGOCORE_GATE_TRACE_TRANSPORT_MAP.md`
  - `EGO_DESKTOP_LAB_EVAL_HARNESS_MAP.md`
- External scans:
  - `EXTERNAL_AGENT_MEMORY_ARCHITECTURE_SCAN.md`
  - `EXTERNAL_AGENT_AUTONOMY_TASK_LOOP_SCAN.md`
  - `EXTERNAL_EMOTION_AWARE_ASSISTANT_UX_SCAN.md`
- Human-trial failure packets or GitHub issue comments with prompt, observed
  behavior, expected behavior, trace/report reference, and failure class.

Ineligible inputs:

- vague inspiration without a source reference.
- "looks useful" dependency imports.
- claims requiring program-state or evidence-ledger mutation.
- proposals that need real user benefit, autonomy, durable memory, or
  consciousness claims to pass.

## Decision Classes

| Class | Meaning | Allowed next step |
| --- | --- | --- |
| `accept_as_primitive` | The idea fits EgoOperator's existing contract and can be implemented with local deterministic or scripted evidence. | Create a narrow implementation issue with observation class, tests, rollback, and claim ceiling. |
| `rewrite_as_candidate_context` | The idea is useful only if it stays readonly/proposal-only. | Create an issue under subject/context/eval primitives; forbid direct state mutation. |
| `research_only` | Useful background but too broad, hosted, dependency-heavy, or not yet testable. | Keep as reference; do not create runtime implementation issue. |
| `discard_as_runtime_entry` | Would reintroduce semantic routing, template fallback, hidden memory writes, or bypass gates. | Add as negative regression material if useful. |
| `stage_card_required` | Requires permission expansion, program-state/evidence changes, mainline claims, memory promotion, external scheduler, or dependency adoption. | Stop and ask for operator Stage Card approval before any implementation. |

## Required Import Packet

Every proposed capability issue must include:

- `source`: legacy file/doc or external source URL.
- `candidate_capability`: one-sentence capability.
- `decision_class`: one of the classes above.
- `primitive_contract`: proposal, readonly context, eval, report, gate, trace, or
  memory candidate.
- `owner`: EgoOperator runtime, memory_system, primitives, scripts/autopilot, or
  docs/evals.
- `non_goals`: at least one explicit forbidden role.
- `acceptance_gate`: deterministic/scripted/human evidence requirement.
- `rollback`: files or behavior to remove.
- `claim_ceiling`: what cannot be claimed.

## Hard Stop Rules

Stop before implementation if any of these are true:

- introduces a new memory authority, vector DB, daemon, or hosted dependency.
- lets LLM output directly mutate core memory, tool state, task state, or
  canonical decisions.
- reintroduces keyword-first or semantic-router-first handling for normal user
  text.
- changes `docs/PROGRAM_STATE_UNIFIED.yaml` or `artifacts/evidence_ledger/**`.
- expands permissions, background execution, schedulers, or transport mutation.
- needs real human-perceived benefit to be considered done.
- claims consciousness, independent awareness, live autonomy, durable learning,
  therapy efficacy, runtime efficacy, or stable user benefit.

## Reviewer Gate

Before closing a `scripted_with_llm_judge` import decision issue, produce a
review packet with:

- selected source scan(s)
- proposed decision class
- proposed implementation issue(s)
- hard-stop scan
- verification output
- claim ceiling

Reviewer verdict can only be:

- `closeout_allowed`
- `revise_packet`
- `stage_card_required`
- `reject_import`

Reviewer cannot override hard-stop rules. If reviewer tooling is unavailable,
the issue remains open or is downgraded to deterministic research only.

## Initial Import Backlog

These are candidates, not implementation approval:

1. `EgoOperator: memory namespace/key schema v1`
   - Source: external memory scan.
   - Decision: `accept_as_primitive`.
   - Contract: metadata-only memory schema; no new store.

2. `EgoOperator: hot-context retrieval reason trace`
   - Source: external memory scan + existing memory system.
   - Decision: `accept_as_primitive`.
   - Contract: trace why memory was injected/excluded.

3. `Codex Autopilot: event-signature stuck detector`
   - Source: external autonomy/task-loop scan + existing pause-check.
   - Decision: `accept_as_primitive`.
   - Contract: control-plane detector only; no code mutation.

4. `Codex Autopilot: pending-work interruption packet`
   - Source: OpenAI/LangGraph HITL patterns.
   - Decision: `rewrite_as_candidate_context`.
   - Contract: serializable pending work; no automatic approval.

5. `EgoOperator: situation-grounded empathy eval pack`
   - Source: external emotion-aware UX scan.
   - Decision: `accept_as_primitive`.
   - Contract: scripted/human eval pack, not runtime emotion model.

6. `EgoOperator: emotional overreach negative gate`
   - Source: external emotion-aware UX scan + self-description honesty gate.
   - Decision: `accept_as_primitive`.
   - Contract: deterministic rejection of overclaim/dependency/diagnosis
     patterns.

7. `EgoOperator: progress-event operator digest`
   - Source: EgoCore progress events + Autopilot operator digest.
   - Decision: `rewrite_as_candidate_context`.
   - Contract: stage-derived digest only, no text-template ownership.

8. `EgoOperator: failure ticket import from human trial`
   - Source: ego_desktop_lab root-cause tickets and operator reports.
   - Decision: `accept_as_primitive`.
   - Contract: normalize prompt/expected/observed/failure class into issue or
     sample pack.

## Rejected Or Reference-Only Imports

- Semantic router as first runtime entry: `discard_as_runtime_entry`.
- Lab shell or console as EgoOperator user entry: `discard_as_runtime_entry`.
- Hosted memory API / vector DB dependency: `research_only` until Stage Card.
- Voice emotion API / Hume integration: `research_only` until a voice-layer
  Stage Card.
- Background scheduler that can send messages without operator-visible pending
  work: `stage_card_required`.

## Rollback

Delete this document and any link from `ALGORITHM_INVENTORY.md`. If follow-up
issues were created from it, close them as superseded or not planned. No runtime
files are changed by this gate.
