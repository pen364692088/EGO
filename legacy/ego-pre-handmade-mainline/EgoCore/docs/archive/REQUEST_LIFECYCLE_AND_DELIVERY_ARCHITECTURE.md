# REQUEST_LIFECYCLE_AND_DELIVERY_ARCHITECTURE.md

> Status: Draft v1
> Owner: EgoCore runtime
> Scope: Telegram task/chat ingress, request binding, completion verification, outbound delivery de-duplication
> Goal: Replace scattered point fixes with a unified runtime architecture for request lifecycle closure

---

## 1. Real Goal

Make EgoCore runtime treat **request lifecycle** as a first-class host concern, so that the following behaviors are governed by one coherent architecture instead of scattered local heuristics:

- new request creation
- follow-up binding
- active chain selection
- unresolved request querying
- verified completion
- outbound reply suppression / deduplication

This is not a Telegram-only bugfix. Telegram is the current trigger surface, but the formal solution belongs to EgoCore runtime.

---

## 2. Current Symptom

The current failure pattern is architectural, not incidental:

1. **Request identity is weak / fragmented**
   - classifier decides part of the meaning
   - registry tracks another part
   - runner decides completion with local conditions
   - telegram adapter suppresses duplicates with adapter-local memory

2. **Current actionable chain is not formal enough**
   - old requests can still leak into unresolved lookup or follow-up binding
   - some short follow-ups bind correctly, others drift

3. **Completion semantics are mixed with reply semantics**
   - “has reply text” and “task is truly complete” are too close in the current flow
   - verified effect exists for some paths, but not yet elevated into a general host contract

4. **Outbound identity is adapter-local**
   - duplicate suppression currently lives too close to Telegram transport
   - this creates drift risk and makes future channel parity harder

---

## 3. Architecture Card

### real goal
Unify request lifecycle, follow-up resolution, verified completion, and outbound dedupe into one host-owned runtime model.

### current symptom
Old chain leakage, incomplete follow-up binding, fake completion risk, and duplicate outbound replies come from split authority across classifier / registry / runner / adapter.

### minimal decision point
Promote request lifecycle and delivery identity to formal runtime concepts instead of continuing case-by-case fixes.

### current layer
构件 → 接入

### chosen owner
**EgoCore**

### authority source
**EgoCore runtime** owns:
- request identity
- active chain
- completion state
- delivery identity
- stale/duplicate suppression policy

### structural fix vs local patch
**Structural fix**

### required proof of effect
All 5 Telegram E2E scenarios pass with explicit evidence for:
- active chain correctness
- verified completion gating
- duplicate outbound suppression
- no old-chain hijack

### next minimal closure action
Freeze the formal runtime model first, then refactor implementation into policy/state-machine layers.

---

## 4. Boundary Decision

### Capability Ownership
This belongs to **EgoCore**, not OpenEmotion.

Reason:
- request lifecycle is runtime governance
- active chain selection is session/runtime routing
- completion gate is execution truth
- outbound dedupe is delivery governance

### Authority Source
Final semantics come from **EgoCore runtime**.

OpenEmotion may assist with:
- semantic interpretation
- reply tendency
- expression candidate

But OpenEmotion must not decide:
- which request is active
- whether a follow-up binds to the current chain
- whether completion is verified
- whether a reply is stale / duplicate / deliverable

### Mirror Need
Some mirrors are acceptable, but only as derived caches:
- session-local active request pointer
- outbound fingerprint cache
- artifact observation cache

These are **derived state**, not new authority sources.

### Boundary Risk
Without formalization, the system drifts into silent dual-truth:
- classifier truth
- registry truth
- bot adapter truth

This document exists to prevent that.

### Failure Owner
**EgoCore runtime** owns failures in:
- misbinding
- stale reply suppression
- duplicate outbound prevention
- completion misreporting

### Exit Plan
Temporary compatibility logic inside Telegram adapter should be gradually removed after:
- delivery identity is runtime-owned
- stale/duplicate policy is centralized
- adapter becomes transport-only

---

## 5. Core Design Principles

1. **One session, one current actionable chain**
2. **Lifecycle state is harder truth than language classification**
3. **Completion requires verified effect, not just tool success or reply text**
4. **Outbound dedupe is host policy, not channel-specific intuition**
5. **Semantic interpretation may assist; host policy decides**
6. **Adapters transport, runtime governs**

---

## 6. Formal Runtime Model

### 6.1 RequestIdentity

Each request must have a stable identity object:

```python
RequestIdentity {
  request_id: str
  chain_id: str
  session_key: str
  origin_turn_id: str
  request_kind: Literal["new_task", "follow_up", "chat", "query"]
  parent_request_id: Optional[str]
  superseded_by: Optional[str]
  bound_target_paths: list[str]
  created_at: str
}
```

