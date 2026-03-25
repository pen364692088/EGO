# MVP-3 Implementation Plan

## Overview
Implement human-like emotion reasoning kernel minimal closed loop for OpenEmotion.

**Baseline:** 348 tests passing, commit 0e453f3
**Branch:** feature-emotiond-mvp

---

## Phase 1: Experiment Validity Constraints (A1+A2)

### A1: request_id Idempotency

#### Database Schema
```sql
CREATE TABLE request_dedupe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    request_id TEXT NOT NULL,
    event_id INTEGER,
    decision_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, request_id)
);
```

#### API Changes
- Add `request_id` to `USER_ALLOWED_META_KEYS` in security.py
- Modify `process_event()` to check dedupe table before processing
- Return `duplicate_ignored` or cached result on repeat

#### Implementation Files
- `emotiond/db.py` - Add `request_dedupe` table, `check_and_record_request()` function
- `emotiond/security.py` - Add `request_id` to allowed keys
- `emotiond/core.py` - Call dedupe check at start of `process_event()`
- `emotiond/api.py` - Handle duplicate response

#### Tests
- Same request_id twice -> second returns duplicate_ignored
- No state change on duplicate
- Audit record for duplicate

### A2: time_passed Cumulative Rate Limiting

#### Database Schema
```sql
CREATE TABLE time_passed_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    seconds REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Implementation
- Window: 10 seconds real time
- Max cumulative: 60 seconds
- Check current window sum before accepting
- Clamp to remaining budget
- Record audit with window_sum, requested, clamped_to, reason

#### Implementation Files
- `emotiond/db.py` - Add tracking table, `get_time_passed_window_sum()`, `record_time_passed()`
- `emotiond/security.py` - Extend time_passed validation with cumulative check
- `emotiond/config.py` - Add `TIME_PASSED_WINDOW_SECONDS=10`, `TIME_PASSED_MAX_CUMULATIVE=60`

#### Tests
- Multiple time_passed within window -> cumulative limit enforced
- Window expiry -> budget reset
- Audit shows clamp details

---

## Phase 2: Interoceptive Inference (B1-B6)

### B1: New Interoceptive States

#### State Variables
- `social_safety: float` in [0, 1], default 0.6
- `energy: float` in [0, 1], default 0.7

#### Database Schema
```sql
ALTER TABLE state ADD COLUMN social_safety REAL DEFAULT 0.6;
ALTER TABLE state ADD COLUMN energy REAL DEFAULT 0.7;
```

#### Update Rules
- `time_passed`: energy += 0.001 * seconds (capped at 1.0)
- High conflict events (betrayal/rejection/ignored): safety -= 0.1, energy -= 0.05
- Positive events (care/apology/repair_success): safety += 0.05

### B2: Action Space

#### Actions (discrete)
1. `approach` - Seek connection
2. `repair_offer` - Attempt repair
3. `boundary` - Set boundary
4. `withdraw` - Pull back
5. `attack` - Retaliate

#### Database Schema
```sql
CREATE TABLE action_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL UNIQUE,
    predicted_safety_delta REAL DEFAULT 0.0,
    predicted_energy_delta REAL DEFAULT 0.0,
    prediction_error_sum REAL DEFAULT 0.0,
    prediction_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### B3: Prediction Model

#### Initial Priors (configurable)
```python
ACTION_PRIORS = {
    "approach": {"safety": 0.03, "energy": -0.02},
    "repair_offer": {"safety": 0.05, "energy": -0.04},
    "boundary": {"safety": 0.02, "energy": -0.03},
    "withdraw": {"safety": 0.01, "energy": 0.02},
    "attack": {"safety": -0.05, "energy": -0.05},
}
```

### B4: Observation Mapping

#### Event Subtype -> Observed Delta
```python
OBSERVATION_MAP = {
    "care": {"safety": 0.1, "energy": 0.05},
    "apology": {"safety": 0.08, "energy": 0.02},
    "repair_success": {"safety": 0.12, "energy": 0.05},
    "rejection": {"safety": -0.15, "energy": -0.08},
    "ignored": {"safety": -0.05, "energy": -0.03},
    "betrayal": {"safety": -0.25, "energy": -0.15},
    "time_passed": {"safety": 0.0, "energy": 0.01},  # per second
}
```

### B5: Prediction Error Learning

#### Learning Rule
```python
prediction_error = observed_delta - predicted_delta
predicted_delta += learning_rate * prediction_error  # lr=0.1
predicted_delta = clamp(predicted_delta, -0.2, 0.2)
```

#### Persistence
- Store in `action_predictions` table
- Load on startup in `load_initial_state()`

### B6: Action Selection

#### Score Function
```python
def score(action, state, relationships):
    # Relationship benefit
    rel_score = w_bond * bond - w_grudge * grudge + w_trust * trust
    
    # Predicted change
    pred_safety = predicted_delta[action]["safety"]
    pred_energy = predicted_delta[action]["energy"]
    pred_score = w_safety * pred_safety + w_energy * pred_energy
    
    # Uncertainty penalty
    uncertainty = prediction_error_sum / prediction_count if count > 0 else 0
    uncertainty_penalty = -w_uncertainty * abs(uncertainty)
    
    return rel_score + pred_score + uncertainty_penalty
```

#### Selection
- Production: `softmax(scores, temperature=0.5)`
- Test mode: `argmax(scores)` for determinism

---

## Phase 3: Structured Explanations (C1-C3)

### C1: Explanation Structure

```python
explanation = {
    "emotion": {
        "top2": [("anger", 0.3), ("sadness", 0.2)],
        "all": {"anger": 0.3, "sadness": 0.2, ...}
    },
    "interoception": {
        "social_safety": 0.45,
        "energy": 0.6
    },
    "relationships": {
        "bond": 0.3, "grudge": 0.5, "trust": 0.2, "repair_bank": 0.1
    },
    "candidates": [
        {
            "action": "withdraw",
            "score": 0.42,
            "predicted_delta": {"safety": 0.01, "energy": 0.02},
            "reasons": ["Low trust", "High grudge"]
        },
        ...
    ],
    "selected": "withdraw",
    "selection_reasons": [
        "Highest score given current state",
        "Conservative choice for low safety"
    ]
}
```

#### Database Schema
```sql
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    explanation TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### C2: API Output

- Add `explanation` field to `/event` response (optional, controlled by env var)
- Add `last_decision` to `/plan` response

### C3: Explanation Consistency Tests

- Top3 candidates match score ranking
- Reasons are non-empty
- Selected action has highest score

---

## Implementation Order

1. **A1: request_id idempotency** - Foundation for all event processing
2. **A2: time_passed cumulative limit** - Prevents gaming
3. **B1: Interoceptive states** - Add to EmotionState + DB
4. **B3+B5: Prediction model** - Initialize priors + learning
5. **B4: Observation mapping** - Event to delta mapping
6. **B2+B6: Actions + selection** - Full action selection loop
7. **C1-C3: Explanations** - Output and tests
8. **Documentation** - MVP-3.md

---

## Test Requirements

### Idempotency Tests
- Duplicate request_id ignored
- No state change on duplicate
- Audit records duplicate

### Rate Limit Tests
- Cumulative limit within window
- Window reset after expiry
- Clamp audit present

### Learning Curve Tests
- Action with negative outcomes -> prediction adjusted downward
- Prediction affects selection probability
- Recovery with positive outcomes

### Explanation Tests
- Top3 matches score order
- Reasons non-empty
- Selected has highest score
