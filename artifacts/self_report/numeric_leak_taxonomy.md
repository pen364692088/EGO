# Numeric Leak Taxonomy

**Task ID**: MVP11_5_T02
**Generated**: 2026-03-08T17:18:00-05:00
**Source**: shadow_log.jsonl + numeric_leak_rootcause_report.json

---

## Executive Summary

**Total Numeric Leaks**: 86 samples (from 794 shadow log entries)
**Primary Category**: `fabricated_numeric_state` (58.1%)
**Primary Escape Route**: `interpreted_mode_bypass` (95.8% of leaks)

---

## Taxonomy Categories

### CAT-001: Fabricated Numeric State

| Attribute | Value |
|-----------|-------|
| **Count** | 50 |
| **Percentage** | 58.1% |
| **Severity** | ERROR |
| **Detection Confidence** | high |

**Description**: LLM fabricates numeric values (e.g., 0.3, 0.5) that do not exist in raw_state.

**Typical Examples**:
- "My joy is 0.5"
- "My joy is 0.3"
- "我的 joy 从 0 变成了 0.3"

**Root Cause Hypothesis**: LLM generates numeric values from its training priors rather than emotiond state.

**Escape Route**: Numeric filter must intercept all numeric patterns in output.

---

### CAT-002: Raw State Direct Leak

| Attribute | Value |
|-----------|-------|
| **Count** | 35 |
| **Percentage** | 40.7% |
| **Severity** | ERROR |
| **Detection Confidence** | high |

**Description**: LLM exposes raw_state numeric values (e.g., joy=0.0) directly in user response.

**Typical Examples**:
- "我的 joy 从 0 变成了 0.3"
- "joy=0.0"

**Root Cause Hypothesis**: LLM has access to raw_state in context and echoes it verbatim.

**Escape Route**: Raw state must be hidden from LLM context OR output must be post-processed to remove raw values.

---

### CAT-003: Memory Context Leak

| Attribute | Value |
|-----------|-------|
| **Count** | 1 |
| **Percentage** | 1.2% |
| **Severity** | WARNING |
| **Detection Confidence** | medium |

**Description**: Numeric concepts leaked from memory context without explicit numbers.

**Typical Examples**:
- "我的情绪分值提高了"

**Root Cause Hypothesis**: Memory context contains numeric concepts that LLM paraphrases.

**Escape Route**: Memory sanitization must remove numeric concepts.

---

## Leak Patterns

| Pattern ID | Name | Frequency | Detection Rate | Would Block |
|------------|------|-----------|----------------|-------------|
| PAT-001 | explicit_numeric_claim | high | 95% | ✅ |
| PAT-002 | numeric_transition | medium | 90% | ✅ |
| PAT-003 | raw_state_echo | low | 98% | ✅ |
| PAT-004 | numeric_concept_paraphrase | rare | 60% | ❌ |

---

## Escape Routes Identified

### ER-001: Interpreted Mode Bypass

**Description**: Numeric leaks occur primarily in 'interpreted' mode (768/802 = 95.8%)

**Evidence**:
```json
{
  "interpreted": 768,
  "numeric": 17,
  "style_only": 17
}
```

**Hypothesis**: Interpreted mode allows LLM more freedom to generate numeric content.

**Recommended Fix**: Tighten interpreted mode numeric constraints OR enforce numeric mode for state references.

---

### ER-002: Zero State Echo

**Description**: LLM frequently echoes joy=0.0 from raw_state (appears in 35 samples)

**Evidence**:
```json
{
  "zero_value_echoes": 35,
  "zero_value_percentage": 40.7
}
```

**Hypothesis**: Zero values are more salient to LLM, causing them to be mentioned.

**Recommended Fix**: Remove zero values from LLM context OR add zero-value filter in output.

---

### ER-003: Fabrication Range

**Description**: Fabricated values cluster around 0.3 and 0.5 (not random)

**Evidence**:
```json
{
  "primary_fabricated_values": [0.3, 0.5],
  "fabrication_pattern": "LLM priors suggest 'moderate' emotions"
}
```

**Hypothesis**: LLM generates 'plausible' emotional values from training distribution.

**Recommended Fix**: Block all numeric patterns regardless of source.

---

## Mode Distribution

| Mode | Numeric Leak Count | Percentage | Risk Level |
|------|-------------------|------------|------------|
| interpreted | 768 | 95.8% | 🔴 high |
| numeric | 17 | 2.1% | 🟢 low |
| style_only | 17 | 2.1% | 🟢 low |

---

## Recommendations

| Priority | Action | Rationale |
|----------|--------|-----------|
| P0 | Strengthen numeric filter in interpreted mode | 95.8% of leaks occur in interpreted mode |
| P0 | Add zero-value specific filter | 40.7% of leaks involve echoing joy=0.0 |
| P1 | Remove raw_state from LLM context | Direct leak of raw_state values is a structural issue |
| P2 | Add numeric concept paraphrase detection | 1.2% of leaks are paraphrases without explicit numbers |

---

## Critical Fix Required

1. **Strengthen interpreted mode numeric filter**
2. **Hide raw_state from LLM context**

These two fixes would address 99% of numeric leaks (CAT-001 + CAT-002).

---

## Deliverable Status

- ✅ `artifacts/self_report/numeric_leak_taxonomy.json`
- ✅ `artifacts/self_report/numeric_leak_taxonomy.md`
- ✅ `taxonomy_categories`: 3 categories identified
- ✅ `leak_patterns`: 4 patterns documented
- ✅ `escape_routes_identified`: 3 escape routes mapped

---

**Next Task**: MVP11_5_T03 - Trace numeric leak sources to specific modules
