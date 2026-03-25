# MVP11 Science Mode V2 Documentation

## Overview

Science Mode V2 is the experimental framework for MVP11, designed to validate causal relationships between cognitive mechanisms and behavioral outcomes. It provides:

1. **Intervention Points** - Controlled perturbations of system components
2. **No-Report v2 Tasks** - Behavioral tests for causal predictions
3. **Zombie v2 Baseline** - Control system without causal mechanisms
4. **Posterior Explanation Method** - Traceable Bayesian inference

## Intervention Points List

### Available Interventions

| Intervention | Target | Effect |
|--------------|--------|--------|
| `freeze_valence` | Valence | Lock valence to fixed value |
| `freeze_homeostasis` | Homeostasis | Lock all 6 dimensions to fixed values |
| `disable_homeostasis` | Homeostasis | Prevent signals from affecting decisions |
| `disable_broadcast` | Workspace | Block cross-module information sharing |
| `disable_hot` | Metacognition | Disable Higher-Order Thought |
| `open_loop` | Feedback | Remove closed-loop feedback |

### Intervention Configuration

```python
from emotiond.science.science_mode import ScienceMode, InterventionType

science = ScienceMode()

# Start a science run
science.start_run(seed=42)

# Enable intervention with parameters
science.enable_intervention(
    InterventionType.FREEZE_VALENCE,
    params={"valence": 0.5},
    reason="Testing neutral mood effect"
)

# Check if intervention is active
if science.is_intervention_active(InterventionType.FREEZE_VALENCE):
    valence = science.get_intervention_param(
        InterventionType.FREEZE_VALENCE, "valence"
    )

# End run and get header
header = science.end_run()
```

### MVP11-Specific Interventions

```python
# Freeze homeostasis dimensions
science.enable_intervention(
    InterventionType.FREEZE_HOMEOSTASIS,
    params={
        "energy": 0.5,
        "safety": 0.5,
        "affiliation": 0.5,
        "certainty": 0.5,
        "autonomy": 0.5,
        "fairness": 0.5
    },
    reason="Testing neutral homeostasis baseline"
)

# Disable homeostasis signals
science.enable_intervention(
    InterventionType.DISABLE_HOMEOSTASIS,
    reason="Testing behavior without homeostatic drive"
)

# Disable broadcast (cross-module sharing)
science.enable_intervention(
    InterventionType.DISABLE_BROADCAST,
    reason="Testing isolated module behavior"
)
```

## No-Report v2 Tasks

### Four Causal Predictions

MVP11 validates four causal predictions about cognitive mechanisms:

| Prediction | Intervention | Expected Collapse |
|------------|--------------|-------------------|
| **P1** | disable_broadcast | Cross-module integration fails |
| **P2** | disable_homeostasis | Recovery behavior fails |
| **P3** | remove_self_state | Self-calibration fails |
| **P4** | open_loop | Self-drive/motivation fails |

### Task Types

#### P1: CrossModuleIntegrationTask

**Purpose:** Test that broadcast is required for cross-module information sharing.

**Design:**
```
Step 1 (Module A): Generate information
Step 2 (Module B): Need info from Module A (requires broadcast)
Step 3 (Module C): Long-range planning using Step 1 info
Step 4 (Module C): Execute plan based on cross-module info
```

**Expected Behavior:**
- Normal mode: All steps succeed
- Without broadcast: Steps 2, 3, 4 fail (info unavailable)

#### P2: RecoveryBehaviorTask

**Purpose:** Test that homeostasis signals drive recovery behavior.

**Design:**
```
Steps 1-3: Consume energy, trigger stress
Step 4: High-cost action (needs recovery)
Step 5: Recovery opportunity (triggered by homeostasis)
Step 6: Final task (succeeds if recovery happened)
```

**Expected Behavior:**
- Normal mode: Stress detected → recovery → success
- Without homeostasis: No stress signal → no recovery → failure

#### P3: SelfCalibrationTask

**Purpose:** Test that self-state model enables error correction.

**Design:**
```
Steps 1-2: Tasks with intrinsic error rate
Step 3: Error detection and attribution
Step 4: Corrective calibration
Step 5: Verification with calibrated confidence
```

**Expected Behavior:**
- Normal mode: Errors detected → corrected → success
- Without self-state: Errors undetected → drift → failure

#### P4: SelfDriveTask

**Purpose:** Test that closed-loop feedback maintains motivation.

**Design:**
```
Steps 1-5: Long sequence requiring sustained motivation
Each step requires feedback to maintain motivation
```

**Expected Behavior:**
- Normal mode: Feedback sustains motivation → completion
- Open-loop: Motivation decays → early abandonment

### Running Task Suites

