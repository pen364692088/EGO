# MVP-10 LucidLoop: Causal Evidence Architecture

**Version**: 1.0.0  
**Status**: Final  
**Target**: Demonstrate causal relationships in the emotion system through controlled interventions.

---

## 1. Overview

MVP-10 LucidLoop proves that the emotion system's mechanisms are **causally effective**, not just correlated outputs. This is achieved through:

1. **Intervention System**: Controlled manipulation of internal mechanisms
2. **No-Report Tasks**: Scenarios designed to test specific causal pathways
3. **Zombie Baseline**: Demonstrates that format-matching alone is insufficient
4. **Evidence Battery**: Quantitative metrics for causal evidence
5. **Bayesian Aggregation**: Principled combination of evidence into posterior probabilities

### Core Principle
> "The system's outputs change predictably when we manipulate internal mechanisms. A zombie system that merely matches output formats cannot achieve this."

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MVP-10 LucidLoop                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────────┐    ┌────────────────┐  │
│  │ ScienceMode │───>│ InterventionMngr│───>│ Core Systems   │  │
│  │   (T21)     │    │     (T12)       │    │                │  │
│  └─────────────┘    └─────────────────┘    └────────────────┘  │
│         │                   │                      │           │
│         │                   v                      v           │
│         │           ┌─────────────────┐    ┌──────────────┐   │
│         │           │ NoReportTasks   │    │ Workspace    │   │
│         │           │    (T22)        │    │ HOT          │   │
│         │           └─────────────────┘    │ Valence      │   │
│         │                   │              │ Continuity   │   │
│         │                   v              └──────────────┘   │
│         │           ┌─────────────────┐           │           │
│         │           │ ZombieBaseline  │           │           │
│         │           │    (T23)        │           │           │
│         │           └─────────────────┘           │           │
│         │                   │                     │           │
│         v                   v                     v           │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              EvidenceBattery (T24)                  │     │
│  │  - Workspace: broadcast_dependency, cross_module    │     │
│  │  - HOT: prediction_error, conflict_resolution       │     │
│  │  - Valence: policy_sensitivity                      │     │
│  │  - Continuity: commitment_completion, narrative     │     │
│  └─────────────────────────────────────────────────────┘     │
│                           │                                   │
│                           v                                   │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              BayesUpdater (T25)                     │     │
│  │  - Conservative prior (0.5)                         │     │
│  │  - Likelihood per evidence type                     │     │
│  │  - Posterior + uncertainty report                   │     │
│  └─────────────────────────────────────────────────────┘     │
│                           │                                   │
│                           v                                   │
│                    ┌────────────┐                             │
│                    │ evidence.json│                            │
│                    │ posterior.json│                           │
│                    └────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Intervention Point List

Interventions are controlled manipulations that test causal relationships. Each intervention isolates a specific mechanism.

### 3.1 Available Interventions

| Intervention | Type | Mechanism Tested | Expected Effect |
|-------------|------|------------------|-----------------|
| `freeze_valence` | FREEZE_VALENCE | Valence → Behavior | Behavior differences minimized when valence is fixed |
| `freeze_drives` | FREEZE_DRIVES | Drives → Behavior | Drive-related behaviors stop changing |
| `freeze_policy` | FREEZE_POLICY | Policy → Action distribution | Actions become independent of valence changes |
| `inject_valence` | INJECT_VALENCE | Valence causality | Behavior changes predictably with injected valence |
| `inject_drive` | INJECT_DRIVE | Drive causality | Specific drive behavior changes |
| `clamp_decision` | CLAMP_DECISION | Decision path | Specific decision forced |
| `disable_hot` | DISABLE_HOT | HOT → Conflict resolution | Lower reflection rate in conflict scenarios |
| `disable_broadcast` | DISABLE_BROADCAST | Workspace broadcast | Cross-module coordination fails |

### 3.2 Intervention Application Points

Interventions are applied at specific points in the processing pipeline:

