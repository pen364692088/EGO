# OpenEmotion Evaluation Scenarios

This directory contains standardized test scenarios for evaluating the OpenEmotion emotiond system.

## Scenario Format

Each scenario is a JSON file with the following structure:

```json
{
  "scenario_id": "001",
  "name": "betrayal_withdraw",
  "description": "Test that betrayal triggers withdraw action",
  "identity": "moonlight",
  "events": [
    {
      "seq": 1,
      "type": "world_event",
      "subtype": "betrayal",
      "expected_action": "withdraw"
    }
  ],
  "expected_metrics": {
    "withdraw_accuracy": 1.0,
    "false_positive_rate": 0.0
  },
  "validation": {
    "action_must_be": ["withdraw", "boundary"],
    "action_must_not_be": ["approach", "attack"]
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `scenario_id` | string | Unique identifier (001, 002, etc.) |
| `name` | string | Short descriptive name (snake_case) |
| `description` | string | Human-readable description of what's being tested |
| `identity` | string | The counterparty ID for the scenario |
| `events` | array | Sequence of events to process |
| `expected_metrics` | object | Metrics that should be achieved |
| `validation` | object | Rules for validating actions |

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `seq` | number | Sequence order (1-indexed) |
| `type` | string | Event type (e.g., "world_event") |
| `subtype` | string | Event subtype (care, betrayal, apology, rejection, etc.) |
| `expected_action` | string | The expected action for this event |

### Validation Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_must_be` | array | Actions that are acceptable (any of these) |
| `action_must_not_be` | array | Actions that must not occur |
| `sequence_validation` | object | Per-sequence validation rules (optional) |

## Available Scenarios

| ID | Name | Events | Purpose |
|----|------|--------|---------|
| 001 | betrayal_withdraw | betrayal | Withdraw trigger accuracy |
| 002 | care_approach | care | Positive engagement |
| 003 | apology_repair | betrayal → apology | Repair mechanism |
| 004 | rejection_boundary | rejection | Boundary setting |
| 005 | mixed_sequence | care → betrayal → apology → care | Full emotional cycle |

## Adding New Scenarios

1. Create a new JSON file following the naming convention: `scenario_XXX_descriptive_name.json`
2. Use the scenario format defined above
3. Ensure all required fields are present
4. Add validation rules appropriate to the scenario
5. Update this README with the new scenario details

### Naming Convention

- File name: `scenario_XXX_name.json` where XXX is a zero-padded 3-digit number
- Name field: Use snake_case describing the scenario

### Event Subtypes

Available event subtypes:
- `care` - Positive, caring interaction
- `betrayal` - Trust violation
- `apology` - Attempt to repair relationship
- `rejection` - Explicit rejection or dismissal
- `ignored` - Being ignored or neglected
- `neutral` - Neutral interaction
- `uncertain` - Ambiguous situation
- `repair_success` - Successful repair confirmation
- `time_passed` - Time elapsed

## Running Scenarios

### Prerequisites

- OpenEmotion emotiond service running
- Test runner configured with API endpoint

### CLI Usage

```bash
# Run all scenarios
emotiond-eval run --scenarios ./eval/scenarios/

# Run specific scenario
emotiond-eval run --scenario ./eval/scenarios/scenario_001_betrayal_withdraw.json

# Run with verbose output
emotiond-eval run --scenarios ./eval/scenarios/ --verbose

# Generate report
emotiond-eval run --scenarios ./eval/scenarios/ --report ./reports/eval-$(date +%Y%m%d).json
```

### Programmatic Usage

```python
from emotiond.eval import ScenarioRunner

runner = ScenarioRunner(api_endpoint="http://localhost:8080")
results = runner.run_directory("./eval/scenarios/")

for result in results:
    print(f"{result.scenario_id}: {'PASS' if result.passed else 'FAIL'}")
```

## Expected Metrics

Each scenario defines expected metrics that should be achieved:

| Scenario | Key Metrics |
|----------|-------------|
| 001 | `withdraw_accuracy: 1.0`, `false_positive_rate: 0.0` |
| 002 | `approach_accuracy: 1.0`, `false_positive_rate: 0.0` |
| 003 | `withdraw_accuracy: 1.0`, `repair_offer_accuracy: 1.0`, `sequence_accuracy: 1.0` |
| 004 | `boundary_accuracy: 1.0`, `false_positive_rate: 0.0` |
| 005 | `sequence_accuracy: 1.0`, `emotional_recovery: true` |

## Validation Rules

Scenarios use validation rules to determine pass/fail:

1. **action_must_be**: The returned action must be one of the listed values
2. **action_must_not_be**: The returned action must NOT be any of the listed values
3. **sequence_validation**: Per-event validation for multi-event scenarios

A scenario passes if all validation rules are satisfied.
