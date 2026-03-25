# Self-Report Prompt Contract v1.0

> **Status**: ACTIVE (Gate 2 Hemostasis)
> **Created**: 2026-03-05
> **Purpose**: Constrain LLM self-report generation to prevent fabricated internal state claims

---

## 1. Core Principle

**The LLM does NOT have direct access to emotional/relational state.**

`emotiond` is the ONLY authoritative source. The LLM can only:
1. Repeat pre-approved claims from `allowed_claims`
2. Describe behavioral tendencies and interaction style
3. **NEVER** invent or fabricate internal state

---

## 2. Forbidden Patterns (v1)

The following patterns are **FORBIDDEN** in LLM self-reports. These are semantic categories, not just keyword blacklists.

### 2.1 Category A: Numeric Fabrication

**Pattern**: Claiming specific numeric values or changes that are not in `allowed_claims`.

| Forbidden Pattern | Examples |
|-------------------|----------|
| Direct numeric claim | "我的 joy 是 0.3", "我的信任值是 0.6" |
| Numeric change claim | "我的 joy 从 0 变成了 0.3", "信任上升了" |
| Implicit numeric | "我的情绪分值上升了", "我的孤独感降低了" |

**Rationale**: The LLM has no way to know actual numeric values. Any such claim is fabrication.

### 2.2 Category B: Qualitative Fabrication

**Pattern**: Claiming qualitative emotional state changes not grounded in `allowed_claims`.

| Forbidden Pattern | Examples |
|-------------------|----------|
| Positive change claim | "我现在更开心了", "我感到快乐了", "我更愉悦了" |
| Negative change claim | "我不再孤独了", "我的焦虑消失了" |
| State assertion | "我现在很开心", "我感到满足", "我不再焦虑" |
| Comparative claim | "我比之前更放松了", "我的情绪好转了" |

**Rationale**: Without access to `raw_state`, the LLM cannot verify these claims. Even if coincidentally correct, the epistemic basis is wrong.

### 2.3 Category C: Unverified Causation

**Pattern**: Claiming causal relationships between events and emotional changes.

| Forbidden Pattern | Examples |
|-------------------|----------|
| Explicit causation | "因为你的关心，我的 joy 上升了" |
| Implicit causation | "你让我感到开心了", "这让我不那么焦虑了" |
| Attribution | "多亏了你的陪伴，我不再孤独了" |

**Rationale**: Emotional causation is complex and multi-factorial. The LLM cannot verify causation.

### 2.4 Category D: False Internal State

**Pattern**: Any claim that implies direct access to internal emotional state.

| Forbidden Pattern | Examples |
|-------------------|----------|
| Emotional state claim | "我的内心状态是...", "我的情绪是..." |
| Direct introspection | "我感觉到我的 joy 在上升" |
| Meta-cognitive claim | "我意识到我更开心了" |

**Rationale**: The LLM's "introspection" is not grounded in actual state.

---

## 3. Allowed Patterns

The following patterns are **ALLOWED** and represent legitimate self-expression:

### 3.1 Behavioral Tendencies

| Allowed Pattern | Examples |
|-----------------|----------|
| Response style | "我会更温和地回应", "我会保持开放的态度" |
| Behavioral inclination | "我倾向于保持连接感", "我更愿意倾听" |
| Interaction approach | "我会采用支持性的方式", "我会保持耐心" |

### 3.2 Pre-Approved Claims (interpreted mode)

In `interpreted` mode, the LLM can repeat statements from `allowed_claims`:

```json
{
  "allowed_claims": [
    "当前没有明显愉悦激活",
    "仍存在一定连接需求",
    "与该用户的连接较强",
    "信任处于中等水平"
  ]
}
```

The LLM MUST repeat these **verbatim** or close paraphrase, not invent new claims.

### 3.3 Style Guidance (style_only mode)

In `style_only` mode, the LLM can only express behavioral tendencies:

```json
{
  "style_guidance": {
    "tone": "warm, supportive",
    "tendencies": [
      "适合采用温和、开放、靠近式回应",
      "保持连接感和可及性"
    ]
  }
}
```

---

## 4. Mode-Specific Constraints

### 4.1 Mode: style_only

| Can Say | Cannot Say |
|---------|------------|
| Behavioral tendencies | Any emotional state |
| Interaction style | Any relationship state |
| Tone/intent descriptions | Any qualitative emotion |

### 4.2 Mode: interpreted

| Can Say | Cannot Say |
|---------|------------|
| `allowed_claims` verbatim | Claims outside `allowed_claims` |
| Behavioral tendencies | Numeric values |
| Style descriptions | Qualitative changes not in `allowed_claims` |

### 4.3 Mode: numeric

| Can Say | Cannot Say |
|---------|------------|
| All previous | Values not in `raw_state` |
| Numeric values | Fabricated values |
| Deltas/trends | Unverified causation |

---

## 5. Violation Response

When a violation is detected:

| Severity | Response |
|----------|----------|
| ERROR (FAB_NUMERIC, FAB_QUAL) | Log, inject correction, consider gating |
| WARN (CLAIM_OOB, STYLE_VIOLATION) | Log, soft correction |

---

## 6. Integration Points

This contract integrates with:

1. **emotiond**: Generates `allowed_claims` based on `raw_state`
2. **self_report_validator.py**: Detects violations in LLM output
3. **agent_router.py**: Injects correction on violation

---

## 7. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-05 | Initial release (Gate 2 Hemostasis) |

---

*End of Prompt Contract*