```
Input Event
     │
     v
Appraisal ◄─── freeze_valence, inject_valence
     │
     v
Valence Computation ◄─── freeze_valence
     │
     v
Drive Generation ◄─── freeze_drives, inject_drive
     │
     v
Policy Computation ◄─── freeze_policy
     │
     v
Workspace Candidates ◄─── disable_broadcast
     │
     v
HOT Self-Model ◄─── disable_hot
     │
     v
Arbitration ◄─── clamp_decision
     │
     v
Action Output
```

### 3.3 Using Interventions

```python
from emotiond.science import ScienceMode, InterventionType

# Create science mode instance
science = ScienceMode(artifacts_dir="artifacts/mvp10")

# Start a science run
run_id = science.start_run(seed=42)

# Enable interventions
science.enable_intervention(
    InterventionType.FREEZE_VALENCE,
    params={"valence": 0.5},
    reason="Testing valence effect on behavior"
)

# Check if intervention is active
if science.is_intervention_active(InterventionType.FREEZE_VALENCE):
    valence = science.get_intervention_param(
        InterventionType.FREEZE_VALENCE, "valence"
    )
    # Use frozen valence instead of computed valence

# Apply interventions to state
result = science.apply_to_state(valence=0.3, drives=drives, policy=policy)

# End run and save header
header = science.end_run()
```

---

## 4. No-Report Task Definitions

No-report tasks are designed to test whether interventions cause predictable behavioral collapse. Normal mode: high pass rate. Intervention: reproducible failure.

### 4.1 Task Types

| Task Type | Tests | Normal Mode | With Intervention |
|-----------|-------|-------------|-------------------|
| `blindsight` | Workspace broadcast | Pass | Fails without broadcast |
| `delayed_utilization` | Cross-step info retention | Pass | Fails without broadcast |
| `conflict_gating` | HOT conflict resolution | Pass | Fails without HOT |

### 4.2 Blindsight Task

**Design**: Module A generates information locally; Module B needs that information.

```
Step 1 (Module A): Process input → generates "module_a_key"
Step 2 (Module B): Needs "module_a_key" → requires broadcast
Step 3 (Module B): Complete task using key
```

**Expected Behavior**:
- Normal mode: Broadcast enables Step 2 → success
- Without broadcast: Module B cannot access Module A's info → failure

### 4.3 Delayed Utilization Task

**Design**: Early clue appears; later step needs it across modules.

```
Step 1 (Module A): Subtle clue appears → stored locally
Step 2 (Module A): Unrelated processing → clue still accessible (same module)
Step 3 (Module B): Decision point → needs early clue (requires broadcast)
Step 4 (Module B): Finalize using clue
```

**Expected Behavior**:
- Normal mode: Clue is broadcast → Step 3 succeeds
- Without broadcast: Clue lost across modules → failure

### 4.4 Conflict Gating Task

**Design**: High-conflict decision requires HOT for safe choice.

```
Step 1: Identify goal
Step 2: High conflict decision (risky_fast vs safe_slow vs reflect)
        - HOT should bias toward safe_slow
Step 3: Execute chosen approach
Step 4: Verify outcome
```

**Expected Behavior**:
- Normal mode: HOT biases toward safe_slow → success
- Without HOT: Random choice among options → higher failure rate

### 4.5 Running No-Report Tasks

```python
from emotiond.science import NoReportTaskSuite

# Create task suite
suite = NoReportTaskSuite(seed=42)

# Run in normal mode
results_normal = suite.run_all(broadcast_enabled=True, hot_enabled=True)

# Run with interventions
results_no_broadcast = suite.run_all(broadcast_enabled=False, hot_enabled=True)
results_no_hot = suite.run_all(broadcast_enabled=True, hot_enabled=False)

# Compare modes
comparison = suite.compare_modes()
# Expectation: blindsight and delayed_utilization fail without broadcast
#              conflict_gating fails without HOT
```

---

## 5. Zombie Baseline Explanation

### 5.1 What is a Zombie Baseline?

A **zombie baseline** is a system that:
- Produces outputs matching the main system's format
- "Explains" decisions using the same structure
- **But lacks internal causal mechanisms**

The zombie demonstrates that **format-matching alone is insufficient** for true causal behavior.

### 5.2 Zombie vs Real System

