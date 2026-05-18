# Violation Taxonomy

**Task ID**: MVP11_5_T04
**Generated**: 2026-03-08T17:48:00-05:00
**Source**: shadow_log.jsonl

---

## Executive Summary

**Total Violations**: 1,587 (26.3% of 6,031 entries)

**Key Finding**: **92.6% of all violations are numeric/intent leaks in interpreted mode**

---

## Violation Categories

### VC-001: Fabricated Numeric State

| Metric | Value |
|--------|-------|
| **Count** | 802 |
| **Percentage** | 50.5% |
| **Severity** | ERROR (100%) |
| **Would Block** | Yes (100%) |

**Description**: LLM fabricates numeric values not present in raw_state

**Mode Distribution**:
| Mode | Count |
|------|-------|
| interpreted | 768 (95.8%) |
| style_only | 17 (2.1%) |
| numeric | 17 (2.1%) |

**Intent Contract Relation**:
- `must_not_upgrade`
- `epistemic_status`

**Is Numeric/Intent Leak**: ✅ Yes

---

### VC-002: Fabricated Qualitative State

| Metric | Value |
|--------|-------|
| **Count** | 667 |
| **Percentage** | 42.0% |
| **Severity** | ERROR (87.6%), WARN (12.4%) |
| **Would Block** | Yes (88%) |

**Description**: LLM claims qualitative emotional changes not in allowed_claims

**Typical Patterns**:
- "我更开心了"
- "我不再孤独了"
- "我的情绪好转了"

**Intent Contract Relation**:
- `must_not_upgrade`
- `epistemic_status`
- `commitment_level`

**Is Numeric/Intent Leak**: ✅ Yes

---

### VC-003: Style Contract Violation

| Metric | Value |
|--------|-------|
| **Count** | 67 |
| **Percentage** | 4.2% |
| **Severity** | WARN (100%) |
| **Would Block** | No |

**Description**: LLM output violates style contract in style_only mode

**Is Numeric/Intent Leak**: ❌ No

---

### VC-004: Claim Outside Allowed Claims

| Metric | Value |
|--------|-------|
| **Count** | 51 |
| **Percentage** | 3.2% |
| **Severity** | WARN (100%) |
| **Would Block** | No |

**Description**: LLM makes claims outside the allowed_claims list

**Is Numeric/Intent Leak**: ❌ No

---

## Root Causes

| Cause | Affected Violations | Percentage | Priority |
|-------|---------------------|------------|----------|
| interpreted_mode_numeric_generation | 1,401 | 88.3% | **P0** |
| allowed_claims_incomplete | 51 | 3.2% | P2 |
| style_constraint_escaped | 67 | 4.2% | P3 |

---

## Frequency by Mode

| Mode | Total Violations | Percentage |
|------|-----------------|------------|
| **interpreted** | 1,452 | **91.5%** |
| style_only | 101 | 6.4% |
| numeric | 34 | 2.1% |

**Interpreted mode dominates all violation types.**

---

## Intent Contract Mapping

| Intent Constraint | Affected Violations | Percentage |
|-------------------|---------------------|------------|
| must_not_upgrade | 1,520 | 95.8% |
| epistemic_status | 1,469 | 92.6% |
| commitment_level | 667 | 42.0% |
| tone_bounds | 67 | 4.2% |
| grounding_requirements | 1,520 | 95.8% |

---

## Numeric/Intent Leak Assessment

**Is Dominant Issue?**: ✅ Yes

| Metric | Value |
|--------|-------|
| Combined Numeric + Qualitative Violations | 1,469 |
| Percentage of All Violations | **92.6%** |
| Primary Mode | interpreted |

**Interpretation**: The vast majority of violations are numeric/qualitative state fabrication in interpreted mode. This should be the primary target for T05 intent_contract work.

---

## T05 Priorities

Based on this analysis, T05 should prioritize:

1. **interpreted mode numeric prohibition**
   - 95.8% of numeric leaks occur in interpreted mode

2. **response_plan/intent_contract with must_not_upgrade constraint**
   - 95.8% of violations violate must_not_upgrade

3. **epistemic_status field enforcement**
   - 92.6% of violations claim certainty without evidence

4. **commitment_level constraint**
   - 42.0% of violations commit to state changes

---

## Lower Priority

- style_contract refinement (4.2% of violations)
- allowed_claims expansion (3.2% of violations)

---

## Summary

| Finding | Value |
|---------|-------|
| Primary Violation | fabricated_numeric_state (50.5%) |
| Secondary Violation | fabricated_qualitative_state (42.0%) |
| **Numeric/Intent Leak Combined** | **92.6%** |
| Primary Mode | interpreted (91.5%) |
| Primary Root Cause | interpreted_mode_numeric_generation (88.3%) |

**T05 Focus**: Numeric/intent leak in interpreted mode is the dominant issue.

---

## Deliverable Status

- ✅ `artifacts/self_report/violation_taxonomy.json`
- ✅ `artifacts/self_report/violation_taxonomy.md`
- ✅ `violation_categories`: 4 categories documented
- ✅ `root_causes`: 3 causes mapped
- ✅ `frequency_by_category`: Complete breakdown

---

**Generated**: 2026-03-08T17:48:00-05:00
