# Trace Rotation Implementation

## Overview

This document describes the trace rotation and cleanup strategy implemented for the Emotiond Bridge Hook.

## Naming Convention

**Before (v1.3):** `traces/<target_id>.jsonl`
**After (v1.4):** `traces/<target_id>-<YYYY-MM-DD>.jsonl`

Example: `traces/telegram-8420019401-2024-02-28.jsonl`

## Rotation Strategy: Date-Based

We chose **date-based rotation** over size-based for the following reasons:

1. **Predictability**: File names are deterministic and easy to understand
2. **Debugging**: Easy to find traces for a specific date
3. **Retention**: Natural fit for time-based retention policies
4. **Simplicity**: No need to check file sizes on every write

### How It Works

- Each day, a new trace file is created automatically
- Multiple writes on the same day append to the same file
- The date is extracted from the system clock at write time

## Retention Policy

- **Default:** Keep files from the last 7 days
- **Configurable:** Via `EMOTIOND_TRACE_RETENTION_DAYS` environment variable
- **Cleanup Frequency:** Every 1 hour (throttled), configurable via `EMOTIOND_TRACE_CLEANUP_INTERVAL_MS`

### Cleanup Process

1. List files in `integrations/openclaw/traces/`
2. Filter to only files matching pattern `<target_id>-YYYY-MM-DD.jsonl`
3. Delete files with dates older than retention period
4. Log results

## Safety Measures

1. **Pattern Matching**: Only files matching `^(.+)-(\d{4}-\d{2}-\d{2})\.jsonl$` are processed
2. **Path Validation**: All paths are validated to be within the traces directory
3. **No Outside Deletion**: Cleanup never deletes files outside `integrations/openclaw/traces/`
4. **File-Only**: Directories and non-trace files are ignored
5. **Dry-Run Mode**: Available for testing cleanup without actual deletion

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `EMOTIOND_TRACE_RETENTION_DAYS` | 7 | Days to keep trace files |
| `EMOTIOND_TRACE_CLEANUP_INTERVAL_MS` | 3600000 | Minimum ms between cleanups |

## Files Changed

1. `integrations/openclaw/hooks/emotiond-bridge/handler.js` - Updated to use traceManager
2. `integrations/openclaw/hooks/emotiond-bridge/traceManager.js` - New module for rotation/cleanup
3. `integrations/openclaw/tests/test_trace_rotation.js` - Test suite

## API

### traceManager.appendTrace(tracesDir, targetId, traceRecord, options)

Appends a trace record to the daily trace file.

```javascript
const traceManager = require('./traceManager');
const result = traceManager.appendTrace('/path/to/traces', 'target-123', { data: 'value' });
// result: { success: true, path: '/path/to/traces/target-123-2024-02-28.jsonl', rotated: false }
```

### traceManager.cleanupOldTraces(tracesDir, options)

Cleans up old trace files based on retention policy.

```javascript
const result = traceManager.cleanupOldTraces('/path/to/traces', {
  retentionDays: 7,
  dryRun: false
});
// result: { deleted: ['file1.jsonl'], kept: ['file2.jsonl'], errors: [] }
```

### traceManager.cleanupOldTracesByCount(tracesDir, options)

Cleans up old trace files keeping N files per target.

```javascript
const result = traceManager.cleanupOldTracesByCount('/path/to/traces', {
  keepFiles: 7,
  dryRun: false
});
```

## Testing

Run tests with:

```bash
cd integrations/openclaw/tests
node test_trace_rotation.js
```

Expected output: 13 tests passing.
