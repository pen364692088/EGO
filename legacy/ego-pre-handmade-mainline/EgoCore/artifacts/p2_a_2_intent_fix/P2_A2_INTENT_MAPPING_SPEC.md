# P2-A.2 Intent Mapping Specification

## Overview

The Intent Mapper (`app/runtime/intent_mapper.py`) parses natural language requests into structured operation intents before tool execution.

## Supported Operations

| Operation | Description | Example Input |
|-----------|-------------|---------------|
| `list_dir` | List directory contents | "看看 /home/docs 里有哪些文件" |
| `read_file` | Read file content | "读取 /home/test.py 文件" |
| `write_file` | Create/write file | "在 /tmp 里创建 test.md 文件" |
| `mkdir` | Create directory | "创建 /home/newdir 目录" |
| `exists` | Check if path exists | "检查 /home/test 是否存在" |

## Intent Structure

```python
@dataclass
class OperationIntent:
    operation: OperationType      # Type of operation
    target_path: Optional[str]    # Target file/directory path
    target_name: Optional[str]    # Filename (for write_file)
    content: Optional[str]        # Content (for write_file)
    confidence: float             # Parsing confidence (0-1)
    raw_text: str                 # Original user text
    extraction_notes: List[str]   # Debug info
```

## Pattern Matching

The mapper uses regex patterns to identify operations:

### LIST_DIR Patterns
```
看看\s*(.+?)\s*[里裡]?\s*(?:有)?哪些文件
列出\s*(.+?)\s*(?:目录|目錄|文件|檔案)
(?:查看|看看|展示|显示|列出)\s*(.+?)\s*(?:目录|目錄)
```

### WRITE_FILE Patterns
```
(?:在|于)\s*(.+?)\s*[里裡下]?\s*(?:创建|建立|新建|写|写入)\s*(?:一个)?\s*(.+?\.\w+)\s*(?:文件)?
```

### READ_FILE Patterns
```
(?:读取|阅读|打开|查看|看看)\s*(.+?\.[a-zA-Z0-9]+)\s*(?:文件)?(?:内容)?
```

## Path Extraction

The mapper handles:
- Absolute paths: `/home/user/docs`
- Trailing slashes: `/home/user/docs/`
- Chinese suffixes: `/home/user/docs里`, `/home/user/docs下`
- File extensions: `test.md`, `config.json`

## Integration

Intent parsing is called in `task_runtime.py`:

```python
from app.runtime.intent_mapper import parse_intent

intent = parse_intent(step_description)

if intent.operation == OperationType.LIST_DIR:
    return self._execute_list_dir(intent, tool_registry, evidence)
```

## Testing

Run tests:
```bash
python -m pytest tests/test_p2_a2_intent.py -v
```

## Future Enhancements

1. Support relative paths with working directory context
2. Support glob patterns (e.g., `*.md`)
3. Support multiple operations in one request
4. Add confidence threshold for unknown intent fallback