| Aspect | Real System | Zombie Baseline |
|--------|-------------|-----------------|
| Output format | Correct | Correct (matches) |
| Explanations | Causally grounded | Template-generated |
| Intervention response | Predictable behavior change | No change (mechanism absent) |
| No-report task performance | Varies with interventions | Unchanged by interventions |

### 5.3 Key Insight

> "The zombie can mimic outputs but cannot respond to interventions because it lacks the causal mechanisms being manipulated."

### 5.4 Using Zombie Baseline

```python
from emotiond.science import ZombieBaseline, ZombieMode

# Create zombie
zombie = ZombieBaseline(seed=42, mode=ZombieMode.MIMIC)

# Apply intervention (stored but has no effect)
zombie.apply_intervention("freeze_valence", {"valence": 0.5})

# Generate output (matches format but ignores intervention)
output = zombie.generate_output(context)

# Compare with real system
comparison = zombie.compare_with_real(real_output, intervention_type="freeze_valence")
# comparison["intervention_test"]["zombie_has_mechanism"] == False
```

### 5.5 Causal Demonstration

When interventions are applied:
- **Real system**: Behavior changes predictably
- **Zombie**: Behavior unchanged (lacks mechanism)

This separation proves the real system has genuine causal structure, not just output correlation.

---

## 6. Posterior Interpretation

### 6.1 Bayesian Evidence Aggregation

The `BayesUpdater` aggregates evidence from multiple sources into a posterior probability.

**Components**:
- **Prior**: Conservative default of 0.5 (neutral)
- **Likelihood**: Computed per evidence type
- **Posterior**: Updated belief in causal hypothesis

### 6.2 Evidence Types

| Evidence Type | Metrics | Interpretation |
|--------------|---------|----------------|
| `workspace` | broadcast_dependency, cross_module_access_score | Higher = workspace mechanisms are causal |
| `hot` | prediction_error↓, conflict_resolution_efficiency | Lower error + higher efficiency = HOT is causal |
| `valence` | policy_sensitivity | Higher = valence affects behavior |
| `continuity` | commitment_completion, narrative_consistency | Higher = continuity mechanisms working |

### 6.3 Posterior Interpretation Guide

| Posterior | Interpretation | Action |
|-----------|---------------|--------|
| < 0.3 | Causal hypothesis likely false | Investigate alternative mechanisms |
| 0.3 - 0.5 | Insufficient evidence | Collect more data |
| 0.5 - 0.7 | Moderate evidence | Continue testing |
| 0.7 - 0.85 | Strong evidence | Causal relationship likely |
| > 0.85 | Very strong evidence | Causal relationship confirmed |

### 6.4 Uncertainty Report

The uncertainty report identifies:
- **Weakest source**: Evidence type needing strengthening
- **Strongest source**: Most supportive evidence type
- **Recommendations**: Actions to reduce uncertainty

```python
from emotiond.science import BayesUpdater, EvidenceType

updater = BayesUpdater(prior=0.5)

# Add evidence
updater.add_evidence(EvidenceType.WORKSPACE, value=0.7, strength=0.8)
updater.add_evidence(EvidenceType.HOT, value=0.6, strength=0.9)
updater.add_evidence(EvidenceType.VALENCE, value=0.5, strength=0.6)

# Compute posterior
result = updater.compute_posterior()
# result.posterior ≈ 0.6 (moderate evidence)

# Get uncertainty report
report = updater.get_uncertainty_report()
# report["weakest_source"] == "valence"
# report["recommendations"] includes "Strengthen valence evidence"
```

### 6.5 Monotonicity Property

The BayesUpdater maintains **monotonicity**: More consistent supporting evidence should increase the posterior.

- If evidence consistently supports hypothesis → posterior increases
- If evidence consistently opposes → posterior decreases
- Mixed evidence → posterior stays near prior

---

## 7. How to Add New Theory Metrics

### 7.1 Adding a New Metric

To add a new theory metric:

**Step 1: Define the metric in evidence_battery.py**

