# EgoOperator Companion Relationship Continuity Contract

## Positive Mechanism Goal

Build a bounded relationship-continuity mechanism for EgoOperator companion use: the agent should carry shared moments, user naming, roleplay relationship context, approved preferences, and user corrections through the current interaction without turning every signal into permanent core memory.

This is an operational continuity layer for companionship and creative immersion. It is not a claim about real consciousness, durable memory efficacy, or stable user benefit.

## Continuity Layers

| layer | owner | prompt use | write rule | example |
| --- | --- | --- | --- | --- |
| session shared moment | `AgentRuntime` conversation/session context | bounded hot context while relevant | append-only turn/session state; no core memory write | "we planned to go out on 520" |
| user identity/name | operator memory core only when explicit | hot context when greeting/identity intent is relevant | `/remember`, `remember_note`, or approved candidate only | "call me 流月" |
| companion self-name | `EgoOperator/identity/self_identity.json` | every prompt as short identity anchor | first-run naming, `/self_name`, or explicit set_self_name tool only | "由乃" |
| preference candidate | candidate memory | reviewable, not automatically permanent | auto candidate only; requires `/memory_approve` for core | "warmer companion tone" |
| correction trace | candidate/core conflict quarantine + session note | latest correction wins in session | correction may archive stale candidate; core changes still gated | "roleplay calls me 博士, real chat calls me 流月" |
| roleplay relationship context | session roleplay context | scene-local only | no memory write unless explicit operator intent | "Skadi and Doctor scene" |

## Boundary Contract

- LLM may infer, propose, and express relationship continuity in the current conversation.
- LLM must not directly write core memory, self-name, task state, or canonical program state.
- Candidate memory may be created from strong preference/correction signals, but promotion to core remains operator-gated.
- Corrections should take precedence over stale candidates in hot context.
- Roleplay context stays in-scene until the user explicitly exits roleplay.
- Runtime must not introduce keyword-first routing or a prompt-copy table for these cases.

## Scripted Acceptance Signals

- User nickname carryover is stable after explicit memory approval or explicit `/remember`.
- Shared moments from recent turns can be referenced without permanent memory writes.
- Preference carryover creates reviewable candidate memory, not ungated core memory.
- Corrections supersede stale candidate context and do not confuse user name with agent self-name.
- Roleplay relationship context remains session-local and does not pollute ordinary identity.

## Rollback

Remove this contract, `companion_relationship_continuity_pack.json`, and the validation wiring added for this issue. No runtime state, program state, evidence ledger, or legacy code is changed by this contract.
