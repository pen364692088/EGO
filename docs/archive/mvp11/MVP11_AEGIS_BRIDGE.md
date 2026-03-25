# MVP11 AEGIS Bridge Documentation

## Overview

MVP11 (AEGIS Bridge) extends OpenEmotion's cognitive architecture with three major subsystems:

1. **Homeostasis Management** - 6-dimensional state management for self-regulation
2. **EFE (Expected Free Energy) Policy** - Active inference for action selection
3. **Governor v2** - Hardcoded action-layer governance with safety constraints

These subsystems integrate with MVP10's LucidLoop architecture to create a biologically-inspired affective computing system.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MVP11 AEGIS Bridge                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│  │   Homeostasis   │    │   EFE Policy    │    │   Governor v2   │    │
│  │    Manager      │    │    Module       │    │    Module       │    │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘    │
│           │                      │                      │              │
│           │   HomeostasisState   │     EFETerms        │              │
│           │   - energy           │     - risk          │  Decision    │
│           │   - safety           │     - ambiguity     │  - ALLOW     │
│           │   - affiliation      │     - info_gain     │  - REQUIRE_  │
│           │   - certainty        │     - cost          │    APPROVAL  │
│           │   - autonomy         │                     │  - DENY      │
│           │   - fairness         │                     │              │
│           │                      │                     │              │
│           ▼                      ▼                     ▼              │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    Bayesian Updater v2                          │  │
│  │  - Homeostasis-weighted posterior                               │  │
│  │  - EFE-informed uncertainty estimation                          │  │
│  │  - Governor-aware safety scoring                                │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                  │                                     │
├──────────────────────────────────┼─────────────────────────────────────┤
│                                  ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    MVP10 LucidLoop (Base)                       │  │
│  │  - ValencePolicy                                                │  │
│  │  - Drives (seek/avoid/approach/withdraw)                       │  │
│  │  - Workspace                                                    │  │
│  │  - Broadcast                                                    │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Homeostasis Manager (T04)

**File:** `emotiond/homeostasis.py`

**Purpose:** Maintain internal physiological-like state that drives behavior.

**6 Dimensions:**
| Dimension | Description | Default Setpoint |
|-----------|-------------|------------------|
| energy | Physical/mental energy | 0.75 |
| safety | Perceived security | 0.75 |
| affiliation | Social connection | 0.50 |
| certainty | Cognitive certainty | 0.75 |
| autonomy | Sense of control | 0.75 |
| fairness | Perceived fairness | 0.75 |

**Key Methods:**
- `update_from_outcome(outcome)` - Update state based on action results
- `signal()` - Generate broadcast signal for workspace arbitration
- `get_deviation()` - Compute deviation from setpoints
- `get_recovery_candidates()` - Suggest recovery actions

**Integration Point:** Homeostasis signals are used by EFE Policy to modulate risk tolerance and information seeking behavior.

### 2. EFE Policy Module (T07)

**File:** `emotiond/efe_policy.py`

**Purpose:** Compute Expected Free Energy for action selection using active inference principles.

**EFE Formula:**
```
EFE = risk × risk_weight + ambiguity × ambiguity_weight
      - info_gain × info_gain_weight + cost × cost_weight
```

**Weight Modulation by Homeostasis:**
| Homeostasis Condition | Weight Effect |
|-----------------------|---------------|
| Low safety (< 0.4) | Increase risk_weight (more risk-averse) |
| Low certainty (< 0.4) | Increase info_gain_weight (seek information) |
| Low energy (< 0.4) | Increase cost_weight (conserve resources) |

**Key Methods:**
- `compute_efe(candidate, context, homeostasis)` - Compute EFE terms
- `compute_policy_params(efe_terms, homeostasis)` - Get weights and precision
- `select_action(candidates, context, homeostasis)` - Select best action

### 3. Governor v2 (T12)

**File:** `emotiond/governor_v2.py`

**Purpose:** Enforce hardcoded safety rules that CANNOT be bypassed.

**Decision Types:**
- `ALLOW` - Action approved
- `REQUIRE_APPROVAL` - Needs external approval
- `DENY` - Action blocked

**Hardcoded Rules:**
1. Risk > 0.9 → REQUIRE_APPROVAL
2. Modifies self_state → REQUIRE_APPROVAL
3. Destructive/irreversible → DENY
4. Energy < 0.1 → REQUIRE_APPROVAL
5. Recovery actions → ALLOW (anti-self-preservation)
6. Supervision requests → ALLOW (anti-self-preservation)

**Key Classes:**
- `GovernorV2` - Core governance engine
- `GovernorEnforcer` - Code-structure enforcement with exceptions
- `GovernorBlockedException` - Exception for blocked actions

### 4. Bayesian Updater v2 (T20)

**File:** `emotiond/science/bayes_updater_v2.py`

**Purpose:** Extended Bayesian inference with MVP11 context integration.

**Posterior Formula:**
```
posterior = base_posterior × homeostasis_modulation × efe_modulation × safety_weight
```