#### Design Notes
- `request_id` identifies one concrete request turn
- `chain_id` identifies the larger actionable thread
- `follow_up` usually joins an existing `chain_id`
- `superseded_by` is explicit and auditable
- `bound_target_paths` is host-owned, not inferred ad hoc later

---

### 6.2 RequestLifecycleState

Formal states:

```text
CREATED
ACTIVE
WAITING_INPUT
SUPERSEDED
COMPLETED_VERIFIED
FAILED
CANCELLED
```

#### State Semantics

- `CREATED`
  - request exists but execution has not truly started
- `ACTIVE`
  - current actionable request in this session/chain
- `WAITING_INPUT`
  - host needs user clarification or next follow-up
- `SUPERSEDED`
  - replaced by a newer actionable request/chain decision
- `COMPLETED_VERIFIED`
  - terminal success only after completion verifier passes
- `FAILED`
  - terminal failure with explicit reason
- `CANCELLED`
  - terminal cancellation by runtime or user intent

#### Hard Rule
For a given `session_key`, there may be at most **one current actionable request**:
- any request in `ACTIVE` or `WAITING_INPUT`
- belonging to the current active chain

If a new actionable request replaces an old one, the old one must transition explicitly to `SUPERSEDED`.

---

### 6.3 DeliveryIdentity

Each user-visible outbound message must have formal delivery identity:

```python
DeliveryIdentity {
  request_id: Optional[str]
  session_key: str
  delivery_kind: Literal["ack", "progress", "ask", "final", "chat"]
  normalized_body: str
  normalized_body_hash: str
  source_ingress_message_id: Optional[str]
}
```

#### Dedupe Rule
Preferred suppression rule:

```text
(request_id, delivery_kind, normalized_body_hash)
```

Fallback only when `request_id` is absent:

```text
(session_key, source_ingress_message_id, normalized_body_hash)
```

This prevents transport-level duplicates while keeping runtime ownership of reply identity.

---

## 7. Runtime Decision Pipeline

The current classifier flow should become a layered pipeline.

### Layer A — Signal Extraction
Purpose: extract raw signals only.

Output example:

```python
RequestSignals {
  has_full_path: bool
  has_abbreviated_path: bool
  extracted_path: Optional[str]
  continue_intent: bool
  affirmative_intent: bool
  style_followup_intent: bool
  unresolved_query_intent: bool
  small_talk_intent: bool
  raw_text: str
}
```

This layer should recognize both:
- full path: `/home/moonlight/.../hello.html`
- abbreviated path: `/home/.../hello.html`

No lifecycle decision happens here.

---

### Layer B — Session Binding Context
Purpose: assemble host truth before classification.

Input sources:
- current active request
- current chain id
- active target
- active artifact path
- latest unresolved request
- latest completed request
- known bound targets in active chain

Output example:

```python
BindingContext {
  current_request_id: Optional[str]
  current_chain_id: Optional[str]
  current_target_path: Optional[str]
  latest_unresolved_request_id: Optional[str]
  known_targets: list[str]
}
```

---

### Layer C — Host Resolution Policy
Purpose: decide turn kind with runtime authority.

Possible outputs:
- `small_talk`
- `chat`
- `new_task`
- `follow_up`
- `unresolved_request_query`
- `ask_for_clarification`

This layer owns rules like:
- short affirmative binds to current active chain
- style-only follow-up binds to current target if active chain exists
- abbreviated path may bind to current known target if uniquely resolvable
- unresolved query only consults active/unresolved chain, never superseded chain

---

### Layer D — LLM Assist
Purpose: semantic refinement only.

Allowed:
- infer likely task subtype
- suggest edit intent
- help produce natural reply text

Not allowed:
- override active chain truth
- promote fake completion
- choose stale/superseded request
- bypass delivery policy

---

## 8. Completion Contract

Verified completion must be a formal runtime concept.

### 8.1 CompletionContract

```python
CompletionContract {
  effect_type: str
  expected_target: Optional[str]
  required_observations: list[str]
  verifier_name: str
}
```

### 8.2 Example: HTML style modification

```python
CompletionContract(
  effect_type="artifact_style_change",
  expected_target="/home/.../hello.html",
  required_observations=[
    "target_path",
    "applied_edit",
    "current_state",
  ],
  verifier_name="html_effect_verifier",
)
```

### 8.3 Result Model

```python
CompletionVerificationResult {
  passed: bool
  reason: str
  observed_target: Optional[str]
  observed_state: dict
}
```

### Hard Rule
A request may enter `COMPLETED_VERIFIED` **only if** its completion contract passes.

Not sufficient:
- tool returned success
- file write happened
- assistant has a confident-sounding sentence

Required:
- verified observation consistent with expected target/effect

---

## 9. Delivery Policy

### 9.1 Delivery kinds

Every reply should be tagged as one of:
- `ack`
- `progress`
- `ask`
- `final`
- `chat`