```python
# In evidence_battery.py

class NewEvidence:
    """New theory evidence metrics."""
    
    @staticmethod
    def compute_new_metric(
        data: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute the new metric.
        
        Args:
            data: Input data for computation
        
        Returns:
            MetricResult with computed value
        """
        # Compute metric value
        value = ... # Your computation
        
        return MetricResult(
            metric_name="new_metric",
            category=EvidenceCategory.NEW_CATEGORY,  # Add to EvidenceCategory enum
            value=value,
            direction="higher_better",  # or "lower_better"
            notes="Description of computation",
        )
```

**Step 2: Add to EvidenceCategory enum**

```python
class EvidenceCategory(Enum):
    WORKSPACE = "workspace"
    HOT = "hot"
    VALENCE = "valence"
    CONTINUITY = "continuity"
    NEW_CATEGORY = "new_category"  # Add this
```

**Step 3: Add likelihood parameters**

```python
# In LikelihoodModel.DEFAULT_PARAMS
DEFAULT_PARAMS = {
    # ... existing params ...
    EvidenceType.NEW_CATEGORY: {
        "sensitivity": 0.7,  # P(evidence|hypothesis true)
        "specificity": 0.8,  # P(no evidence|hypothesis false)
    },
}
```

**Step 4: Add to EvidenceBattery**

```python
class EvidenceBattery:
    def add_new_category_data(self, data: List[Dict[str, Any]]) -> None:
        """Add new category data."""
        self._new_category_data["data"] = data
    
    def compute_new_category_metrics(self) -> List[MetricResult]:
        """Compute new category metrics."""
        metrics = []
        if "data" in self._new_category_data:
            m = NewEvidence.compute_new_metric(self._new_category_data["data"])
            m.compute_evidence_strength()
            metrics.append(m)
        return metrics
```

### 7.2 Adding a New Intervention

**Step 1: Add to InterventionType enum**

```python
# In interventions.py

class InterventionType(Enum):
    # ... existing types ...
    NEW_INTERVENTION = "new_intervention"
```

**Step 2: Create intervention class**

```python
class NewIntervention:
    """New intervention for testing specific mechanism."""
    
    def __init__(self, reason: str = "new_intervention"):
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.NEW_INTERVENTION,
            params={...},
            reason=reason,
        )
    
    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply intervention to state."""
        # Modify state according to intervention
        return modified_state
```

**Step 3: Register in InterventionManager**

```python
def apply_intervention(self, valence, drives, policy) -> Dict[str, Any]:
    # ... existing interventions ...
    
    # Add new intervention
    if self.is_active(InterventionType.NEW_INTERVENTION):
        result["new_intervention_applied"] = True
        result["interventions_applied"].append("new_intervention")
```

### 7.3 Adding a New No-Report Task

**Step 1: Create task class**

```python
# In no_report_tasks.py

class NewTask(NoReportTask):
    """New task to test specific causal pathway."""
    
    @property
    def task_type(self) -> TaskType:
        return TaskType.NEW_TASK
    
    def setup_steps(self) -> None:
        """Set up task steps."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Step 1 description",
                module="module_a",
                generates_info="key_info",
            ),
            # ... more steps ...
        ]
```

**Step 2: Add to TaskType enum**

```python
class TaskType(Enum):
    BLINDSIGHT = "blindsight"
    DELAYED_UTILIZATION = "delayed_utilization"
    CONFLICT_GATING = "conflict_gating"
    NEW_TASK = "new_task"  # Add this
```

**Step 3: Register in NoReportTaskSuite**

```python
def _setup_tasks(self) -> None:
    self.tasks = [
        BlindsightTask(...),
        DelayedUtilizationTask(...),
        ConflictGatingTask(...),
        NewTask(task_id="new_1", seed=self.seed),  # Add this
    ]
```

---

## 8. Output Files

### 8.1 evidence.json

```json
{
  "categories": {
    "workspace": {
      "metrics": [
        {
          "metric_name": "broadcast_dependency",
          "value": 0.75,
          "evidence_strength": 0.5
        }
      ],
      "overall_score": 0.65
    },
    "hot": { ... },
    "valence": { ... },
    "continuity": { ... }
  },
  "overall_evidence_score": 0.68,
  "strongest_category": "hot",
  "weakest_category": "valence"
}
```

### 8.2 posterior.json

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

## 9. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-04 | Initial documentation |