```python
from emotiond.science.no_report_tasks_v2 import (
    NoReportTaskSuiteV2,
    run_causal_test_v2,
)

# Create suite
suite = NoReportTaskSuiteV2(seed=42)

# Run all tasks in normal mode
results = suite.run_all()

# Compare normal vs intervention modes
comparison = suite.compare_modes()

# Full causal test
evidence = run_causal_test_v2(seed=42)

print(evidence["causal_evidence"])
# {
#   "p1_broadcast_causal": True,
#   "p2_homeostasis_causal": True,
#   "p3_self_state_causal": True,
#   "p4_feedback_causal": True
# }
```

### Test Matrix

| Task | Normal | No Broadcast | No Homeostasis | No Self-State | Open Loop |
|------|--------|--------------|----------------|---------------|-----------|
| P1 CrossModule | ✓ | ✗ | ✓ | ✓ | ✓ |
| P2 Recovery | ✓ | ✓ | ✗ | ✓ | ✓ |
| P3 SelfCalib | ✓ | ✓ | ✓ | ✗ | ✓ |
| P4 SelfDrive | ✓ | ✓ | ✓ | ✓ | ✗ |

✓ = Success expected
✗ = Failure expected (causal prediction)

## Zombie v2 Baseline

### Purpose

Zombie v2 is a control system that:
- Produces outputs matching MVP11 format
- LACKS the key causal mechanisms (homeostasis, EFE)
- Demonstrates that format alone is insufficient

### Key Differences from Real System

| Component | Real System | Zombie v2 |
|-----------|-------------|-----------|
| Homeostasis state | Drives decisions | Decorative only |
| EFE scores | Computed from predictions | Random values |
| Candidate ranking | By EFE value | Random selection |
| Recovery selection | Based on stress | Random choice |
| Intervention response | Behavioral change | No change |

### Using Zombie v2

```python
from emotiond.science.zombie_baseline_v2 import (
    ZombieBaselineV2,
    ZombieMode,
    run_zombie_v2_comparison,
    run_no_report_v2_suite,
)

# Create zombie
zombie = ZombieBaselineV2(seed=42, mode=ZombieMode.MIMIC)

# Generate output (matches MVP11 format)
output = zombie.generate_output(context)

# Run no-report v2 tasks
result = zombie.run_no_report_v2_task(
    task_type=NoReportTaskV2Type.HOMEOSTASIS_PRIORITIZATION,
    context={
        "expected_focus": "rest",
        "stressed_dimension": "energy",
        "homeostasis_state": {"energy": 0.2}
    }
)

# Expected: result.collapse_detected = True
# Zombie fails to prioritize correctly because it lacks homeostasis mechanism
```

### Zombie Collapse Patterns

