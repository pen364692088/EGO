# External Agent Memory Architecture Scan

Status: `external research / EgoOperator memory primitive input`

Issue: `#64 Research: GitHub agent memory architecture scan`

Scan date: `2026-05-20`

Claim ceiling: `EgoOperator external memory-pattern scan local candidate`.

This scan records reusable agent-memory patterns from current public projects
and docs. It does not add dependencies, change EgoOperator memory behavior, or
claim durable learning efficacy.

## Structure Risk Check

- Real target: find memory design patterns that improve user-perceived
  continuity without importing a second memory authority.
- Main risk: copying a vector DB, hosted memory API, or external framework would
  bypass EgoOperator's operator-approved memory contract and create state drift.
- Contract first: every imported memory idea must fit `candidate -> review ->
  core/hot/cold -> trace -> feedback`; LLM output can propose memory, but cannot
  directly promote canonical state.
- Counterexample gate: if a memory layer makes EgoOperator confidently recall a
  stale or unapproved fact, the import is wrong.
- Current validation: research-only. It can guide future issues but cannot
  prove durable memory, stable user benefit, live autonomy, or consciousness.

## Source Scan

| Project / docs | Observed memory pattern | Reusable idea | EgoOperator import stance |
| --- | --- | --- | --- |
| [Letta / MemGPT](https://github.com/letta-ai/letta), [Letta API docs](https://docs.letta.com/guides/get-started/intro) | Stateful agents with explicit memory as a first-class system concern; Letta Code mentions local memory and skills/subagents; the API docs frame agents as remembering, learning, and improving over time. | Treat memory as part of the agent contract, not only prompt stuffing. Keep memory visible/editable to the operator. | `rewrite`: adopt explicit memory surfaces and review UX, not the full Letta runtime or hosted API. |
| [LangChain / LangGraph long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory) | Long-term memory persists across threads, stored as JSON documents by namespace/key with optional cross-namespace search. | Namespaces and stable keys are useful for separating user, task, preference, and runtime memories. | `keep concept`: use JSONL/Markdown now; future store must preserve namespace/key and path-level traceability. |
| [Mem0](https://github.com/mem0ai/mem0) | Dedicated memory layer with add/search APIs, filters such as user id, hybrid retrieval, CLI, and integration skills. | Retrieval should be scoped by user/agent/run metadata and should expose add/search as clear operations. | `rewrite later`: no vector DB dependency in v1; import metadata/filter contract and integration-test discipline. |
| [CrewAI memory](https://docs.crewai.com/en/concepts/memory) | A unified memory API that infers scope/category/importance on save and ranks recall by semantic similarity, recency, and importance. | Recency + importance + relevance is a good hot-context ranking model. | `keep concept`: implement deterministic scoring first; LLM-inferred importance must stay candidate-only until reviewed. |
| [AutoGen memory/RAG](https://microsoft.github.io/autogen/0.6.4/user-guide/agentchat-user-guide/memory.html) | Agents can attach memory components such as persistent vector stores; memory returns retrieved chunks and the agent state is updated by agent calls. | Memory components should be explicit attachments, with lifecycle/cleanup and retrieval thresholds. | `reference-only`: avoid hidden agent-state mutation; use retrieval thresholds and explicit close/cleanup discipline. |
| [OpenHands persistence](https://docs.openhands.dev/sdk/guides/convo-persistence) | Conversation persistence stores base state, event files, tool outputs, agent status, iteration count, stuck detection settings, and usage statistics. | Event-sourced conversation persistence and per-event files improve replay and debugging. | `keep concept`: EgoOperator should keep trace/event replay separate from core memory and include stuck/loop signals. |
| [smolagents](https://github.com/huggingface/smolagents) | The agent loop adds task and execution logs to agent memory; tools run through code actions, with strong sandbox warnings. | Execution logs can be operational memory, but action memory must be separated from durable user memory. | `reference-only`: useful for short-term run memory and sandbox cautions; do not use code-action memory as core continuity. |

## Cross-Project Pattern Synthesis

### Pattern 1: Memory Is A Governed Store, Not Just Context

Strong systems separate storage from prompt injection. Letta and LangGraph make
memory an explicit platform/store concern; OpenHands separates event history
from state. EgoOperator should keep:

- raw history: append-only, not automatically prompt-visible.
- candidate memory: proposed facts/preferences/lessons.
- core memory: operator-approved.
- hot context: scored and traceable injection.
- cold archive: retained but normally not injected.

### Pattern 2: Namespace And Metadata Beat A Single Memory Blob

LangGraph namespace/key storage and Mem0 filters both point to the same
contract: memories need stable ownership and scope. EgoOperator should avoid a
single unstructured `MEMORY.md` as the only long-term shape. Future schema:

- `namespace`: user, task, preference, operator, runtime, project.
- `key`: stable correction/replacement target.
- `source`: user explicit, operator approval, scripted import, candidate
  compaction.
- `confidence`: deterministic or reviewer-backed.
- `status`: candidate, core, pinned, archived, rejected.
- `trace_ref`: where the memory came from.

### Pattern 3: Retrieval Needs A Gate And A Budget

CrewAI's recency/importance/relevance mix and Mem0's scoped search point toward
bounded hot-context retrieval. EgoOperator should inject memory only when:

- the memory is approved/pinned or meets an explicit relevance threshold.
- the query/task asks for the memory or benefits from continuity.
- the injected packet fits a small token/character budget.
- the reply can cite that the memory is candidate-local, not global authority.

### Pattern 4: Write Path Is The Real Risk

Most memory drift comes from unfiltered writes, not lack of storage. EgoOperator
should keep write-path filtering stricter than recall:

- explicit `/remember` and `/memory_approve` stay direct promotion gates.
- LLM extraction remains candidate-only.
- contradictions should quarantine stale facts before new facts become hot.
- automatic compaction can produce episodic summaries and candidate updates, not
  core memory.

### Pattern 5: Trace/Event Store Is Not Core Memory

OpenHands and smolagents show why execution history is useful. But tool logs,
approval results, stuck detection, and iterations are operational trace, not
identity/user memory. EgoOperator should continue separating:

- `agent_trace.jsonl`: replay/debug truth.
- session memory: current conversation state and approval results.
- operator memory: reviewed long-term continuity.

## Recommended EgoOperator Follow-Up Issues

1. `EgoOperator: memory namespace/key schema v1`
   - Add metadata around existing memory records without changing runtime
     behavior.
   - Observation class: `deterministic_local`.

2. `EgoOperator: hot-context retrieval budget and reason trace`
   - Make context injection report why each memory was included or excluded.
   - Observation class: `scripted_real_entry`.

3. `EgoOperator: candidate-memory write-path audit pack`
   - Add regressions for stale fact correction, unapproved extraction, and
     contradiction quarantine.
   - Observation class: `deterministic_local`.

4. `EgoOperator: memory replay/debug separation contract`
   - Ensure trace/session facts can answer "what happened" without promoting to
     core memory.
   - Observation class: `deterministic_local`.

## Import Rules

- Do not add vector DB, hosted memory API, MCP memory, or external framework in
  this phase.
- Do not allow LLM-generated memory to enter core/hot context without a gate.
- Do not make trace replay a memory authority.
- Do not claim consciousness, independent awareness, live autonomy, durable
  learning, or stable user benefit from these patterns.

## Rollback

Delete this scan and any link from `ALGORITHM_INVENTORY.md`. No runtime code,
memory files, or external dependencies are changed by this issue.
