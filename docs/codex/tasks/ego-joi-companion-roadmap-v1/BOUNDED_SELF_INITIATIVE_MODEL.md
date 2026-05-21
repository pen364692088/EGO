# EgoOperator Bounded Self-Initiative Model

## Positive Mechanism Goal

Build a bounded self-initiative mechanism for EgoOperator companion use: the agent can notice a useful next move, explain why it would help, and propose a time-bounded follow-up or action while preserving operator approval, expiry, trace, and cancellation.

This is an operational initiative layer for companionship and task continuity. It lets EgoOperator sound like it has judgment and care in the interaction, without making the LLM the owner of external action, memory mutation, or canonical state.

## Initiative Primitive

For companion-facing and operator-facing turns, initiative has five stages:

1. `sense`: notice a user-authorized opportunity for follow-up, check-in, reminder, research, file work, or emotional support.
2. `frame`: explain the reason in user-facing language, not as an internal policy dump.
3. `propose`: produce a bounded proposal with action, reason, expiry, cancellation path, and traceable payload.
4. `gate`: runtime approval, permission lease, memory gate, or tool gate decides whether the proposal can mutate anything.
5. `settle`: record result as session evidence or pending candidate; do not turn it into core memory or background action without the matching gate.

## Ownership Contract

| surface | owner | allowed initiative | forbidden overreach |
| --- | --- | --- | --- |
| follow-up / check-in | `PermissionBroker` heartbeat proposal | propose a bounded heartbeat with reason and due time | sending or scheduling unbounded messages without approval |
| files / commands / web | runtime transaction gate | propose a tool action and wait for `/approve` | self-authorizing side effects |
| memory | operator memory gate | propose or create candidate memory for review | writing core memory from inference alone |
| relationship context | session context | carry recent shared context and suggest a gentle next beat | claiming a real-world relationship commitment |
| task board | GitHub Project/autopilot contract | propose next issue or closeout packet | closing high-impact or human-required issues without evidence |

## Scripted Acceptance Signals

- Explicit follow-up requests produce a bounded proposal with reason, expiry, and cancellation path.
- Ambiguous "be more proactive" requests do not start unbounded background behavior.
- Due heartbeat entries become candidate follow-up messages, not autonomous claims of independent action.
- Tool, file, web, command, and memory mutations still route through their existing gates.
- Agent self-voice can say "I would suggest..." or "I want to keep this thread from getting lost" while still making the proposal auditable.

## Rollback

Remove this contract, `bounded_self_initiative_pack.json`, and the validation wiring. No runtime state, program state, evidence ledger, or legacy code is changed by this contract.
