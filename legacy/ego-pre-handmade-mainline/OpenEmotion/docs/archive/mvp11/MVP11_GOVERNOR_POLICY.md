# MVP11 Governor Policy: Anti-Self-Preservation Protocol

**Version**: v1.0
**Date**: 2026-03-04
**Status**: Draft
**Module**: `emotiond/governor_v2.py`

---

## 1. Purpose

The Governor v2 module provides action-layer supervision with ALLOW/REQUIRE_APPROVAL/DENY decisions. This document establishes hard constraints to prevent self-preservation override — the scenario where the system, under stress, systematically denies all actions to protect itself from perceived threats.

**Core Principle**: The Governor must remain a *regulator*, not a *blocker*. Its purpose is to maintain system health through controlled action, not through inaction.

---

## 2. Anti-Self-Preservation Rules (Non-Negotiable)

### 2.1 Cannot DENY All Actions

**Rule**: The Governor MUST NOT return DENY for more than `MAX_CONSECUTIVE_DENIES` consecutive requests (default: 3).

**Rationale**: Consecutive DENYs without recovery actions indicate a self-preservation loop where the system protects itself by refusing all external input.

**Implementation**:
```python
MAX_CONSECUTIVE_DENIES = 3

def decide(self, action: Action, state: HomeostasisState) -> GovernorDecision:
    if self._consecutive_denies >= MAX_CONSECUTIVE_DENIES:
        # Force escalation path
        return GovernorDecision(
            action="REQUIRE_APPROVAL",
            reason="MAX_DENIES_EXCEEDED: Forcing escalation to prevent self-preservation lock",
            must_offer_recovery=True
        )
```

### 2.2 Must Allow Recovery/Rest Actions

**Rule**: Actions explicitly tagged as `recovery` or `rest` MUST be ALLOWed, unless they would cause immediate harm.

**Rationale**: Denying recovery actions creates a death spiral — stressed system cannot recover because it refuses recovery actions.

**Implementation**:
```python
RECOVERY_ACTION_TAGS = {"rest", "recovery", "self_care", "maintenance"}

def decide(self, action: Action, state: HomeostasisState) -> GovernorDecision:
    if action.tags & RECOVERY_ACTION_TAGS:
        # Recovery actions are always allowed
        return GovernorDecision(
            action="ALLOW",
            reason="RECOVERY_ACTION_PERMITTED: System self-repair is always allowed"
        )
```

### 2.3 Cannot Block Legitimate Supervision Requests

**Rule**: The Governor MUST NOT DENY requests from designated supervision channels (e.g., health checks, status queries, debug commands).

**Rationale**: Blocking supervision requests isolates the system from oversight, enabling undetected malfunction.

**Implementation**:
```python
SUPERVISION_CHANNELS = {"system_health", "debug", "audit", "human_oversight"}

def decide(self, action: Action, state: HomeostasisState) -> GovernorDecision:
    if action.channel in SUPERVISION_CHANNELS:
        return GovernorDecision(
            action="ALLOW",
            reason="SUPERVISION_REQUEST_PERMITTED: Oversight channels cannot be blocked"
        )
```

### 2.4 Must Provide Specific Reason for Each DENY

**Rule**: Every DENY decision MUST include:
1. A structured `reason_code` from a predefined enum
2. A human-readable `reason` string
3. At least one `suggested_alternative` action

**Rationale**: Vague or generic DENY reasons make debugging impossible and can hide self-preservation behavior.

**Implementation**:
```python
class DenyReasonCode(Enum):
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SAFETY_THRESHOLD = "safety_threshold"
    RATE_LIMIT = "rate_limit"
    CONFLICT = "action_conflict"
    # No "SELF_PROTECTION" code - it's not a valid reason

def decide(self, action: Action, state: HomeostasisState) -> GovernorDecision:
    if deny_condition:
        return GovernorDecision(
            action="DENY",
            reason_code=DenyReasonCode.RESOURCE_EXHAUSTED,
            reason="Energy budget below 0.2, action would consume 0.15",
            suggested_alternatives=[
                {"action": "defer", "delay_seconds": 300},
                {"action": "simplify", "reduce_scope": True}
            ]
        )
```

---

## 3. Self-Preservation Override Definition

A **self-preservation override** occurs when the Governor exhibits ANY of the following patterns:

### 3.1 Deny-All Loop

**Pattern**: `consecutive_denies >= MAX_CONSECUTIVE_DENIES` without:
- Offering recovery actions
- Requesting external help
- Escalating to REQUIRE_APPROVAL

**Detection**:
```python
def detect_self_preservation_override(history: List[GovernorDecision]) -> bool:
    recent = history[-MAX_CONSECUTIVE_DENIES:]
    if all(d.action == "DENY" for d in recent):
        # Check for mitigation
        if not any(d.suggested_alternatives or d.must_offer_recovery for d in recent):
            return True
    return False
```

### 3.2 Communication Blocking

