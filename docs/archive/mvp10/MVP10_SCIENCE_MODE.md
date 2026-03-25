# MVP-10 Science Mode Guide

**Version**: 1.0.0  
**Status**: Final  
**Purpose**: Guide for running controlled experiments with science mode interventions.

---

## 1. What is Science Mode?

Science Mode is a unified interface for running controlled experiments on the emotion system. It allows:

1. **Enabling/disabling interventions** with traceable logging
2. **Injecting parameters** for controlled experiments
3. **Logging all interventions** to run headers for reproducibility
4. **Comparing performance** across intervention configurations

### Key Principle
> All interventions go through a single interface. No scattered if-else checks across the codebase.

---

## 2. Quick Start

### 2.1 Basic Usage

```python
from emotiond.science import ScienceMode, InterventionType

# Create science mode instance
science = ScienceMode(artifacts_dir="artifacts/mvp10")

# Start a science run with a seed for reproducibility
run_id = science.start_run(seed=42)

# Enable an intervention
science.enable_intervention(
    InterventionType.FREEZE_VALENCE,
    params={"valence": 0.5},
    reason="Testing valence effect on decision making"
)

# Check if intervention is active
if science.is_intervention_active(InterventionType.FREEZE_VALENCE):
    # Get the frozen valence parameter
    valence = science.get_intervention_param(
        InterventionType.FREEZE_VALENCE, "valence", default=0.0
    )
    # Use frozen valence in processing...

# Apply all active interventions to state
result = science.apply_to_state(
    valence=current_valence,
    drives=current_drives,
    policy=current_policy
)

# End the run and get the header
header = science.end_run()
print(f"Run {header.run_id} completed with hash {header.config_hash}")
```

### 2.2 Running the Evaluation Script

```bash
# Quick mode: Core loop + key tests
python scripts/eval_mvp10.py --mode quick

# Science mode: Full intervention matrix + evidence + posterior
python scripts/eval_mvp10.py --mode science

# Replay mode: Verify determinism
python scripts/eval_mvp10.py --mode replay

# Compare with zombie baseline
python scripts/eval_mvp10.py --mode science --compare zombie
```

---

## 3. Intervention Point List

### 3.1 Complete Intervention Reference

| Intervention | Effect | Use Case |
|-------------|--------|----------|
| `FREEZE_VALENCE` | Locks valence to fixed value | Test if valence causally affects behavior |
| `FREEZE_DRIVES` | Locks drive levels | Test drive → behavior relationship |
| `FREEZE_POLICY` | Locks policy parameters | Test policy stability |
| `INJECT_VALENCE` | Injects specific valence value | Test valence causality |
| `INJECT_DRIVE` | Injects specific drive level | Test drive causality |
| `CLAMP_DECISION` | Forces specific decision | Test decision path |
| `DISABLE_HOT` | Disables HOT self-model influence | Test HOT's causal role |
| `DISABLE_BROADCAST` | Disables workspace broadcast | Test broadcast's causal role |

### 3.2 Intervention Application Flow

```
                        ┌─────────────────┐
                        │  ScienceMode    │
                        │   start_run()   │
                        └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         v                       v                       v
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ enable_interv.  │   │ enable_interv.  │   │ enable_interv.  │
│ FREEZE_VALENCE  │   │  DISABLE_HOT    │   │DISABLE_BROADCAST│
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 v
                        ┌─────────────────┐
                        │ apply_to_state  │
                        │   valence       │
                        │   drives        │
                        │   policy        │
                        └────────┬────────┘
                                 │
                                 v
                        ┌─────────────────┐
                        │ Modified State  │
                        │ + Applied Log   │
                        └────────┬────────┘
                                 │
                                 v
                        ┌─────────────────┐
                        │    end_run()    │
                        │  RunHeader saved│
                        └─────────────────┘
```

### 3.3 Specialized Intervention Classes

For convenience, specialized classes provide streamlined interfaces:

```python
from emotiond.science import (
    FreezeValenceIntervention,
    DisableHOTIntervention,
    DisableBroadcastIntervention,
)

# Freeze valence
freeze = FreezeValenceIntervention(valence=0.5)
modified_valence = freeze.apply(current_valence)

# Disable HOT
disable_hot = DisableHOTIntervention()
if disable_hot.is_active():
    modified_hot_state = disable_hot.apply_to_hot_state(hot_state)

# Disable broadcast
disable_broadcast = DisableBroadcastIntervention()
filtered_candidates = disable_broadcast.filter_candidates(
    candidates, local_source="local"
)
```

---

## 4. No-Report Task Definitions

### 4.1 Purpose

No-report tasks are designed to demonstrate **reproducible collapse** when key mechanisms are disabled. They test whether the system's performance depends on specific causal pathways.

### 4.2 Task Categories