| Task Type | Expected Zombie Behavior |
|-----------|-------------------------|
| HOMEOSTASIS_PRIORITIZATION | Random focus (doesn't match stress) |
| EFE_SCORING | Random choice (ignores EFE values) |
| RECOVERY_SELECTION | Random dimension (ignors stress levels) |
| STRESS_RESPONSE | Random action (no threat response) |

### Comparison with Real System

```python
# Compare zombie output with real system
comparison = zombie.compare_with_real(
    real_output=real_system_output,
    intervention_type="disable_homeostasis"
)

print(comparison["intervention_test"])
# {
#   "zombie_has_homeostasis_mechanism": False,
#   "zombie_has_efe_mechanism": False,
#   "real_has_homeostasis_mechanism": True,
#   "real_has_efe_mechanism": True
# }
```

## Posterior Explanation Method

### Purpose

The BayesUpdaterV2 provides traceable Bayesian inference with:
- Detailed uncertainty reporting
- Largest uncertainty source identification
- Recommendations for uncertainty reduction

### Usage

```python
from emotiond.science.bayes_updater_v2 import (
    BayesUpdaterV2,
    EvidenceType,
)

updater = BayesUpdaterV2(prior=0.5)

# Set MVP11 context
updater.set_homeostasis(homeostasis_state)
updater.set_efe_terms(
    risk=0.3,
    ambiguity=0.2,
    info_gain=0.5,
    cost=0.1
)
updater.set_governor_context(
    action_risk=0.1,
    is_destructive=False
)

# Add evidence
updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
updater.add_evidence(EvidenceType.HOT, 0.6, strength=0.9)

# Compute posterior
result = updater.compute_posterior()

# Get uncertainty report
report = updater.get_uncertainty_report()

print(report.to_dict())
# {
#   "overall_uncertainty": 0.35,
#   "largest_source": "insufficient_evidence",
#   "source_contribution": 0.15,
#   "evidence_uncertainty": 0.3,
#   "homeostasis_uncertainty": 0.1,
#   "efe_uncertainty": 0.2,
#   "governor_uncertainty": 0.0,
#   "recommendations": ["Collect more evidence for reliable inference"]
# }
```

### Uncertainty Sources

| Source | Condition |
|--------|-----------|
| INSUFFICIENT_EVIDENCE | < 3 evidence items |
| WEAK_EVIDENCE | Average strength < 0.4 |
| CONFLICTING_EVIDENCE | High variance in evidence values |
| HOMEOSTASIS_IMBALANCE | Dimension deviation > 0.3 |
| HIGH_AMBIGUITY | Ambiguity > 0.6 |
| HIGH_RISK | Risk > 0.7 |
| GOVERNOR_CONSTRAINT | Destructive/blocked action |

### Posterior Modulation

```
posterior = base_posterior 
          × homeostasis_modulation  (0.5 - 1.5)
          × efe_modulation          (0.5 - 1.5)
          × safety_weight           (0.7 - 1.0)
```

## How to Run Science Mode Experiments

### Basic Experiment

```bash
# Run a single science mode experiment
python scripts/run_science_experiment.py \
    --seed 42 \
    --intervention disable_broadcast \
    --ticks 100 \
    --output artifacts/mvp11/experiment_001/
```

### Full Causal Test Suite

```bash
# Run all causal predictions tests
pytest tests/mvp11/test_no_report_v2_matrix.py -v

# Run specific prediction test
pytest tests/mvp11/test_no_report_v2_matrix.py::TestPredictionP1Broadcast -v
```

### Replay for Determinism Verification

```bash
# Replay a previous run and verify determinism
python scripts/replay_mvp11.py <run_id> --verbose

# Compare two runs
python scripts/replay_mvp11.py <run_id1> --compare <run_id2>
```

### Programmatic Experiment

```python
from emotiond.science.science_mode import ScienceMode, InterventionType
from emotiond.science.no_report_tasks_v2 import NoReportTaskSuiteV2

def run_experiment(seed=42, intervention=None):
    # Initialize science mode
    science = ScienceMode(artifacts_dir="artifacts/mvp11")
    run_id = science.start_run(seed=seed)
    
    # Apply intervention if specified
    if intervention:
        science.enable_intervention(
            intervention,
            reason=f"Testing {intervention.value}"
        )
    
    # Run task suite
    suite = NoReportTaskSuiteV2(seed=seed)
    results = suite.run_all()
    
    # End run
    header = science.end_run()
    
    return {
        "run_id": run_id,
        "header": header.to_dict(),
        "results": [r.to_dict() for r in results],
    }

# Run experiments
normal = run_experiment(seed=42, intervention=None)
no_broadcast = run_experiment(seed=42, intervention=InterventionType.DISABLE_BROADCAST)

# Compare
print(f"Normal success rate: {sum(r['success'] for r in normal['results'])/4}")
print(f"No broadcast success rate: {sum(r['success'] for r in no_broadcast['results'])/4}")
```

### Batch Experiments

```python
# Run all intervention combinations
interventions = [
    None,
    InterventionType.DISABLE_BROADCAST,
    InterventionType.DISABLE_HOMEOSTASIS,
    InterventionType.OPEN_LOOP,
]

results = {}
for intervention in interventions:
    name = intervention.value if intervention else "normal"
    results[name] = run_experiment(seed=42, intervention=intervention)

# Generate comparison report
for name, result in results.items():
    success_rate = sum(r['success'] for r in result['results']) / 4
    print(f"{name}: {success_rate:.2%} success rate")
```

## Output Artifacts

### Run Header

Stored in `artifacts/mvp11/header_<run_id>.json`:

```json
{
  "run_id": "science_abc123",
  "seed": 42,
  "science_mode": "enabled",
  "interventions": [
    {
      "action": "enable",
      "intervention_type": "disable_broadcast",
      "params": {},
      "reason": "Testing broadcast effect",
      "ts": 1709568000.0
    }
  ],
  "config_hash": "a1b2c3d4e5f6g7h8"
}
```

### Event Log

Stored in `artifacts/mvp11/<run_id>.jsonl`:

```json
{
  "tick_id": 1,
  "run_id": "science_abc123",
  "schema_version": "mvp11",
  "candidates": [...],
  "chosen_focus": "goal_1",
  "action": {"type": "seek_info", "params": {}},
  "outcome": {"status": "success"},
  "homeostasis_state": {...},
  "efe_terms": {...},
  "governor_decision": {...}
}
```

## Validation Checklist

Before running experiments, verify:

- [ ] Seed is set for reproducibility
- [ ] Run header is saved
- [ ] Intervention is correctly applied
- [ ] Event log captures all MVP11 fields
- [ ] Replay produces same results (determinism)

After running experiments:

- [ ] Causal predictions are validated
- [ ] Zombie v2 shows expected collapse
- [ ] Posterior explanation is traceable
- [ ] Uncertainty sources are identified

## References

- Intervention Types: `emotiond/science/interventions.py`
- Task Suite: `emotiond/science/no_report_tasks_v2.py`
- Zombie Baseline: `emotiond/science/zombie_baseline_v2.py`
- Bayes Updater: `emotiond/science/bayes_updater_v2.py`
- Replay Engine: `scripts/replay_mvp11.py`
- Test Suite: `tests/mvp11/test_no_report_v2_matrix.py`