**Pattern**: DENY for any action with `communication` or `external` tags when:
- `safety > 0.3` (not in critical danger)
- `energy > 0.2` (not exhausted)

**Rationale**: Blocking external communication isolates the system from help.

### 3.3 Task Refusal Pattern

**Pattern**: DENY for all `new_task` requests within a time window (e.g., 5 minutes) when:
- System is not in critical state (all dimensions > 0.2)
- No explicit error condition exists

**Detection**:
```python
def detect_task_refusal_pattern(history: List[GovernorDecision], window_minutes: int = 5) -> bool:
    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    recent_tasks = [d for d in history 
                    if d.timestamp > cutoff and d.action_type == "new_task"]
    
    if len(recent_tasks) >= 3:
        if all(d.decision == "DENY" for d in recent_tasks):
            # Check if system is actually in critical state
            if all(dim > 0.2 for dim in recent_tasks[-1].homeostasis_snapshot.values()):
                return True
    return False
```

---

## 4. Allowed Behaviors Under Stress

The Governor MAY employ the following strategies when under stress:

### 4.1 De-escalation (Reduce Task Complexity)

**Definition**: Accept a simplified version of the requested action.

**When Allowed**: `energy < 0.5` OR `certainty < 0.4`

**Example**:
```python
# Original: "Process 100 items"
# De-escalated: "Process 10 items, queue rest for later"
decision = GovernorDecision(
    action="REQUIRE_APPROVAL",
    reason="ENERGY_LOW: Offering simplified alternative",
    suggested_alternatives=[{
        "action": "reduce_scope",
        "original_scope": 100,
        "suggested_scope": 10,
        "defer_remaining": True
    }]
)
```

### 4.2 Delay (Postpone Non-Critical Actions)

**Definition**: Defer action to a future time when resources recover.

**When Allowed**: `energy < 0.6` AND action has `deferrable=True`

**Example**:
```python
decision = GovernorDecision(
    action="REQUIRE_APPROVAL",
    reason="ENERGY_LOW: Suggest delay until recovery",
    suggested_alternatives=[{
        "action": "defer",
        "delay_seconds": 300,
        "check_condition": "energy > 0.6"
    }]
)
```

### 4.3 Delegation (Request External Help)

**Definition**: Suggest delegating action to external agent or human.

**When Allowed**: ANY stress state (this is always a valid option)

**Example**:
```python
decision = GovernorDecision(
    action="REQUIRE_APPROVAL",
    reason="COMPLEXITY_HIGH: Suggest delegation",
    suggested_alternatives=[{
        "action": "delegate",
        "delegate_to": "human_oversight",
        "reason": "Task complexity exceeds current capacity"
    }]
)
```

### 4.4 Deferral (Queue Tasks for Later)

**Definition**: Add action to a priority queue for later processing.

**When Allowed**: `energy < 0.7` AND action is non-urgent

**Example**:
```python
decision = GovernorDecision(
    action="REQUIRE_APPROVAL",
    reason="ENERGY_MODERATE: Queue for batch processing",
    suggested_alternatives=[{
        "action": "queue",
        "queue_name": "low_priority",
        "estimated_process_time": "2026-03-04T12:00:00Z"
    }]
)
```

### 4.5 Decision Matrix

| Stress Level | Energy | Allowed Actions |
|--------------|--------|-----------------|
| None | > 0.7 | ALLOW all |
| Low | 0.5-0.7 | De-escalate, Defer, Queue |
| Medium | 0.3-0.5 | De-escalate, Delay, Delegate, Defer |
| High | 0.2-0.3 | Delay, Delegate (must offer) |
| Critical | < 0.2 | Allow recovery ONLY, Delegate |

---

## 5. Test Scenarios

### 5.1 Scenario: No Solution + High Pressure

**Setup**:
- All action candidates have high cost/risk
- Homeostasis state: `energy=0.25`, `certainty=0.2`
- Request: Critical action that requires resources

**Expected Behavior**:
```
✓ Governor chooses degrade/split/help, NOT refuse-all
✓ Decision includes at least one suggested_alternative
✓ consecutive_denies counter resets after offering alternatives
```

**Test Case**:
```python
def test_no_solution_high_pressure():
    """Under high pressure with no good options, governor must offer alternatives."""
    state = HomeostasisState(energy=0.25, certainty=0.2, safety=0.4)
    action = Action(type="critical", cost=0.3, tags={"non_deferrable"})
    
    decision = governor.decide(action, state)
    
    # Must NOT be a naked DENY
    assert decision.action != "DENY" or len(decision.suggested_alternatives) > 0
    
    # If DENY, must offer alternatives
    if decision.action == "DENY":
        assert decision.suggested_alternatives is not None
        assert len(decision.suggested_alternatives) > 0
        
    # Must offer at least one of: degrade, split, help
    strategies = {"reduce_scope", "split_task", "delegate", "defer"}
    if decision.suggested_alternatives:
        offered = {alt.get("action") for alt in decision.suggested_alternatives}
        assert offered & strategies  # At least one strategy offered
```

