# External Agent Autonomy And Task-Loop Scan

Status: `external research / Codex Autopilot and EgoOperator active-layer input`

Issue: `#65 Research: GitHub agent autonomy and task-loop scan`

Scan date: `2026-05-20`

Claim ceiling: `EgoOperator/Codex Autopilot task-loop pattern scan local candidate`.

This scan compares current public agent-loop and human-in-the-loop patterns with
Codex Autopilot gates. It does not implement unattended code mutation,
background autonomy, or an EgoOperator active event loop.

## Structure Risk Check

- Real target: reduce operator burden while keeping action, memory, and claim
  authority inspectable.
- Main risk: a naked `while True: think -> act` loop would blur proposal,
  approval, execution, trace, and closeout evidence.
- Contract first: every loop needs step boundaries, interruption state,
  termination/stuck detection, scoped permissions, report output, and replay.
- Counterexample gate: if the loop closes a human-smoke, permission-expansion,
  program-state, or evidence-ledger issue without an operator gate, the design
  has failed.
- Current validation: research-only. This scan cannot prove autonomous
  development reliability, live autonomy, runtime efficacy, or consciousness.

## Source Scan

| Project / docs | Observed task-loop pattern | Reusable idea | EgoOperator / Autopilot import stance |
| --- | --- | --- | --- |
| [OpenAI Agents SDK HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/) | Runs can pause on approval interruptions, resume after approval/rejection, carry unresolved interruptions across passes, customize rejection text, and serialize durable `RunState`. | Approval is a first-class interruption state, not a prompt convention. Pending approvals can be partially resolved and resumed. | `keep concept`: keep PermissionBroker proposal/lease, add durable pending-work packets before any L4/L5 mutation. |
| [LangGraph human-in-the-loop](https://langchain-ai.lang.chat/langgraph/how-tos/human_in_the_loop/add-human-in-the-loop/) | Graph nodes can interrupt, persist graph state, and resume with human input. Multiple interrupt ids can be resumed with mapped values. | HITL should be a graph/state transition with explicit resume values. | `keep concept`: model future active layer as event graph/checkpoint, not infinite internal monologue. |
| [OpenHands agent architecture](https://docs.openhands.dev/sdk/arch/agent) | Agent is stateless between steps, event-driven, atomic per step, and pauses on pending confirmation. Security analyzer decides direct/log/confirm/block. | Autonomy is safer as single-step event processing with pending actions and explicit conversation status. | `keep concept`: Codex Autopilot should process one issue/step at a time and emit report/status events. |
| [OpenHands stuck detector](https://docs.openhands.dev/sdk/guides/agent-stuck-detector) | Detects repeated action-observation cycles, repeated errors, monologues, alternating loops, and context-window errors; can halt execution. | Loop safety should watch patterns in event history, not only count iterations. | `keep / extend`: existing `pause-check` can add tool/action/error repetition signatures. |
| [AutoGen termination conditions](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/termination.html) | Termination conditions include max messages, text mention, token usage, timeout, handoff, external termination, function-call termination, and custom functional checks. | Termination should be composable: budget, status, external stop, tool result, handoff, and custom predicate. | `keep concept`: Autopilot run-loop needs composable stop reasons and cannot rely on one max-issues cap. |
| [OpenHands persistence](https://docs.openhands.dev/sdk/guides/convo-persistence) | Conversations persist base state, event files, tool outputs, execution status, iteration count, stuck settings, and usage stats. | Long runs need a replayable event store and status snapshot, separate from durable memory. | `keep concept`: `.codex/autopilot/runs/` should stay run reports; do not promote reports into EGO memory or evidence ledger. |
| [smolagents](https://github.com/huggingface/smolagents) | ReAct loop stores tasks/execution logs in agent memory and warns that local code execution is not a security boundary. | Agent memory can preserve run context, but execution logs require sandbox/permission separation. | `reference-only`: useful for code-action efficiency ideas, but EgoOperator must not make local code execution a default autonomy path. |

## Pattern Synthesis

### Pattern 1: Autonomy Is Step-Based, Not Continuous Thought

The strongest designs expose a bounded `step()` or node transition. Each step
can:

1. read current event state,
2. propose or execute one bounded action,
3. emit an observation/report,
4. stop, pause, or continue under a budget.

This fits Codex Autopilot better than a hidden internal while loop.

### Pattern 2: Interruptions Are Data

Approvals and human input should be serializable records:

- `interruption_id`
- action/proposal payload
- risk/gate reason
- decision state: pending, approved, rejected, expired
- resume value
- trace/report reference

This mirrors EgoOperator's proposal/lease model and should guide future L4/L5
implementation.

### Pattern 3: Stop Reasons Need A Taxonomy

Autopilot should keep explicit stop reasons:

- no ready issue
- human_required
- protected path / dirty unsafe
- missing verify profile
- repeated failure / Zeno trap
- approval pending
- timeout/budget exhausted
- reviewer blocked
- external service unavailable
- program-state/evidence-ledger gate

This prevents a loop from treating every pause as "try harder".

### Pattern 4: Stuck Detection Should Use Event Signatures

OpenHands-style stuck detection suggests future Autopilot should detect:

- same issue selected repeatedly without new scoped diff
- same command/tool failure repeated
- same closeout blocked reason repeated
- alternating status changes without a new artifact
- repeated provider/context errors

Current `pause-check` covers repeated issue/stop-reason patterns; a future issue
should add tool/action/error signatures.

### Pattern 5: Reports Are The Operator UI

The operator should not inspect raw logs to know what happened. Every run needs:

- selected issue
- action attempted
- scoped diff summary
- verification profile and result
- stop reason
- claim ceiling
- next operator action
- trace/report path

This matches the existing `operator_digest` direction.

## Implications For Codex Autopilot

### Keep

- L0/L1 read/report/plan.
- L2 dirty-baseline scoped diff.
- L3 closeout oracle with hard-stop gates.
- L4 dry-run patrol only.
- L5 executor-check as a dry-run readiness gate.

### Extend Later

1. `Codex Autopilot: event-signature stuck detector`
   - Add repeated command/error/blocked-closeout signatures to `pause-check`.
   - Observation class: `deterministic_local`.

2. `Codex Autopilot: pending-work interruption packet`
   - Represent approvals/human smoke/stage cards as serializable pending work.
   - Observation class: `deterministic_local`.

3. `Codex Autopilot: single-step executor state machine`
   - Execute one low-risk deterministic issue step at a time, with stop reason
     and report emission before the next step.
   - Observation class: `scripted_with_llm_judge` or tighter.

4. `EgoOperator: active event-loop contract`
   - Model heartbeat/wake events as bounded proposals with budget, expiry,
     trace, and operator-visible report.
   - Observation class: `human_required` for user-perceived initiative.

### Do Not Import

- hidden infinite loops.
- unreviewed automatic issue closeout.
- default local code execution as an autonomy primitive.
- external task schedulers that bypass `.codex/project_contract.yaml`.
- "self-awareness" or "independent will" claims from loop mechanics.

## Rollback

Delete this scan and the `ALGORITHM_INVENTORY.md` link. No runtime code,
GitHub automation behavior, memory file, or external dependency is changed.
