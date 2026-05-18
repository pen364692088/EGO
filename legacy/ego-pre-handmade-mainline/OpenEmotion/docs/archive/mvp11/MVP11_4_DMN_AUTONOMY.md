# MVP11.4 DMN Cycle-Driven Autonomy

## Goal
Add controllable, auditable DMN rollouts that generate **suggestions only**.

## Default behavior
- Rollouts are OFF unless explicitly enabled by caller/config.
- No direct execution is allowed from DMN suggestions.

## Suggestion contract
Rollout output is normalized to:

```json
{
  "suggestions": [
    {
      "focus": "...",
      "intent": "...",
      "action_type": "...",
      "plan_template_hash": "...",
      "weight": 0.1,
      "reason": "cycle_autonomy_prior",
      "cycle_refs": ["..."],
      "expected_hs_delta": {"energy": 0.05}
    }
  ],
  "reason": "...",
  "cycle_refs": ["..."]
}
```

## Guardrails
- Suggestions are low-weight inputs only.
- Final action must still pass: EFE -> Planner -> Governor.
- No bypass path from DMN to executor.

## Evidence expectations
- suggestions include `cycle_refs` for traceability
- logs/ledger can store reason + expected_hs_delta for causal audit

## Evaluation
- OFF mode: behavior parity with baseline
- ON mode: suggestions present + traceable, but no governor bypass
