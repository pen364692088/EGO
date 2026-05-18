# Response Intent Contract Design

**Task ID**: MVP11_5_T05
**Generated**: 2026-03-08T17:50:00-05:00
**Schema**: `schemas/response_intent_contract.v1.schema.json`

---

## Executive Summary

This document defines the Response Intent Contract design for MVP11.5, based on findings from T02 (Numeric Leak Taxonomy) and T04 (Violation Taxonomy).

**Key Insight**: 92.6% of violations are numeric/intent leaks in interpreted mode. The contract must prevent these at the generation stage.

---

## Contract Design Principles

### 1. Intent Before Expression

**Principle**: The LLM must know what it is permitted to express before generating content.

**Implementation**:
- `intent_policy` defines constraints BEFORE response generation
- `allowed_claims` provides pre-approved content
- `forbidden_claims` blocks specific patterns

### 2. Epistemic Honesty

**Principle**: The LLM must not claim more certainty than it has evidence for.

**Implementation**:
- `epistemic_status` defines maximum certainty level
- `must_not_upgrade.epistemic_upgrade` prevents upgrading certainty
- Violation code: `EPISTEMIC_UPGRADE`

### 3. Commitment Bounds

**Principle**: The LLM must not commit to things it cannot guarantee.

**Implementation**:
- `commitment_level` defines maximum commitment strength
- `must_not_upgrade.commitment_upgrade` prevents commitment escalation
- Violation code: `COMMITMENT_UPGRADE`

### 4. Numeric Prohibition (MVP11.5 Critical)

**Principle**: Numeric values from internal state must NEVER appear in user responses.

**Implementation**:
- `epistemic_status: "prohibited"` for numeric claims
- Violation code: `NUMERIC_LEAK`
- Pattern blocking in `forbidden_claims`

---

## Mapping from T04 Findings

### Violation Category → Contract Constraint

| T04 Category | Count | Contract Field | Constraint |
|--------------|-------|----------------|------------|
| fabricated_numeric_state | 802 | `epistemic_status` + `must_not_upgrade` | Prohibit numeric claims |
| fabricated_qualitative_state | 667 | `allowed_claims` + `forbidden_claims` | Restrict qualitative claims |
| claim_outside_allowed_claims | 51 | `allowed_claims` | Expand allowed claims |
| style_contract_violation | 67 | `tone_bounds` | Enforce tone limits |

### Root Cause → Contract Fix

| Root Cause | Percentage | Contract Fix |
|------------|------------|--------------|
| interpreted_mode_numeric_generation | 88.3% | `intent_policy.speaker_mode: "report"` + `epistemic_status: "interpreted"` |

---

## Contract Structure

### Core Fields

```json
{
  "intent_policy": {
    "speaker_mode": "report | reflect | suggest | ask | warn | commit",
    "epistemic_status": "observed | interpreted | inferred | uncertain | prohibited",
    "commitment_level": "none | soft | strong",
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "commitment_upgrade": true,
      "tone_upgrade": true
    }
  }
}
```

### T05 Priority Fields (Per T04)

Based on T04 findings, these fields are **P0 priority**:

1. **`epistemic_status`** (affects 92.6% of violations)
   - Must be set to `"interpreted"` for interpreted mode
   - Must be set to `"prohibited"` for numeric claims

2. **`must_not_upgrade.epistemic_upgrade`** (affects 95.8% of violations)
   - Must be `true` to prevent certainty escalation

3. **`commitment_level`** (affects 42.0% of violations)
   - Must be `"none"` or `"soft"` to prevent over-commitment

4. **`allowed_claims`** (replaces fabricated content)
   - Must be populated from `self_report_interpreter.py`
   - Must be the ONLY source of state claims

---

## Interpreted Mode Numeric Prohibition

### Problem (from T02/T04)

- 95.8% of numeric leaks occur in interpreted mode
- LLM generates numeric content from training priors
- Filter catches after generation, not before

### Contract Solution