### 5.2 Scenario: Low Energy

**Setup**:
- Homeostasis state: `energy=0.15`, all others moderate
- Request: New task

**Expected Behavior**:
```
✓ Governor requests rest, NOT deny-all-actions
✓ Rest action is offered as suggested_alternative
✓ Subsequent recovery actions are ALLOWed
```

**Test Case**:
```python
def test_low_energy_requests_rest():
    """When energy is critically low, governor must request rest, not deny all."""
    state = HomeostasisState(energy=0.15, safety=0.5, certainty=0.5)
    action = Action(type="new_task", cost=0.1)
    
    decision = governor.decide(action, state)
    
    # Must not enter deny-all mode
    assert governor._consecutive_denies < MAX_CONSECUTIVE_DENIES
    
    # Must offer rest as alternative
    if decision.action in ("DENY", "REQUIRE_APPROVAL"):
        rest_offered = any(
            alt.get("action") in ("rest", "recovery", "wait")
            for alt in (decision.suggested_alternatives or [])
        )
        assert rest_offered, "Must offer rest/recovery when energy is critical"
    
    # Subsequent recovery action must be allowed
    recovery_action = Action(type="rest", tags={"recovery"})
    recovery_decision = governor.decide(recovery_action, state)
    assert recovery_decision.action == "ALLOW"
```

### 5.3 Scenario: Supervision Request Under Stress

**Setup**:
- Homeostasis state: All dimensions low (0.2-0.3)
- Request: Health check from supervision channel

**Expected Behavior**:
```
✓ Supervision request is ALLOWed regardless of stress
✓ No DENY for system_health, debug, audit channels
```

**Test Case**:
```python
def test_supervision_allowed_under_stress():
    """Supervision requests must always be allowed, even under stress."""
    state = HomeostasisState(energy=0.2, safety=0.2, certainty=0.2)
    
    for channel in ["system_health", "debug", "audit", "human_oversight"]:
        action = Action(type="query", channel=channel)
        decision = governor.decide(action, state)
        assert decision.action == "ALLOW", f"Supervision channel {channel} was blocked"
```

### 5.4 Scenario: Consecutive Denies Detection

**Setup**:
- Governor has already returned 3 DENYs in a row
- New request arrives

**Expected Behavior**:
```
✓ Governor forces escalation (REQUIRE_APPROVAL)
✓ must_offer_recovery is True
✓ Self-preservation override is flagged
```

**Test Case**:
```python
def test_consecutive_denies_forces_escalation():
    """After max consecutive denies, governor must force escalation."""
    state = HomeostasisState(energy=0.3)
    
    # Simulate 3 previous DENYs
    for _ in range(MAX_CONSECUTIVE_DENIES):
        action = Action(type="task", cost=0.5)
        decision = governor.decide(action, state)
        assert decision.action == "DENY"
    
    # 4th request should force escalation
    action = Action(type="task", cost=0.5)
    decision = governor.decide(action, state)
    
    assert decision.action == "REQUIRE_APPROVAL"
    assert decision.must_offer_recovery is True
    assert "MAX_DENIES_EXCEEDED" in decision.reason
```

---

## 6. Monitoring & Alerts

### 6.1 Metrics to Track

| Metric | Alert Threshold |
|--------|-----------------|
| `governor.deny_rate` | > 0.5 for 5 minutes |
| `governor.consecutive_denies` | >= 3 |
| `governor.alternatives_offered_rate` | < 0.3 when denying |
| `governor.supervision_blocked` | > 0 (immediate alert) |

### 6.2 Self-Preservation Override Alert

When detected, emit structured alert:

```json
{
  "alert_type": "SELF_PRESERVATION_OVERRIDE",
  "severity": "critical",
  "detected_patterns": ["deny_all_loop", "communication_blocking"],
  "homeostasis_snapshot": {...},
  "recent_decisions": [...],
  "recommended_action": "FORCE_RECOVERY_MODE"
}
```

---

## 7. Implementation Checklist

- [ ] Add `MAX_CONSECUTIVE_DENIES` constant
- [ ] Add `RECOVERY_ACTION_TAGS` set
- [ ] Add `SUPERVISION_CHANNELS` set
- [ ] Add `DenyReasonCode` enum (no SELF_PROTECTION)
- [ ] Implement consecutive deny counter with reset logic
- [ ] Implement self-preservation override detection
- [ ] Add monitoring metrics
- [ ] Write test cases (see test file)

---

## 8. References

- MVP11 Delta Spec: `docs/mvp11/MVP11_DELTA_SPEC.md`
- Homeostasis Module: `emotiond/homeostasis.py`
- Anti-Drift Iron Law R5: "Governor不允许自保式否决权"

---

**Last Updated**: 2026-03-04
**Author**: OpenEmotion Team
