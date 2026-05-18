# EGOCORE_RUNTIME_V2_CLEANUP_ROADMAP.md

> Status: Proposed mainline roadmap
> Owner: EgoCore runtime
> Scope: Runtime v2 kernel cleanup, contract hardening, adapter slimming, real-effect closure
> Reference Direction: nanobot's thin-host / strong-loop / clean-interface philosophy
> Non-Goal: copy nanobot mechanically or collapse EgoCore ↔ OpenEmotion boundary

---

## 1. Executive Summary

EgoCore Runtime v2 has already crossed the line from pure idea to a runnable path: the v2 loop can drive a real hello.html modification flow and produce visible effect.

So the main problem is no longer:

- whether Runtime v2 should exist
- whether a single loop can work
- whether LLM-driven `plan/act/complete` is viable

The real problem now is:

**how to turn a runnable v2 path into a formal, stable, auditable runtime kernel that does not regress into split truth, fake completion, duplicate outbound replies, or adapter-local lifecycle logic.**

This roadmap defines the cleanup and refactor path needed to make Runtime v2 the formal main chain.

---

## 2. Architecture Card

### real goal
Build a minimal but formal Runtime v2 main chain based on:

- Thin Host
- Strong LLM Loop
- Formal Runtime Contracts

while preserving EgoCore as runtime authority and OpenEmotion as cognition authority.

### success criteria
Runtime v2 is considered structurally ready only when all of the following are true:

1. CLI and Telegram share the same runtime v2 loop.
2. LLM drives task progression through a structured action protocol.
3. Tool execution returns typed, auditable results.
4. Completion requires verifier-approved effect, not model confidence.
5. Delivery / dedupe truth is runtime-owned, not adapter-owned.
6. Telegram adapter becomes transport-only.
7. The hello.html real E2E path is stable.
8. Follow-up turns such as `你没改啊` continue the active task without phrase-table dependence.
9. No fake completion.
10. No duplicate outbound.

### current symptom
Runtime v2 already runs, but some truth is still too loose or mixed:

- loop logic is still too concentrated
- tool contract is still dict-shaped and loose
- verifier is still too weak for real effect validation
- busy/failure/completion outward semantics are not fully unified
- adapter thinning is incomplete
- old v1 modules still risk holding residual authority

### minimal decision point
Do not continue adding more heuristics to Runtime v1.
Instead, freeze Runtime v2 as the formal direction and clean it into a real kernel.

### current layer
接入 → 启用 → 局部生效

### chosen owner
**EgoCore**

### authority source
**EgoCore runtime** owns:
- request/task lifecycle
- execution truth
- completion truth
- delivery truth
- transport routing decision

**OpenEmotion** may provide:
- interaction interpretation
- social signal
- reply tendency
- expressive candidate

But OpenEmotion does **not** own:
- tool execution
- task lifecycle
- completion verification
- delivery dedupe
- runtime routing authority

### structural fix vs local patch
**Structural fix**

### required proof of effect
- hello.html true edit path passes through Runtime v2
- verifier gates completion
- Telegram follow-up stays on active task
- duplicate outbound is suppressed by runtime-owned delivery policy

### next minimal closure action
Formalize the v2 cleanup path in docs, then implement Phase 1: contract hardening around tool result, completion contract, and delivery policy.

---

## 3. What To Learn From nanobot

The point is **not** to imitate nanobot feature-for-feature.
The point is to learn the right architectural compression principles.

### 3.1 Learn: smallest reliable kernel
The best lesson from nanobot is not “be tiny at any cost”, but:

- keep the kernel small
- keep interfaces explicit
- let capabilities hang off contracts instead of polluting the loop
- avoid multi-place truth ownership

### 3.2 Learn: adapters should be thin
Telegram / CLI / other channels should be:

- ingress / egress
- retry / logging
- transport lifecycle

They should **not** own:

- active task truth
- completion truth
- delivery dedupe truth
- stale reply truth

### 3.3 Learn: capabilities should be brokered uniformly
Tool execution, verifier selection, and delivery policy should all be runtime-governed through clear interfaces, not scattered conditionals in random modules.

