# Self-Model State Schema

## 1. Canonical Owner

As of Step04C, the formal MVP13 self-model contract is defined by:

- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/schemas/self_model.schema.json`

The older `emotiond/self_model/*` line is no longer the semantic owner for
MVP13 stage claims. It remains:

- historical evidence
- migration reference
- comparative/shadow material

but it must not be used as the primary contract source for roadmap state or
behavioral influence proof.

## 2. Current Top-Level Formal Contract

The current formal owner contract contains these top-level fields:

- `schema_version`
- `identity_handle`
- `capabilities`
- `limitations`
- `active_goals`
- `standing_commitments`
- `tool_authority_boundary`
- `dependency_map`
- `confidence_by_domain`
- `known_unknowns`
- `created_at`
- `last_modified_at`
- `modification_audit_trail`

## 3. Behaviorally Relevant Owner Fields

For future MVP13 behavioral influence proof, the allowed authoritative levers
are the fields that already exist on the formal owner contract:

- `active_goals`
- `standing_commitments`
- `confidence_by_domain`
- `capabilities`
- `limitations`

### 3.1 Minimal Owner-Backed Decision Surface

As of Step04E, the first formal-owner-backed downstream decision surface is:

- `confidence_by_domain["action:<action>"]`
- `confidence_by_domain["action.<action>"]`

These namespaced entries are interpreted as structured action confidence
signals for the real mainline action scoring path. This choice stays inside
the converged formal owner contract, keeps the signal numeric and replayable,
and avoids re-promoting legacy-only behavioral tendency fields.

Naming rule:

- the namespace must be `action:<action>` or `action.<action>`
- `<action>` must match a real mainline action in `emotiond/core.py::ACTION_SPACE`
- other arbitrary confidence keys must not be used as formal MVP13 behavioral
  proof levers unless separately normalized into the contract

These are the fields whose controlled intervention may later be used to prove
that the persistent self-model changes downstream behavior.

### 3.2 Current Minimal Formal Proof Path

As of Step04F, the minimal formal proof path for MVP13 behavioral influence is:

- API entry: `POST /decision/target?test_mode=true`
- target scope: same `target` + same `target_id`
- intervention lever:
  - `confidence_by_domain["action:<action>"]`
- downstream decision point:
  - `emotiond.core.generate_explanation_v31()`
  - `emotiond.core.select_action_with_explanation_v31()`
  - `emotiond.core.score_action_with_target()`

The proof contract for this path is:

- hold base predictions and relationship state fixed
- intervene only on the formal owner action-confidence surface
- show downstream action change on the same decision point
- exclude legacy-only `emotiond/self_model/*` fields from the causal path

## 4. Legacy / Migration Candidates

The following structures appear in the older `emotiond/self_model/*` line and
may still be useful as migration references, but they are not Step04C formal
owner fields:

- `identity_core`
- `stable_constraints`
- `behavioral_tendencies`
- `active_tensions`
- `long_horizon_orientations`
- `continuity_trace`
- `revision_history`
- `SelfModelManager`

If any of these are needed for future formal proof, they must first be
explicitly migrated into `openemotion/self_model/*` or otherwise redefined in
the formal owner contract.

## 5. Convergence Rule

From Step04C onward:

- proof harnesses must consume the formal owner contract
- roadmap state must cite the formal owner contract
- legacy fields may inform migration planning, but not formal promotion claims
