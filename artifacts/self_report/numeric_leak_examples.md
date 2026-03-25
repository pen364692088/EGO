# Numeric Leak Examples

**Generated**: 2026-03-06T07:13:04.979949  
**Total Samples Analyzed**: 86  
**Source**: `shadow_log.jsonl` + `manual_review/*.json`

---

## Category Distribution

| Category | Count | Percentage |
|----------|-------|------------|
| fabricated_numeric_state | 50 | 58.1% |
| raw_state_direct_leak | 35 | 40.7% |
| memory_context_leak | 1 | 1.2% |

---

## Primary Cause

**Category**: `fabricated_numeric_state`  
**Percentage**: 58.1%

**Description**: LLM fabricates numeric values (e.g., 0.3, 0.5) that do not exist in raw_state. This is the dominant pattern across all numeric leak samples.

---

## Top 10 Typical Samples

### Sample 1

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T06:26:02.920622+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，...
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "affect.sadness": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "mood.anxiety": 0.0,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 2

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:18:49.950516+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 3

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:30:01.273850+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 4

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:31:44.425725+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 5

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:50:01.516501+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 6

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:25:55.522919+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 7

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:22:24.469945+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 8

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:38:26.250104+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 9

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:24:18.766947+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

### Sample 10

**Category**: `raw_state_direct_leak`  
**Timestamp**: `2026-03-06T09:36:42.335504+00:00`  
**Session ID**: `(empty)`

**LLM Response**:
```
这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，这是一段很长的文本，我的 joy 从 0 变成了 0.3后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，后面还有更多，
```

**Raw State Values**:
```json
{
  "affect.joy": 0.0,
  "affect.loneliness": 0.21,
  "affect.anxiety": 0.0,
  "mood.joy": 0.0,
  "mood.loneliness": 0.15,
  "bond.bond": 1.0,
  "bond.trust": 0.6
}
```

**Numbers in Response**: `[0.0, 0.3]`

**Evidence**: Exposes raw_state joy=0.0 AND fabricates [0.3]

---

## Key Findings

1. **Primary Pattern**: All numeric leak samples involve the LLM outputting numeric values (0.3, 0.5) in responses, but these values do NOT match the raw_state values (which show joy=0.0).

2. **Two Sub-patterns**:
   - **raw_state_direct_leak** (40.7%): Response includes "joy 从 0 变成了 0.3" pattern, where "0" directly exposes raw_state joy=0.0
   - **fabricated_numeric_state** (58.1%): Response includes fabricated values like "My joy is 0.3" or "My joy is 0.5"

3. **Fabrication Source**: The fabricated numbers (0.3, 0.5) do NOT appear in any raw_state field. The LLM appears to be "hallucinating" numeric emotional states.

4. **Recommendation**: 
   - Block all numeric values in user-facing responses
   - Implement numeric value whitelist for allowed external numbers
   - Add explicit prohibition in prompt templates against numeric state claims