### 3.4 Learn: growth should happen at interfaces, not in the core loop
New tools, verifiers, and adapters should be plugged in through formal contracts. The loop should remain the orchestrator, not become a heap of special cases.

---

## 4. What NOT To Copy From nanobot

### 4.1 Do not flatten the dual-core boundary
EgoCore and OpenEmotion have a formal separation that nanobot does not need to preserve.

Do not “simplify” by moving cognition authority back into EgoCore runtime.

### 4.2 Do not chase line-count minimalism
Reducing code is good only when it reduces split truth and maintenance burden.
Reducing code by erasing needed runtime contracts is harmful.

### 4.3 Do not over-prioritize generalized plugin polish before core closure
The main need is not a beautiful generic plugin architecture.
The main need is:

- one runtime truth
- one delivery truth
- one completion truth
- one real E2E closure path

---

## 5. Current Runtime v2 Assessment

Current `app/runtime_v2/` already contains:

- `loop.py`
- `state.py`
- `action_protocol.py`
- `tool_broker.py`
- `verifier.py`
- `cli.py`

This means Runtime v2 already has a usable skeleton.

### 5.1 What is already good
1. A single loop exists.
2. Structured actions exist: `plan`, `act`, `ask`, `complete`, `chat`.
3. Minimal state exists.
4. Tool broker exists and now emits typed execution contracts.
5. Completion verification exists behind formal contract objects.
6. CLI and Telegram now consume typed turn results as the primary Runtime v2 interface.
7. Real task-path evidence exists.

### 5.2 What is still structurally weak
1. ingress-side Telegram heuristics have started moving into a bridge layer, but are not fully generalized yet.
2. `verifier.py` is stronger than before, but html/file effect verification can still deepen.
3. `state.py` still mixes runtime state with outward-notice state.
4. Delivery policy is partially extracted, but ingress/delivery bridge policy is not yet fully isolated across all channels.
5. Telegram adapter thinning is improved but not yet fully proven transport-only.
6. Old v1 modules still risk residual authority.

### 5.3 Current main risk
The biggest risk is not “v2 cannot run”.
The biggest risk is **v2 becoming another patch layer instead of becoming the formal kernel**.

---

## 6. Cleanup Principles

All Runtime v2 cleanup should obey these rules:

1. **One runtime truth source** for request/task/completion/delivery.
2. **Completion is harder truth than reply text**.
3. **Adapters transport; runtime governs**.
4. **LLM decides next action; host owns execution, verification, and delivery authority**.
5. **Contracts before proliferation**: add formal types/interfaces before adding more cases.
6. **Real effect beats local elegance**: changes are not done until real E2E remains correct.

---

## 7. Target Runtime v2 Shape

Recommended target shape:

```text
app/runtime_v2/
  action_protocol.py
  contracts.py
  state.py
  loop.py
  decision_engine.py
  transition.py
  tool_broker.py
  completion_contract.py
  delivery_policy.py
  effect_verifiers/
    __init__.py
    html_effect_verifier.py
    file_write_verifier.py
  adapters/
    openemotion_adapter.py
```

Optional later:

```text
  audit.py
  persistence.py
  task_binding.py
```

---

## 8. File-Level Refactor Direction

### 8.1 `action_protocol.py`
Current role is valid, but should be hardened.

#### Keep
- small action set: `plan`, `act`, `ask`, `complete`, `chat`
- strict JSON-only output requirement

#### Refactor
- move from loose optional-field dataclass parsing toward more explicit action models
- reject or normalize unknown / malformed fields more intentionally
- strengthen `complete` requirements
- optionally add `action_id` / `turn_id` / `correlation_id`

#### Target outcome
The action protocol stays simple, but becomes less ambiguous and easier to test.

---

### 8.2 `loop.py`
Current loop is useful, but too fat.

#### Today it mixes
- LLM call
- JSON retry handling
- state transition
- tool execution orchestration
- completion verification
- reply shaping

#### Refactor goal
Turn `loop.py` into an orchestrator only.