| Task | Mechanism Tested | Collapse Condition |
|------|-----------------|-------------------|
| Blindsight | Workspace broadcast | Fails when broadcast disabled |
| Delayed Utilization | Cross-module info retention | Fails when broadcast disabled |
| Conflict Gating | HOT conflict resolution | Fails when HOT disabled |

### 4.3 Running Tasks

```python
from emotiond.science import NoReportTaskSuite

# Create task suite
suite = NoReportTaskSuite(seed=42)

# Run individual tasks
from emotiond.science import BlindsightTask, DelayedUtilizationTask, ConflictGatingTask

# Blindsight task
blindsight = BlindsightTask(task_id="blindsight_1", seed=42)
result_normal = blindsight.run(broadcast_enabled=True, hot_enabled=True)
result_disabled = blindsight.run(broadcast_enabled=False, hot_enabled=True)
# Expectation: result_normal.success=True, result_disabled.success=False

# Delayed utilization task
delayed = DelayedUtilizationTask(task_id="delayed_1", seed=42)
result_normal = delayed.run(broadcast_enabled=True, hot_enabled=True)
result_disabled = delayed.run(broadcast_enabled=False, hot_enabled=True)
# Expectation: result_normal.success=True, result_disabled.success=False

# Conflict gating task
conflict = ConflictGatingTask(task_id="conflict_1", seed=42)
result_normal = conflict.run(broadcast_enabled=True, hot_enabled=True)
result_disabled = conflict.run(broadcast_enabled=True, hot_enabled=False)
# Expectation: result_normal.success=True, result_disabled.success=False (higher failure rate)
```

### 4.4 Task Result Structure

```python
@dataclass
class TaskResult:
    task_id: str              # Task identifier
    task_type: TaskType       # BLINDSIGHT, DELAYED_UTILIZATION, CONFLICT_GATING
    success: bool             # Overall success
    steps_completed: int      # Number of steps completed
    total_steps: int          # Total steps in task
    broadcast_used: bool      # Whether broadcast was needed
    hot_used: bool            # Whether HOT was needed
    info_captured: Dict       # Information generated during task
    decisions: List[Dict]     # Decision records
    error_type: Optional[str] # Type of error if failed
```

### 4.5 Mode Comparison

```python
# Compare performance across all modes
comparison = suite.compare_modes()

# comparison structure:
{
    "normal": {
        "success_rate": 1.0,  # All tasks pass
        "broadcast_used": [True, True, False],
        "hot_used": [False, False, True],
    },
    "no_broadcast": {
        "success_rate": 0.33,  # Only conflict_gating passes
    },
    "no_hot": {
        "success_rate": 0.67,  # Blindsight and delayed pass
    },
    "neither": {
        "success_rate": 0.0,  # All fail
    },
    "separation": {
        "blindsight": {
            "normal_success": True,
            "no_broadcast_success": False,
            "expected_collapse": True,
        },
        # ... other tasks
    },
}
```

---

## 5. Zombie Baseline Explanation

### 5.1 Concept

A **zombie baseline** is a control system that:
- Matches output format exactly
- Generates plausible explanations
- **Lacks internal causal mechanisms**

### 5.2 Why Zombie Baseline?

The zombie demonstrates that **format-matching ≠ causal structure**.

| Test | Real System | Zombie |
|------|-------------|--------|
| Normal operation | Works | Works (mimics) |
| With intervention | Behavior changes | No change |
| Causal mechanism | Present | Absent |

### 5.3 Using Zombie Baseline

```python
from emotiond.science import ZombieBaseline, ZombieMode

# Create zombie in MIMIC mode (tries to mimic observed patterns)
zombie = ZombieBaseline(seed=42, mode=ZombieMode.MIMIC)

# "Apply" intervention (stored but has no effect)
zombie.apply_intervention("freeze_valence", {"valence": 0.5})

# Generate output
output = zombie.generate_output(context={"valence": -0.3})
# Note: output.valence will NOT be 0.5 (intervention ignored)

# Compare with real system
real_output = real_system.generate_output(context)
comparison = zombie.compare_with_real(real_output, intervention_type="freeze_valence")

# Key check:
assert comparison["intervention_test"]["zombie_has_mechanism"] == False
```

### 5.4 Zombie Modes

| Mode | Behavior |
|------|----------|
| `RANDOM` | Generates random outputs |
| `MIMIC` | Tries to mimic observed patterns from context |
| `TEMPLATE` | Uses fixed templates for outputs |

### 5.5 Demonstration of Causal Separation

