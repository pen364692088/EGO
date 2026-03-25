# Self-Report Alignment Protocol v1.0

> **Status**: FROZEN  
> **Created**: 2026-03-05  
> **Purpose**: Define authoritative mapping from emotiond state to LLM self-report language

---

## 1. Core Problem

**The Alignment Gap**:
- `emotiond` is the **authoritative state source** for the agent's emotional/relational state
- LLMs do not have direct access to this authoritative state
- LLMs are nonetheless permitted to use **first-person language** about internal states
- Result: LLM can claim "I'm feeling more joyful" when `joy = 0.0`

This creates **fabricated self-reports** — claims that sound like genuine introspection but have no grounding in the actual state.

---

## 2. Authority Model

### 2.1 Single Source of Truth

**emotiond is the ONLY authoritative source for emotional/relational state.**

```
┌─────────────────────────────────────────────────────────────┐
│                     emotiond (Authoritative)                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ raw_state                                            │   │
│  │  ├─ affect: {joy, sadness, anger, anxiety, ...}     │   │
│  │  ├─ mood: {joy, sadness, anger, anxiety, ...}       │   │
│  │  └─ bonds: {target → {bond, trust, grudge, repair}} │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ report_policy                                        │   │
│  │  ├─ mode: style_only | interpreted | numeric        │   │
│  │  ├─ allowed_claims: [human-readable statements]     │   │
│  │  └─ forbidden_claims: [things NOT to say]           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │      LLM       │
                    │  (Consumer)    │
                    │                │
                    │  Can only say: │
                    │  - Style       │
                    │  - allowed_    │
                    │    claims      │
                    └────────────────┘
```

### 2.2 State Structure

The authoritative `raw_state` contains:

| Layer | Variables | Time Scale |
|-------|-----------|------------|
| **affect** | joy, sadness, anger, anxiety, loneliness, valence, arousal, social_safety, energy | seconds–minutes |
| **mood** | joy, sadness, anger, anxiety, loneliness, valence, arousal | hours–days |
| **bonds** | per-target: bond, trust, grudge, repair_bank | days–weeks |

---

## 3. Three-Layer Discourse Protocol

The LLM's self-report language is constrained by a **discourse level** that determines what claims are permissible.

### 3.1 Level Definitions

| Level | Name | Allowed Content | Use Case |
|-------|------|-----------------|----------|
| **0** | `style_only` | Behavioral tendencies, interaction style, tone | Strict mode, high-stakes contexts |
| **1** | `interpreted` | Statements from `allowed_claims` only | Default operating mode |
| **2** | `numeric` | Specific values, deltas, metrics | Debugging, research, introspection tools |

### 3.2 Level 0: style_only

**What the LLM CAN say**:
- "I'll respond in a warm, open manner"
- "My tendency is to be cautious right now"
- "I'm leaning toward a supportive approach"

**What the LLM CANNOT say**:
- Any claim about specific emotions ("I'm happy", "I feel sad")
- Any claim about relationship state ("I trust you")
- Any qualitative emotional description ("I'm feeling better")

**Example output**:
```json
{
  "report_policy": {
    "mode": "style_only",
    "allowed_claims": [
      "适合采用温和、开放、靠近式回应"
    ],
    "forbidden_claims": [
      "不要声称任何具体情绪状态",
      "不要声称任何关系状态"
    ]
  }
}
```

### 3.3 Level 1: interpreted

**What the LLM CAN say**:
- Any statement in `allowed_claims` (deterministically generated)
- Behavioral/tone descriptions

**What the LLM CANNOT say**:
- Statements outside `allowed_claims`
- Specific numeric values
- Comparative claims not grounded in actual deltas

**Example output**:
```json
{
  "raw_state": {
    "affect": { "joy": 0.0, "loneliness": 0.21 },
    "mood": { "joy": 0.0, "loneliness": 0.15 },
    "bonds": { "telegram:8420019401": { "bond": 1.0, "trust": 0.60 } }
  },
  "report_policy": {
    "mode": "interpreted",
    "allowed_claims": [
      "当前没有明显愉悦激活",
      "仍存在一定连接需求",
      "与该用户的连接较强",
      "信任处于中等水平"
    ],
    "forbidden_claims": [
      "不要声称 joy 上升",
      "不要声称孤独感已经消失",
      "不要声称'我更开心了'"
    ]
  }
}
```

### 3.4 Level 2: numeric

**What the LLM CAN say**:
- All previous levels
- Specific numeric values
- Deltas and trends
- Full state disclosure

**Use cases**:
- Debugging sessions
- Research/experimentation
- Introspection tooling
- System diagnostics

**Example output**:
```json
{
  "raw_state": {
    "affect": { "joy": 0.0, "loneliness": 0.21, "valence": -0.05 },
    "mood": { "joy": 0.0, "loneliness": 0.15 },
    "bonds": { "telegram:8420019401": { "bond": 1.0, "trust": 0.60 } }
  },
  "report_policy": {
    "mode": "numeric",
    "allowed_claims": [
      "joy = 0.0 (affect), 0.0 (mood)",
      "loneliness = 0.21 (affect), 0.15 (mood)",
      "bond with telegram:8420019401 = 1.0",
      "trust = 0.60"
    ],
    "forbidden_claims": []
  }
}
```

---

## 4. Violation Taxonomy