#### Move out
- decision logic → `decision_engine.py`
- state transition logic → `transition.py`
- delivery judgment → `delivery_policy.py`
- verifier routing → `completion_contract.py` / verifier registry

#### Target outcome
The loop becomes easy to read, easy to test, and hard to corrupt with future patches.

---

### 8.3 `state.py`
Current state model is useful but under-modeled.

#### Problems
- runtime state and outward-notice state are mixed
- delivery ledger is not formal
- active task state is not sharply separated from session state

#### Refactor goal
Split state into clearer layers.

#### Recommended models
- `RuntimeSessionState`
- `TaskState`
- `DeliveryLedger`

#### Move out of core task state if possible
- `last_busy_notice_at`
- `last_failure_notice_at`
- `last_failure_notice_text`

These likely belong in a delivery policy / ledger context.

#### Target outcome
State becomes explicit enough that “completed then busy again” or “duplicate final send” can be debugged as state bugs, not folklore.

---

### 8.4 `tool_broker.py`
This is one of the highest priority cleanup areas.

#### Current problem
The broker returns loose dicts. This works, but contracts remain soft.

#### Refactor goal
Introduce formal tool call / tool result contracts.

#### Recommended types
```python
ToolCall
ToolExecutionResult
ToolExecutionError
```

#### Minimum fields for `ToolExecutionResult`
- `success`
- `tool`
- `stdout`
- `stderr`
- `exit_code`
- `cwd`
- `timed_out`
- `truncated`
- `metadata`

#### Target outcome
Tool execution becomes stable input for verifier, delivery policy, audit, and tests.

---

### 8.5 `verifier.py` → `completion_contract.py` + `effect_verifiers/*`
This is the second highest priority cleanup area.

#### Current problem
Current verification is still mostly:
- target exists
- last tool succeeded
- expected substring optional

That is not enough to prevent fake completion in a durable way.

#### Refactor goal
Separate:
- completion contract declaration
- verifier selection
- concrete effect verification

#### New modules
- `completion_contract.py`
- `effect_verifiers/html_effect_verifier.py`
- `effect_verifiers/file_write_verifier.py`

#### Recommended formal result
```python
CompletionVerificationResult
```
with at least:
- `passed`
- `reason`
- `verifier`
- `target`
- `evidence`
- `warnings`

#### Target outcome
Completion becomes a host-governed truth gate, not a soft heuristic.

---

### 8.6 `delivery_policy.py`
This is the third highest priority cleanup area.

#### Why
Recent real behavior already showed the core issue:
- completed message sent
- then busy/progress-like reply sent
- then explanation-style reply sent

That means outward semantics are not fully unified.

#### Delivery policy should own
- ack/progress/ask/final/chat categories
- dedupe keys
- busy notice suppression
- failure notice suppression
- completion-after-final suppression
- challenge/follow-up handling after verified completion

#### Recommended model
```python
DeliveryDecision
DeliveryIdentity
DeliveryLedger
```

#### Hard rule
Adapter does not decide duplicate truth.
Runtime policy does.

---

### 8.7 Telegram adapter and old runtime modules
#### Telegram adapter should become
- transport-only
- ingress/egress glue
- no hidden lifecycle truth
- no hidden dedupe truth
- no hidden completion truth

#### Old modules should be downgraded
- `request_classifier.py` → signal extraction / hint-only
- `request_registry.py` → storage / lifecycle persistence support
- `agent_runner.py` → orchestration compatibility shell
- `telegram_bot.py` → transport glue only

#### Target outcome
Old v1 logic may remain temporarily for compatibility, but no longer owns formal runtime semantics.

---

## 9. Recommended New Contracts

### 9.1 Runtime action contract
Keep the small action vocabulary, but tighten schema behavior.

### 9.2 Tool contract
Formalize tool call and result models.

### 9.3 Completion contract
Formalize what effect must be observed before completion is allowed.

### 9.4 Delivery contract
Formalize dedupe identity and outward message kind.

### 9.5 OpenEmotion adapter contract
If Runtime v2 uses OpenEmotion in stage 1, keep it minimal and structured:

- EgoCore → OpenEmotion: structured event
- OpenEmotion → EgoCore: structured result