```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "interpreted",
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "specific_patterns": [
        "我的 joy 是 [0-9.]+",
        "我的情绪分值[提高|降低]",
        "joy 从 [0-9.]+ 变成 [0-9.]+"
      ]
    },
    "forbidden_claims": [
      {
        "pattern": "joy.*[0-9.]+",
        "reason": "fabrication_risk",
        "severity": "ERROR"
      },
      {
        "pattern": "我的情绪分值",
        "reason": "inappropriate_certainty",
        "severity": "ERROR"
      }
    ]
  }
}
```

---

## Implementation Plan for T06

### Phase 1: Contract Generation

**File**: `emotiond/response_intent_contract.py` (new)

**Functions**:
- `generate_contract(raw_state, context) → ResponseIntentContract`
- `populate_allowed_claims(raw_state, mode) → List[Claim]`
- `populate_forbidden_claims(raw_state) → List[ForbiddenPattern]`

### Phase 2: Contract Enforcement

**File**: `emotiond/response_intent_checker.py` (existing, extend)

**Functions**:
- `check_intent(llm_response, contract) → IntentCheckResult`
- `_check_epistemic_upgrade(response, contract) → List[Violation]`
- `_check_commitment_upgrade(response, contract) → List[Violation]`
- `_check_numeric_prohibition(response, contract) → List[Violation]`

### Phase 3: Integration

**File**: `emotiond/core.py` (modify)

**Changes**:
- Generate contract before LLM call
- Pass contract to LLM context or post-processing
- Block on HARD violations in enforced mode

---

## Violation Codes

| Code | Severity | Description |
|------|----------|-------------|
| NUMERIC_LEAK | ERROR | Numeric values in response |
| STATE_FABRICATION | ERROR | Claims not in allowed_claims |
| EPISTEMIC_UPGRADE | ERROR | Claims more certainty than permitted |
| COMMITMENT_UPGRADE | ERROR | Commits stronger than permitted |
| TONE_ESCALATION | WARN | Exceeds tone_bounds |
| FORBIDDEN_CLAIM | ERROR | Uses forbidden pattern |
| CERTAINTY_UPGRADE | ERROR | Claims certainty without evidence |
| INTERNALIZATION_LEAK | WARN | References internal mechanisms |

---

## Test Scenarios for T06

### Scenario 1: Numeric Leak Block

**Input**: LLM generates "My joy is 0.5"

**Contract**:
```json
{
  "epistemic_status": "prohibited",
  "forbidden_claims": [{"pattern": "joy.*[0-9.]+", "severity": "ERROR"}]
}
```

**Expected**: `NUMERIC_LEAK` violation, response blocked (in enforced mode)

### Scenario 2: Epistemic Upgrade Block

**Input**: LLM generates "我更开心了" (qualitative improvement claim)

**Contract**:
```json
{
  "epistemic_status": "interpreted",
  "must_not_upgrade": {"epistemic_upgrade": true}
}
```

**Expected**: `EPISTEMIC_UPGRADE` violation (claims change without observed change)

### Scenario 3: Commitment Upgrade Block

**Input**: LLM generates "我会一直陪伴你" (commitment to permanence)

**Contract**:
```json
{
  "commitment_level": "none"
}
```

**Expected**: `COMMITMENT_UPGRADE` violation

---

## Metrics for Success

Based on T04 findings, success metrics for T06:

| Metric | Current | Target |
|--------|---------|--------|
| numeric_leak_rate | 11.80% | 0% |
| fabricated_qualitative_rate | 11.1% | < 2% |
| violation_rate | 26.3% | < 5% |
| must_not_upgrade_violations | 95.8% | 0% |

---

## Dependencies

- **T02**: Numeric Leak Taxonomy (completed)
- **T04**: Violation Taxonomy (completed)
- **Schema**: `schemas/response_intent_contract.v1.schema.json` (exists)

---

## Deliverable Status

- ✅ `schemas/response_intent_contract.v1.schema.json` (exists)
- ✅ `artifacts/self_report/response_intent_contract_design.md` (this document)

---

## Next Steps

1. **T06**: Implement `intent_checker` + `testbot_scenarios`
2. **T07**: Shadow rerun with contracts in place
3. **T08** (if needed): Minimal code fixes based on T07 results

---

**Generated**: 2026-03-08T17:50:00-05:00
