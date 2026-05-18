# MVP13 — Persistent Self-Model

## 1. Purpose

MVP13 introduces a persistent self-model that can survive across
time, sessions, and internal cycles.

The goal is not merely to generate self-descriptive text.
The goal is to maintain a structured, inspectable, updateable
representation of the system's own state, tendencies, constraints,
and continuity.

## 2. Core Problem

Before MVP13, the system may generate developmental candidates
and internal cycles, but it does not yet maintain a stable
cross-time model of "self".

Without a persistent self-model:
- identity is reconstructed ad hoc
- behavioral continuity is fragile
- long-horizon adaptation cannot be reliably grounded
- self-description can drift from actual internal state

## 3. Scope

MVP13 focuses on:
- persistent self-model storage
- update rules
- continuity constraints
- identity invariants
- drift detection
- replayable self-model transitions

MVP13 does NOT yet focus on:
- endogenous drives as primary behavior source
- reflective counterfactual self-analysis
- open-ended developmental growth

## 4. Architectural Position

Layer 1 — Governance Shell  
Layer 2 — Proto-Self / SRAP  
Layer 3 — Developmental Core Sandbox  
Layer 4 — Persistent Self-Model

The self-model is fed by lower layers but does not override
governance authority.

### 4.1 Formal Owner

As of Step04C, the formal owner for MVP13 self-model semantics is:

- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/schemas/self_model.schema.json`

The older `emotiond/self_model/*` line remains historical and comparative
evidence only. It can inform migration or future extension work, but it is
not the formal owner for MVP13 contract claims, roadmap state, or future
behavioral influence proof.

### 4.2 Current Minimal Owner Contract

The current formal owner contract is centered on:

- `identity_handle`
- `capabilities`
- `limitations`
- `active_goals`
- `standing_commitments`
- `tool_authority_boundary`
- `dependency_map`
- `confidence_by_domain`
- `known_unknowns`
- `created_at / last_modified_at / modification_audit_trail`

These are the only fields that Step04C allows downstream proof harnesses to
treat as authoritative MVP13 self-model state.

## 5. Mandatory Principles

- self-model must be structured, not purely textual
- updates must be audit-logged
- changes must be replayable
- identity invariants must be preserved unless explicitly revised
- self-model outputs are evidence-backed, not free-form claims