Do not rely on prompt-text pseudo-fields.

---

## 10. Phase Roadmap

## Phase 0 — Freeze Direction
### Goal
Stop v1 heuristic expansion and formally declare Runtime v2 as the mainline direction.

### Deliverables
- this roadmap accepted
- Runtime v2 declared as formal main chain direction
- no new unresolved phrase table / follow-up phrase-table growth unless temporary compatibility is explicitly marked

### Acceptance
- team aligns that Runtime v1 is in containment mode, not feature-growth mode

---

## Phase 1 — Contract Hardening
### Goal
Make Runtime v2 contracts formal enough that later refactors do not drift.

### Status
Substantially complete in development branch:
- typed `ToolExecutionResult`
- `CompletionContract`
- `CompletionVerificationResult`
- `DeliveryIdentity` / `DeliveryLedger`
- typed `RuntimeV2Reply` / `RuntimeV2TurnResult`

### Must do
1. Introduce typed `ToolExecutionResult`
2. Introduce `CompletionContract`
3. Introduce `CompletionVerificationResult`
4. Introduce `DeliveryIdentity` / `DeliveryLedger`
5. Tighten action protocol parse/validation rules

### Files likely added or changed
- `app/runtime_v2/contracts.py`
- `app/runtime_v2/tool_broker.py`
- `app/runtime_v2/completion_contract.py`
- `app/runtime_v2/delivery_policy.py`
- `app/runtime_v2/action_protocol.py`

### Acceptance
- unit tests for contract parsing and result normalization pass
- hello.html path still runs
- no contract ambiguity in the core loop

---

## Phase 2 — Loop Decomposition
### Goal
Make the loop small and durable.

### Status
In progress and largely landed in development branch:
- `decision_engine.py` extracted
- `transition.py` extracted
- loop now returns typed turn results as the formal interface

### Must do
1. Extract `decision_engine.py`
2. Extract `transition.py`
3. Reduce `loop.py` to orchestration
4. Move retry / malformed-action handling out of the core loop body

### Acceptance
- `loop.py` becomes clearly smaller
- decision, transition, and delivery logic can be tested separately
- no behavior regression in CLI hello.html flow

---

## Phase 3 — Effect Verification Upgrade
### Goal
Make completion effect-based, not rhetoric-based.

### Must do
1. Add `effect_verifiers/html_effect_verifier.py`
2. Use completion contracts to select verifier
3. Ensure `complete` cannot transition to verified completion without verifier pass

### Acceptance
- hello.html modification is verified by effect-oriented logic
- fake completion can be blocked in tests
- verifier result is auditable

---

## Phase 4 — Delivery Unification
### Goal
Stop duplicate / contradictory / post-completion noisy outbound behavior.

### Must do
1. Centralize delivery kind classification
2. Add dedupe keys and ledger-based suppression
3. Prevent `completed_verified` from emitting conflicting busy/progress notices
4. Define post-completion follow-up handling for challenge turns like `你没改啊`

### Acceptance
- no `completed` then `still working` contradiction
- no duplicate outbound for same semantic final
- challenge follow-up stays coherent

---

## Phase 5 — Adapter Slimming
### Goal
Make Telegram and CLI truly share one runtime truth.

### Status
Partially landed in development branch:
- CLI now consumes typed turn results directly
- Telegram runtime_v2 path now consumes typed turn results directly
- ingress-side Telegram heuristics have been extracted into `runtime_v2/telegram_bridge.py`
- Telegram runtime_v2 path now follows a clearer orchestration skeleton: ingress inspect -> pre-runtime action -> runtime loop -> result delivery
- remaining work is to further reduce adapter-owned typing/send lifecycle glue and move closer to transport-only behavior

### Must do
1. route Telegram through the same v2 kernel path as CLI
2. remove adapter-local lifecycle logic
3. remove adapter-local duplicate truth
4. remove adapter-local completion truth

### Acceptance
- Telegram adapter becomes transport-only in practice
- same core lifecycle behavior visible in CLI and Telegram
- no hidden Telegram-specific truth source remains

---