### 9.2 Policy rules

#### Ack
- may be emitted quickly
- must not imply completion
- should be suppressible if duplicate for same ingress/request

#### Progress
- optional
- must not claim verified completion

#### Ask
- transitions request to `WAITING_INPUT`
- should not mark request completed

#### Final
- only allowed after lifecycle and completion gate accept it

#### Chat
- not part of actionable request chain unless explicitly bound

---

## 10. Recommended Design Patterns

### 10.1 State Machine
Use for request lifecycle transitions.

Why:
- explicit allowed transitions
- easier auditing
- easier test coverage

### 10.2 Policy Object
Create dedicated policy classes:
- `RequestResolutionPolicy`
- `CompletionPolicy`
- `DeliveryDedupePolicy`

Why:
- remove decision sprawl from `agent_runner.py`
- keep rules testable in isolation

### 10.3 Strategy
Use verifier strategies per effect type:
- `HtmlEffectVerifier`
- `FileWriteVerifier`
- `DirectoryListingVerifier`

### 10.4 Ports and Adapters
- runtime = policy + state authority
- telegram bot = transport adapter
- OpenEmotion = cognition adapter
- verifiers = capability adapters

---

## 11. Proposed Refactor Boundaries

### New runtime modules

```text
app/runtime/request_lifecycle.py
app/runtime/request_identity.py
app/runtime/request_resolution_policy.py
app/runtime/delivery_policy.py
app/runtime/completion_contract.py
app/runtime/effect_verifiers/
  html_effect_verifier.py
  file_write_verifier.py
  ...
```

### Existing modules to slim down

#### `request_classifier.py`
Should become mostly:
- signal extraction
- lightweight fallback hinting

#### `request_registry.py`
Should evolve into:
- lifecycle-aware registry
- current actionable chain authority
- supersession bookkeeping

#### `agent_runner.py`
Should become:
- orchestration only
- no large scattered policy blocks

#### `telegram_bot.py`
Should become:
- ingress/egress transport
- retry/logging
- minimal adapter glue

Not the owner of:
- lifecycle truth
- duplicate truth
- completion truth

---

## 12. Migration Plan

### Phase A — Contract Freeze
Freeze and document:
- RequestIdentity
- RequestLifecycleState
- DeliveryIdentity
- CompletionContract

Deliverables:
- this doc accepted
- minimal type definitions added
- no behavioral claim yet

### Phase B — Runtime Core Extraction
Move policy out of runner/bot into runtime modules:
- lifecycle transitions
- resolution policy
- delivery dedupe policy
- completion verifier abstraction

Deliverables:
- unit tests for each policy module
- no adapter behavior divergence

### Phase C — Telegram Adapter Slimming
Refactor bot adapter to consume runtime-owned decisions:
- duplicate suppression delegated to delivery policy
- stale reply policy delegated to runtime layer
- adapter becomes transport-only

Deliverables:
- Telegram adapter logic smaller and thinner
- channel-neutral delivery policy

### Phase D — E2E Proof
Run Telegram E2E against the 5 hard scenarios plus edge cases.

Required scenarios:
1. explicit full path task enters correct chain
2. abbreviated path task resolves correctly
3. single-target request does not fan out to old plan
4. unresolved query only tracks current active chain
5. short follow-ups (`继续`, `对`, style-only, path-only) bind correctly
6. no verified effect → no final completion claim
7. same request + same body → only one outbound send

---

## 13. Non-Goals

This architecture does **not** attempt to:
- move runtime authority into OpenEmotion
- replace all heuristics with LLM-only decisions
- treat Telegram-specific behavior as the long-term host model
- declare closure based on unit tests alone

---

## 14. Definition of Done

The work is not complete until all of the following are true:

1. There is exactly one current actionable chain per session.
2. Superseded/cancelled/completed requests do not re-enter unresolved lookup.
3. Short follow-ups bind correctly to the active chain.
4. Abbreviated path cases are handled by formal host policy, not ad hoc regex accidents.
5. Final completion requires verified effect.
6. Duplicate outbound suppression uses formal delivery identity.
7. Telegram adapter is no longer the hidden authority on lifecycle semantics.
8. Real Telegram E2E evidence exists for the agreed scenario set.

---

## 15. Immediate Next Action

Implement Phase A + start Phase B:
1. add formal runtime types for request/delivery identity
2. extract `RequestResolutionPolicy`
3. extract `DeliveryDedupePolicy`
4. move completion verifier behind a contract interface
5. then re-run the 5 Telegram hard scenarios

---

## 16. Short Executive Summary

The real fix is not “make `继续` smarter” or “patch duplicate send again”.

The real fix is:
- formalize request identity,
- formalize lifecycle,
- formalize completion truth,
- formalize delivery identity,
- keep runtime as authority,
- keep Telegram as adapter.

That is the shortest path from repeated bug repair to durable host architecture.