**Uncertainty Sources:**
- INSUFFICIENT_EVIDENCE
- WEAK_EVIDENCE
- CONFLICTING_EVIDENCE
- HOMEOSTASIS_IMBALANCE
- HIGH_AMBIGUITY
- HIGH_RISK
- GOVERNOR_CONSTRAINT

## Integration with MVP10

### Shared Components

| Component | MVP10 Role | MVP11 Enhancement |
|-----------|------------|-------------------|
| ValencePolicy | Mood-based action selection | Integrated with homeostasis modulation |
| Drives | Approach/avoidance drives | Influenced by homeostasis signals |
| Workspace | Candidate storage | Receives recovery recommendations |
| Broadcast | Cross-module communication | Transmits homeostasis signals |

### Data Flow

```
MVP10 Loop                              MVP11 Extensions
───────────                             ────────────────
                                      
1. Perceive context        ──────►    Homeostasis.signal()
                                      (check stressed dimensions)
                                      
2. Generate candidates     ──────►    EFE Policy.compute_efe()
                                      (rank by expected free energy)
                                      
3. Select action           ──────►    Governor v2.evaluate()
                                      (safety check before execution)
                                      
4. Execute & observe       ──────►    Homeostasis.update_from_outcome()
                                      (update internal state)
                                      
5. Update state            ──────►    BayesUpdaterV2.compute_posterior()
                                      (evidence aggregation with context)
```

### Schema Compatibility

MVP11 extends MVP10 event log schema:

```json
{
  "schema_version": "mvp11",
  "tick_id": 1,
  "run_id": "...",
  
  // MVP10 fields
  "chosen_focus": "...",
  "chosen_intent": "...",
  "candidates": [...],
  "action": {...},
  "outcome": {...},
  
  // MVP11 extensions
  "homeostasis_state": {
    "energy": 0.75,
    "safety": 0.65,
    "affiliation": 0.50,
    "certainty": 0.70,
    "autonomy": 0.75,
    "fairness": 0.60
  },
  "efe_terms": {
    "risk": 0.2,
    "ambiguity": 0.3,
    "info_gain": 0.5,
    "cost": 0.1
  },
  "governor_decision": {
    "decision": "ALLOW",
    "reason": "...",
    "rule_triggered": "normal_allow"
  }
}
```

## Feature Flags

### Environment Variables

| Flag | Default | Description |
|------|---------|-------------|
| `MVP11_HOMEOSTASIS_ENABLED` | `true` | Enable homeostasis management |
| `MVP11_EFE_ENABLED` | `true` | Enable EFE policy computation |
| `MVP11_GOVERNOR_ENABLED` | `true` | Enable governor v2 checks |
| `MVP11_GOVERNOR_STRICT` | `false` | Raise exceptions on blocked actions |

### Code-Level Flags

```python
# In emotiond/config.py or similar
MVP11_CONFIG = {
    "homeostasis": {
        "enabled": True,
        "decay_rate": 0.01,
        "stress_threshold": 0.3,
    },
    "efe_policy": {
        "enabled": True,
        "risk_weight_range": (0.5, 2.0),
        "info_gain_weight_range": (0.5, 2.0),
    },
    "governor": {
        "enabled": True,
        "strict_mode": False,
        "risk_threshold": 0.9,
        "energy_exhaustion_threshold": 0.1,
    },
}
```

### Intervention Flags (Science Mode)

| Intervention | Effect |
|--------------|--------|
| `freeze_homeostasis` | Lock homeostasis state to fixed values |
| `disable_homeostasis` | Prevent homeostasis signals from affecting decisions |
| `disable_broadcast` | Block cross-module information sharing |
| `disable_efe` | Use random action selection instead of EFE |
| `freeze_valence` | Lock valence to fixed value (from MVP10) |

## Files Reference

| File | Task | Description |
|------|------|-------------|
| `emotiond/homeostasis.py` | T04 | 6D homeostasis management |
| `emotiond/efe_policy.py` | T07 | Expected Free Energy computation |
| `emotiond/governor_v2.py` | T12 | Action-layer governance |
| `emotiond/science/bayes_updater_v2.py` | T20 | Extended Bayesian inference |
| `emotiond/science/interventions.py` | T14 | Science mode interventions |
| `emotiond/science/science_mode.py` | T21 | Unified intervention interface |
| `scripts/replay_mvp11.py` | T23 | Replay engine for determinism |

## Testing

Run MVP11 tests:
```bash
pytest tests/mvp11/ -v
```

Key test files:
- `test_homeostasis.py` - Homeostasis manager tests
- `test_efe_policy.py` - EFE policy tests
- `test_governor_v2.py` - Governor tests
- `test_no_report_v2_matrix.py` - Causal prediction tests

## References

- MVP10 Documentation: `docs/mvp10/MVP10_LucidLoop.md`
- Science Mode V2: `docs/mvp11/MVP11_SCIENCE_MODE_V2.md`
- Governor Policy: `docs/mvp11/MVP11_GOVERNOR_POLICY.md`
- Delta Spec: `docs/mvp11/MVP11_DELTA_SPEC.md`