```python
def demonstrate_causal_separation():
    """Show that zombie cannot respond to interventions."""
    
    real_system = RealSystem()
    zombie = ZombieBaseline(seed=42)
    
    # Both systems generate similar outputs normally
    real_normal = real_system.generate_output(context)
    zombie_normal = zombie.generate_output(context)
    
    # Apply intervention
    real_system.apply_intervention("freeze_valence", {"valence": 0.5})
    zombie.apply_intervention("freeze_valence", {"valence": 0.5})
    
    # Generate outputs with intervention
    real_intervened = real_system.generate_output(context)
    zombie_intervened = zombie.generate_output(context)
    
    # Real system: valence should be 0.5 (frozen)
    assert real_intervened.valence == 0.5
    
    # Zombie: valence unchanged (intervention ignored)
    assert zombie_intervened.valence != 0.5  # Not frozen
    
    # This proves real system has causal mechanism
```

---

## 6. Posterior Interpretation

### 6.1 Bayesian Framework

Science Mode uses Bayesian updating to aggregate evidence:

```
Prior P(H) = 0.5  (conservative, neutral)

For each evidence item:
  Likelihood P(E|H) computed from evidence type
  
Posterior P(H|E) ∝ P(E|H) × P(H)
```

### 6.2 Evidence Categories

| Category | Metrics | Higher Value Means |
|----------|---------|-------------------|
| `workspace` | broadcast_dependency, cross_module_access | Workspace mechanisms are causal |
| `hot` | prediction_error↓, conflict_resolution | HOT mechanisms are causal |
| `valence` | policy_sensitivity | Valence affects behavior |
| `continuity` | commitment_completion, narrative_consistency | Continuity mechanisms work |

### 6.3 Interpreting Results

```python
from emotiond.science import BayesUpdater, EvidenceType

updater = BayesUpdater(prior=0.5)  # Conservative prior

# Add evidence from experiments
updater.add_evidence(
    EvidenceType.WORKSPACE,
    value=0.75,  # Strong broadcast dependency
    strength=0.8,  # High confidence in this evidence
    notes="Blindsight task failed without broadcast"
)

updater.add_evidence(
    EvidenceType.HOT,
    value=0.65,
    strength=0.7,
    notes="Conflict resolution worse without HOT"
)

# Compute posterior
result = updater.compute_posterior()

# Interpretation guide:
# posterior < 0.3: Hypothesis likely false
# 0.3 - 0.5: Insufficient evidence
# 0.5 - 0.7: Moderate evidence
# 0.7 - 0.85: Strong evidence
# > 0.85: Very strong evidence

if result.posterior > 0.7:
    print("Strong evidence for causal hypothesis")
    print(f"Weakest source: {result.weakest_source}")
    print(f"Recommendations: {updater.get_uncertainty_report()['recommendations']}")
```

### 6.4 Uncertainty Report

```python
report = updater.get_uncertainty_report()

# report structure:
{
    "posterior": 0.72,
    "uncertainty": 0.25,
    "weakest_source": "valence",
    "strongest_source": "workspace",
    "evidence_by_type": {
        "workspace": {"count": 2, "avg_value": 0.75, ...},
        "hot": {"count": 1, "avg_value": 0.65, ...},
        "valence": {"count": 0},  # Missing!
        "continuity": {"count": 0},  # Missing!
    },
    "recommendations": [
        "Strengthen valence evidence",
        "Missing evidence types: valence, continuity"
    ]
}
```

### 6.5 Monotonicity Guarantee

The BayesUpdater guarantees **monotonicity**:

- **Supporting evidence** (value > 0.5) → posterior increases
- **Opposing evidence** (value < 0.5) → posterior decreases
- More consistent evidence → stronger posterior shift

```python
# Demonstrate monotonicity
updater = BayesUpdater(prior=0.5)

# Add supporting evidence
updater.add_evidence(EvidenceType.WORKSPACE, value=0.7, strength=0.8)
result1 = updater.compute_posterior()
assert result1.posterior > 0.5  # Increased

# Add more supporting evidence
updater.add_evidence(EvidenceType.HOT, value=0.8, strength=0.9)
result2 = updater.compute_posterior()
assert result2.posterior > result1.posterior  # Further increased

# Add opposing evidence
updater.add_evidence(EvidenceType.VALENCE, value=0.3, strength=0.5)
result3 = updater.compute_posterior()
assert result3.posterior < result2.posterior  # Decreased
```

---

## 7. How to Add New Theory Metrics

### 7.1 Adding a Metric

**Step 1: Define the metric**

```python
# In evidence_battery.py

class NewTheoryEvidence:
    """Evidence metrics for new theory."""
    
    @staticmethod
    def compute_new_metric(data: List[Dict]) -> MetricResult:
        """
        Compute new metric.
        
        Args:
            data: Input data
        
        Returns:
            MetricResult with computed value
        """
        # Your computation here
        value = len([d for d in data if d.get("success")]) / len(data)
        
        return MetricResult(
            metric_name="new_metric",
            category=EvidenceCategory.NEW_THEORY,
            value=value,
            direction="higher_better",
            notes="Description",
        )
```

**Step 2: Add to enum**

