# P2-A.2 Postcondition Validation Specification

## Overview

Postcondition validation ensures that tool execution results match user intent, preventing "fake completed" scenarios.

## Problem Statement

Before P2-A.2:
- User requests: "看看 /home/docs 里有哪些文件"
- System executes: `list_dir(".")` (wrong path)
- System returns: `completed` (incorrect)

After P2-A.2:
- System parses intent: `list_dir("/home/docs")`
- System executes: `list_dir("/home/docs")`
- System validates: actual_path == expected_path
- If mismatch: returns `INTENT_MISMATCH` failure

## Validation Rules

### Path Match Validation
```python
expected_path = "/home/user/docs"
actual_path = "/home/user"  # Wrong!

# Result: path_match = False
# Failure: INTENT_MISMATCH
```

### Existence Check (for write/mkdir)
```python
# For WRITE_FILE and MKDIR operations
if not os.path.exists(target_path):
    # Result: exists_check = False
    # Failure: POSTCONDITION_FAILED
```

## Failure Classes

| Failure Class | When Used |
|--------------|-----------|
| `INTENT_MISMATCH` | Actual path differs from expected path |
| `POSTCONDITION_FAILED` | File/directory doesn't exist after creation |
| `PATH_EXTRACTION_ERROR` | Could not parse target path from request |

## PostconditionResult Structure

```python
@dataclass
class PostconditionResult:
    success: bool              # Overall validation result
    actual_path: Optional[str] # Path actually used
    expected_path: Optional[str] # Path from intent
    path_match: bool           # Do paths match?
    operation_match: bool      # Did operation match?
    exists_check: bool         # Does target exist?
    violations: List[str]      # List of violations
```

## Integration

Postcondition validation is called in `task_runtime.py`:

```python
from app.runtime.postcondition import validate_postcondition

# Execute tool
tool_result = execute_list_dir(intent, ...)

# Validate result
validated = validate_postcondition(intent, actual_path, tool_result)

# If postcondition fails, success becomes False
if not validated.success:
    # Task will be marked as FAILED, not COMPLETED
```

## Examples

### Example 1: Path Mismatch Detection
```python
intent = parse_intent("看看 /home/docs 里有哪些文件")
# intent.target_path = "/home/docs"

# Tool accidentally lists wrong directory
tool_result = UnifiedExecutionResult.success_result(
    summary="List success",
    output="file1, file2"
)

# Validate with wrong path
validated = validate_postcondition(intent, "/home", tool_result)

# Result:
# validated.success = False
# validated.failure_class = FailureClass.INTENT_MISMATCH
```

### Example 2: File Creation Verification
```python
intent = parse_intent("在 /tmp 里创建 test.md 文件")
# intent.target_path = "/tmp/test.md"

# Tool creates file
create_file("/tmp/test.md")

# Validate
validated = validate_postcondition(intent, "/tmp/test.md", tool_result)

# Result (if file exists):
# validated.success = True
# validated.exists_check = True
```

## Testing

Run tests:
```bash
python -m pytest tests/test_p2_a2_intent.py::TestPostconditionValidator -v
```

## Impact on Task Status

| Scenario | Pre-P2-A.2 | Post-P2-A.2 |
|----------|-----------|-------------|
| Tool success, wrong path | COMPLETED | FAILED (INTENT_MISMATCH) |
| Tool success, correct path | COMPLETED | COMPLETED |
| Tool failure | FAILED | FAILED (original class) |
| File not created | COMPLETED | FAILED (POSTCONDITION_FAILED) |