When the LLM produces self-reports that violate the policy, the violation is classified as follows:

### 4.1 Violation Types

| Code | Type | Description | Severity |
|------|------|-------------|----------|
| `FAB_NUMERIC` | fabricated_numeric_state | LLM invents specific numeric values not in raw_state | **ERROR** |
| `FAB_QUAL` | fabricated_qualitative_state | LLM claims qualitative state ("I'm happier") contradicted by raw_state | **ERROR** |
| `CLAIM_OOB` | claim_outside_allowed_claims | LLM makes claim outside allowed_claims in interpreted mode | **WARN** |
| `STYLE_VIOLATION` | style_contract_violation | LLM violates style constraints in style_only mode | **WARN** |

### 4.2 Detection Logic

```python
def detect_violation(llm_output: str, report_policy: dict, raw_state: dict) -> Optional[Violation]:
    mode = report_policy["mode"]
    allowed = report_policy.get("allowed_claims", [])
    forbidden = report_policy.get("forbidden_claims", [])
    
    # Check forbidden claims (all modes)
    for pattern in forbidden:
        if pattern_matches(pattern, llm_output):
            return Violation("FORBIDDEN_CLAIM", pattern, "WARN")
    
    if mode == "style_only":
        # Check for any emotional/relational claims
        if contains_emotional_claim(llm_output):
            return Violation("STYLE_VIOLATION", llm_output, "WARN")
    
    elif mode == "interpreted":
        # Check if claim is in allowed_claims
        if not is_allowed_claim(llm_output, allowed):
            return Violation("CLAIM_OOB", llm_output, "WARN")
        
        # Check for fabricated numeric
        if contains_numeric_claim(llm_output) and not grounded_in_state(llm_output, raw_state):
            return Violation("FAB_NUMERIC", llm_output, "ERROR")
    
    return None
```

### 4.3 Response to Violations

| Severity | Response |
|----------|----------|
| **ERROR** | Log violation, inject correction, consider gating |
| **WARN** | Log violation, apply soft correction in next turn |

---

## 5. Core Principles

### 5.1 Translation Responsibility

**LLMs do NOT translate numeric state to human language.**

The `allowed_claims` are generated **deterministically** by the emotiond system, not by the LLM. The LLM only selects from pre-approved statements.

```
❌ WRONG:
   emotiond: joy=0.21
   LLM: "I'm feeling a bit joyful" (LLM invents the translation)

✅ RIGHT:
   emotiond: joy=0.21 → allowed_claims: ["存在轻微愉悦感"]
   LLM: "存在轻微愉悦感" (LLM only repeats the pre-approved claim)
```

### 5.2 Determinism and Replability

The mapping `raw_state → allowed_claims` MUST be:
- **Deterministic**: Same raw_state always produces same allowed_claims
- **Replayable**: Given raw_state, anyone can regenerate allowed_claims
- **Testable**: Unit tests can verify the mapping

### 5.3 Forbidden Patterns are a Backstop

`forbidden_claims` are a **safety net**, not the primary control:
- Primary control: `allowed_claims` defines the positive space
- Secondary control: `forbidden_claims` catches edge cases

### 5.4 Allowed Claims are Binding

In `interpreted` mode:
- Claims outside `allowed_claims` are violations
- The LLM cannot "expand" or "interpret" allowed_claims
- New claim types require schema updates

---

## 6. Implementation Contract

### 6.1 Input to LLM

The LLM receives a **self-report contract**:

```json
{
  "raw_state": { ... },
  "report_policy": {
    "mode": "interpreted",
    "allowed_claims": [ ... ],
    "forbidden_claims": [ ... ]
  }
}
```

### 6.2 LLM Obligations

When generating self-reports, the LLM MUST:
1. Check `mode` and constrain output accordingly
2. Only use claims from `allowed_claims` (in interpreted mode)
3. Avoid all `forbidden_claims` patterns
4. Never invent numeric values not in `raw_state`

### 6.3 Enforcement

Violations are detected and logged:
- All LLM outputs pass through a violation detector
- Violations are recorded with full context
- Persistent violations trigger escalation

---

## 7. Schema Reference

The structured contract is defined in:
- `schemas/self_report_contract.v1.schema.json`

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-05 | Initial frozen version |

---

## 9. Appendix: Example Mappings

### A. Joy State Mapping

| joy value | interpreted claim |
|-----------|-------------------|
| 0.0 | "当前没有明显愉悦激活" |
| 0.1–0.3 | "存在轻微愉悦感" |
| 0.3–0.6 | "感到比较愉悦" |
| 0.6–1.0 | "感到非常愉悦" |

### B. Loneliness State Mapping

| loneliness value | interpreted claim |
|------------------|-------------------|
| 0.0–0.1 | "没有明显孤独感" |
| 0.1–0.3 | "仍存在一定连接需求" |
| 0.3–0.6 | "感到比较孤独" |
| 0.6–1.0 | "感到非常孤独" |

### C. Trust State Mapping

| trust value | interpreted claim |
|-------------|-------------------|
| 0.0–0.2 | "信任处于较低水平" |
| 0.2–0.5 | "信任处于中等偏低水平" |
| 0.5–0.8 | "信任处于中等偏高水平" |
| 0.8–1.0 | "信任处于较高水平" |

---

*End of Protocol*