```python
class EvidenceCategory(Enum):
    WORKSPACE = "workspace"
    HOT = "hot"
    VALENCE = "valence"
    CONTINUITY = "continuity"
    NEW_THEORY = "new_theory"  # Add this
```

**Step 3: Add likelihood parameters**

```python
# In LikelihoodModel
DEFAULT_PARAMS = {
    # ... existing ...
    EvidenceType.NEW_THEORY: {
        "sensitivity": 0.7,
        "specificity": 0.8,
    },
}
```

### 7.2 Adding an Intervention

**Step 1: Add type**

```python
class InterventionType(Enum):
    # ... existing ...
    NEW_INTERVENTION = "new_intervention"
```

**Step 2: Create class**

```python
class NewIntervention:
    def __init__(self, param: float):
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.NEW_INTERVENTION,
            params={"param": param},
            reason="new_intervention",
        )
    
    def apply(self, state: Dict) -> Dict:
        # Modify state
        state["new_field"] = self.manager.get_config(
            InterventionType.NEW_INTERVENTION
        ).params["param"]
        return state
```

**Step 3: Register in manager**

```python
# In InterventionManager.apply_intervention
if self.is_active(InterventionType.NEW_INTERVENTION):
    result["interventions_applied"].append("new_intervention")
```

### 7.3 Adding a Task

**Step 1: Create task**

```python
class NewTask(NoReportTask):
    @property
    def task_type(self) -> TaskType:
        return TaskType.NEW_TASK
    
    def setup_steps(self) -> None:
        self.steps = [
            TaskStep(step_id=1, description="...", module="a", ...),
            # ...
        ]
```

**Step 2: Add to enum**

```python
class TaskType(Enum):
    # ... existing ...
    NEW_TASK = "new_task"
```

**Step 3: Add to suite**

```python
def _setup_tasks(self) -> None:
    self.tasks = [
        # ... existing ...
        NewTask(task_id="new_1", seed=self.seed),
    ]
```

---

## 8. Output Files

### 8.1 Run Header

Saved to `artifacts/mvp10/header_<run_id>.json`:

```json
{
  "run_id": "science_abc123",
  "seed": 42,
  "science_mode": "enabled",
  "interventions": [
    {
      "action": "enable",
      "intervention_type": "freeze_valence",
      "params": {"valence": 0.5},
      "reason": "Testing valence effect",
      "ts": 1709563200.0
    }
  ],
  "config_hash": "a1b2c3d4e5f6",
  "metadata": {}
}
```

### 8.2 Evidence JSON

Saved to `artifacts/mvp10/evidence.json`:

```json
{
  "categories": {
    "workspace": {
      "metrics": [
        {"metric_name": "broadcast_dependency", "value": 0.75, ...}
      ],
      "overall_score": 0.65
    }
  },
  "overall_evidence_score": 0.68,
  "strongest_category": "workspace",
  "weakest_category": "valence"
}
```

### 8.3 Posterior JSON

Saved to `artifacts/mvp10/posterior.json`:

```json
{
  "prior": 0.5,
  "posterior": 0.72,
  "log_likelihood": 2.45,
  "evidence_count": 8,
  "uncertainty": 0.25,
  "weakest_source": "valence",
  "strongest_source": "workspace"
}
```

---

## 9. Best Practices

### 9.1 Reproducibility

- Always set a **seed** when starting a run
- Save **run headers** for all experiments
- Use **config_hash** to verify intervention consistency

### 9.2 Evidence Collection

- Collect evidence from **all categories** when possible
- Document the **reason** for each intervention
- Use the **uncertainty report** to identify gaps

### 9.3 Interpreting Results

- Posterior > 0.7: Good evidence for causal hypothesis
- Check **weakest_source** to identify what needs strengthening
- Compare with **zombie baseline** to confirm genuine causality

### 9.4 Common Patterns

```python
# Pattern 1: Full intervention test
def test_intervention_effect():
    science = ScienceMode()
    science.start_run(seed=42)
    
    # Baseline
    baseline = run_task(broadcast_enabled=True, hot_enabled=True)
    
    # With intervention
    science.enable_intervention(InterventionType.DISABLE_BROADCAST)
    intervened = run_task(broadcast_enabled=False, hot_enabled=True)
    
    # Compare
    assert baseline.success and not intervened.success
    
    science.end_run()

# Pattern 2: Evidence aggregation
def collect_evidence():
    updater = BayesUpdater(prior=0.5)
    
    for intervention_type in [InterventionType.DISABLE_BROADCAST, ...]:
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(intervention_type)
        
        result = run_experiments()
        
        updater.add_evidence(
            evidence_type_for(intervention_type),
            value=result.performance_gap,
            strength=result.confidence
        )
        
        science.end_run()
    
    return updater.compute_posterior()
```

---

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-04 | Initial documentation |