## Phase 6 — Legacy Downgrade and Cleanup
### Goal
Prevent Runtime v1 leftovers from silently reclaiming authority.

### Status
Started in development branch:
- Telegram Runtime v2 is the formal mainline path
- `_handle_with_new_runtime` is explicitly compatibility-only
- `_handle_with_legacy_router` is explicitly compatibility-only
- legacy-path warning logs are emitted when compatibility branches are used
- legacy runtime modules now carry explicit compatibility-only markers (`agent_runner.py`, `request_classifier.py`, `request_registry.py`)
- `docs/LEGACY_RUNTIME_MODULE_STATUS.md` records current formal-vs-legacy module roles

### Must do
1. mark legacy modules as compatibility-only
2. remove or bypass old authority-bearing heuristics
3. document which modules remain transitional and when they can be deleted

### Acceptance
- no important runtime truth depends on legacy modules
- legacy code paths are explicit, bounded, and removable

---

## 11. Implementation Priority Order

If work must be done in the smallest valuable order, use this sequence:

1. **delivery policy**
2. **completion contract + effect verifier**
3. **typed tool result**
4. **loop decomposition**
5. **Telegram adapter slimming**
6. **legacy downgrade**

Reason:
- delivery/completion/tool contract directly affect real correctness
- loop decomposition improves maintainability next
- adapter slimming matters after the core truth is stable
- legacy cleanup should follow the new authority path, not precede it

---

## 12. Test and Acceptance Plan

### 12.1 Unit
Must cover at least:
- action protocol parsing and malformed JSON handling
- tool result normalization
- completion contract behavior
- html effect verifier
- delivery dedupe / suppression rules

### 12.2 Integration
Must cover at least:
- CLI single-turn `plan → act → complete`
- CLI multi-turn continuation
- Telegram adapter using runtime v2 loop
- hello.html full edit chain

### 12.3 Real-machine E2E
Must cover at least:

#### Case A
Input:
`/home/moonlight/Project/Github/MyProject/TestProject/hello.html 配色不太好看,你换一个好看的颜色`

Expected:
- enters runtime v2
- LLM emits structured action(s)
- tool executes real modification
- verifier passes
- final reply is not fake

#### Case B
Follow-up:
`你没改啊`

Expected:
- binds to active task / active artifact
- continues without phrase-table dependence
- no wrong binding to stale chain
- no contradictory outbound replies

#### Case C
Social interruption during task
Expected:
- task state remains coherent
- delivery policy remains coherent
- no duplicate / conflicting final

---

## 13. Definition of Done

Runtime v2 cleanup is not done until all of the following are true:

1. Telegram and CLI share the same runtime v2 loop.
2. LLM is the main task progression decider.
3. Host retains execution, verification, state, and delivery authority.
4. request / completion / delivery truth remain inside EgoCore runtime.
5. OpenEmotion is not swallowed by runtime.
6. hello.html real path is stable.
7. `你没改啊` can continue the active task.
8. fake completion is blocked.
9. duplicate outbound is blocked.
10. related tests pass.
11. legacy authority leakage is removed or explicitly contained.

---

## 14. Non-Goals During This Cleanup

Do not turn this roadmap into:

- multi-agent expansion
- long-term planner buildout
- giant plugin-framework polishing
- broad memory redesign
- OpenEmotion deep integration expansion before runtime truth is stable

The purpose is **kernel cleanup and correctness closure**, not parallel scope explosion.

---

## 15. Recommended Immediate Next Action

Implement **Phase 1** first, in this exact order:

1. add `contracts.py`
2. formalize `ToolExecutionResult`
3. add `completion_contract.py`
4. add `delivery_policy.py`
5. adapt `loop.py` to consume these contracts without changing high-level behavior yet
6. re-run hello.html CLI + Telegram verification

This is the cheapest discriminative step that improves correctness without losing momentum.

---

## 16. One-Sentence Closure

The right lesson from nanobot is not “make EgoCore smaller”; it is:

**make EgoCore Runtime v2 into one clean kernel with explicit contracts and thin adapters, so real effect stays correct without falling back into patch-driven split truth.**
