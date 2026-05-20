# OpenEmotion Subject Primitive Extraction Map

Status: `research inventory / proposal-only mapping`

Canonical source: GitHub issue `#60` and
`docs/codex/tasks/ego-experience-roadmap-bootstrap-v1/ROADMAP.md`.

Claim ceiling: `OpenEmotion subject primitive extraction map local candidate`.
This document does not claim consciousness, independent awareness, runtime
efficacy, stable user benefit, durable memory efficacy, or live autonomy.

## Structure Risk Check

- Real target: reuse useful OpenEmotion subject ideas in EgoOperator without
  importing a second daemon, state owner, or semantic router.
- Drift risk: OpenEmotion concepts can easily become a hidden authority source
  for memory, identity, emotion, or initiative if copied directly.
- Contract first: every extracted primitive must be `proposal-only` or
  `readonly context`; EgoOperator's gate, memory commands, trace, and operator
  approval remain the state mutation boundary.
- Counterexample gate: if a subject primitive makes the agent claim true
  consciousness, overread emotion, write memory without approval, or act without
  an operator-visible proposal, the extraction is invalid.
- Validation level: document/inventory only; implementation still needs focused
  deterministic tests and real operator samples.

## Mapping Table

| OpenEmotion concept | Legacy evidence surface | EgoOperator primitive | Allowed role | Forbidden role | Next extraction shape |
| --- | --- | --- | --- | --- | --- |
| Self-model / identity constraints | `emotiond/self_model/schema.py`, `schemas/self_model.schema.json`, `TASK_PROTO_SELF_KERNEL_V1.md` | `operational_self_model` in `primitives/subject_context.py` | Bounded role, capability, uncertainty, and commitment context | Proof of consciousness, independent awareness, or authority to rewrite identity | Add explicit source labels and expiry to each injected self-model field before any persistence beyond session. |
| Salience / episodic / narrative memory | `emotiond/memory/*`, `emotiond/episodic_memory.py`, `emotiond/narrative_memory.py` | `candidate_memory` / hot-context selection in `memory_system.py` | Rank candidate memories and propose review items | Direct `MEMORY.md` mutation or canonical EGO memory | Add salience scoring as a candidate-only review signal; promotion stays `/memory_approve` or explicit remember intent. |
| Appraisal dimensions | `emotiond/appraisal.py` (`goal_progress`, `expectation_violation`, `controllability`, `social_threat`, `novelty`) | `emotion_signal` and empathy style guidance | Tone calibration, next-step urgency, repair priority hints | Claiming the user's true emotion or deciding the final reply | Rewrite into a small bounded appraisal vector with confidence and evidence cues; keep `canonical_truth=false`. |
| Reflection / self-conflict | `emotiond/reflection.py`, `emotiond/reflection_engine/*`, `emotiond/meta_cognition.py` | reviewer/check proposal context | Suggest contradiction checks, missing evidence, or next verification | Auto-changing state, memory, identity, or final answer | Add a `reflection_proposal` record that must be consumed by reviewer/gate, not by direct reply mutation. |
| Initiative / intrinsic motivation | `emotiond/intrinsic_motivation.py`, `emotiond/cycle_autonomy.py`, `emotiond/rhythm_scheduler.py` | `primitives/initiative.py` bounded proposal | Suggest bounded follow-up or heartbeat proposals with budget/expiry | Background autonomous action or self-authorized outreach | Keep explicit operator consent and quiet-mode gates; no daemon loop without separate Stage Card. |
| Self-report alignment | `POLICIES/SELF_REPORT_ALIGNMENT.md`, `schemas/self_report_contract.v1.schema.json`, `response_intent_contract.v1.schema.json` | `self_description_honesty` guidance/evaluator | Prevent overclaims and keep descriptions operational | Letting subject state generate unverifiable first-person claims | Convert allowed/forbidden claim patterns into local self-description tests and reviewer prompts. |

## Extraction Order

1. **Self-description honesty and operational self-model** are already partially
   present in `primitives/subject_context.py`; continue with tests before adding
   persistence.
2. **Appraisal** should be next only as a bounded vector that improves response
   style. It must not override the user's explicit correction.
3. **Salience** can improve memory review and hot context, but promotion remains
   operator-approved.
4. **Reflection** belongs in reviewer packets and failure recovery, not the main
   reply path.
5. **Initiative** stays proposal-only until active event-loop gates and operator
   consent are separately accepted.

## Implementation Guard

Any future issue that imports OpenEmotion subject ideas into EgoOperator must
state:

- primitive name and schema version;
- source concept and source file family;
- whether it is readonly context, candidate memory, proposal, or gate input;
- exact state/memory/tool mutations that remain forbidden;
- trace fields that prove the primitive did not bypass gate/approval;
- claim ceiling, including explicit non-claims for consciousness and durable
  efficacy.
