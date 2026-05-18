# Future Runtime Shadow/Event Tap Contract

This document is a future integration spec only. It is not an implementation
task for the current slice.

## Purpose

Let the lab observe runtime events later without becoming a runtime authority.
The first bridge must be a shadow/event tap, not a reply path.

## Allowed

- Read copied event summaries from a runtime/channel boundary.
- Build a lab-only `AgencyDecisionView`.
- Compare lab-selected behavior options against the runtime decision as shadow
  diagnostics.
- Write lab-local shadow artifacts only when a task explicitly asks for them.

## Blocked

- No mutation of EgoCore runtime state.
- No mutation of OpenEmotion state.
- No Telegram send, file operation, system command, GUI action, or external
  message.
- No replacement of `ResponsePlan`, `DecisionView`, transport gates, or
  OpenEmotion subject semantics.
- No formal evidence admission from shadow output alone.

## Promotion Gate

Before any runtime influence is proposed, the lab must already have deterministic
proof that:

- outcome feedback changes next-cycle ranking under replay,
- behavior option selection is proposal-only and gate-bounded,
- affective / drive pressure can shift options without bypassing gates,
- shell/DecisionView surfaces explain the change without recomputing decisions,
- no external action is executed.
