/**
 * Trace Manager - Rotation and Cleanup for Emotiond Bridge
 * 
 * Implements date-based rotation and retention policy for trace files.
 * 
 * Naming convention: traces/<target_id>-<YYYY-MM-DD>.jsonl
 * Retention: Keep last N files per target_id (default: 7 days)
 */

const fs = require('fs');
const path = require('path');

// Configuration
const DEFAULT_RETENTION_DAYS = 7;
const MAX_FILE_SIZE_MB = 5; // For size-based rotation (optional hybrid mode)

// Regex for trace file pattern: <target_id>-YYYY-MM-DD.jsonl
// Target ID can contain hyphens, so we match from the end: capture date pattern at end
const TRACE_FILE_PATTERN = /^(.+)-(\d{4}-\d{2}-\d{2})\.jsonl$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Get current date string in YYYY-MM-DD format
 */
function getCurrentDateString() {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

/**
 * Get trace file path for a given target_id and date
 * @param {string} tracesDir - Base traces directory
 * @param {string} targetId - Target ID
 * @param {string} dateStr - Date string (YYYY-MM-DD), defaults to today
 * @returns {string} Full path to trace file
 */
function getTraceFilePath(tracesDir, targetId, dateStr = null) {
  const date = dateStr || getCurrentDateString();
  // Sanitize targetId to prevent path traversal
  const safeTargetId = targetId.replace(/[/\\]/g, '_');
  return path.join(tracesDir, `${safeTargetId}-${date}.jsonl`);
}

/**
 * Validate that a path is within the traces directory (prevents path traversal)
 * @param {string} tracesDir - Base traces directory (must be absolute)
 * @param {string} filePath - File path to validate
 * @returns {boolean} True if path is safe
 */
function isPathWithinTracesDir(tracesDir, filePath) {
  const resolvedTracesDir = path.resolve(tracesDir);
  const resolvedFilePath = path.resolve(filePath);
  return resolvedFilePath.startsWith(resolvedTracesDir + path.sep) || 
         resolvedFilePath === resolvedTracesDir;
}

/**
 * Check if a filename matches the trace file pattern
 * @param {string} filename - Filename to check
 * @returns {boolean} True if matches pattern
 */
function isTraceFile(filename) {
  const match = filename.match(TRACE_FILE_PATTERN);
  if (!match) return false;
  // Validate that the captured date part is actually a valid date format
  return DATE_PATTERN.test(match[2]);
}

/**
 * Parse trace filename to extract target_id and date
 * @param {string} filename - Trace filename
 * @returns {{targetId: string, date: string}|null} Parsed components or null
 */
function parseTraceFilename(filename) {
  const match = filename.match(TRACE_FILE_PATTERN);
  if (!match) return null;
  
  const targetId = match[1];
  const date = match[2];
  
  // Validate date format
  if (!DATE_PATTERN.test(date)) return null;
  
  return { targetId, date };
}

/**
 * Get file size in bytes
 * @param {string} filePath - Path to file
 * @returns {number} File size in bytes, or 0 if file doesn't exist
 */
function getFileSize(filePath) {
  try {
    const stats = fs.statSync(filePath);
    return stats.size;
  } catch {
    return 0;
  }
}

/**
 * Append trace record to daily trace file
 * This implements date-based rotation automatically (new file per day)
 * 
 * @param {string} tracesDir - Base traces directory
 * @param {string} targetId - Target ID
 * @param {object} traceRecord - Trace record to append
 * @param {object} options - Optional settings
 * @param {number} options.maxSizeMB - Max size in MB before splitting (0 = disabled)
 * @returns {{success: boolean, path: string, rotated: boolean}}
 */
function appendTrace(tracesDir, targetId, traceRecord, options = {}) {
  const { maxSizeMB = 0 } = options;
  
  try {
    // Ensure directory exists
    if (!fs.existsSync(tracesDir)) {
      fs.mkdirSync(tracesDir, { recursive: true });
    }

    const tracePath = getTraceFilePath(tracesDir, targetId);
    let rotated = false;

    // Optional: Size-based rotation within same day
    if (maxSizeMB > 0 && fs.existsSync(tracePath)) {
      const sizeBytes = getFileSize(tracePath);
      if (sizeBytes > maxSizeMB * 1024 * 1024) {
        // Rotate by adding sequence number
        const seq = findNextSequence(tracesDir, targetId);
        const rotatedPath = getTraceFilePath(tracesDir, targetId, `${getCurrentDateString()}-${seq}`);
        fs.renameSync(tracePath, rotatedPath);
        rotated = true;
      }
    }

    // Append the trace record
    fs.appendFileSync(tracePath, JSON.stringify(traceRecord) + '\n', 'utf8');
    
    return { success: true, path: tracePath, rotated };
  } catch (e) {
    console.error('[trace-manager] Trace write error: ' + e.message);
    return { success: false, path: null, rotated: false, error: e.message };
  }
}

/**
 * Find next sequence number for size-based rotation
 */
function findNextSequence(tracesDir, targetId) {
  const date = getCurrentDateString();
  const files = fs.readdirSync(tracesDir);
  const prefix = `${targetId}-${date}`;
  
  let maxSeq = 0;
  for (const f of files) {
    const match = f.match(new RegExp(`^${prefix}-(\\d+)\\.jsonl$`));
    if (match) {
      const seq = parseInt(match[1], 10);
      if (seq > maxSeq) maxSeq = seq;
    }
  }
  return maxSeq + 1;
}

/**
 * Cleanup old trace files based on retention policy
 * SAFETY: Only deletes files matching trace pattern within traces directory
 * 
 * @param {string} tracesDir - Base traces directory
 * @param {object} options - Cleanup options
 * @param {number} options.retentionDays - Keep files from last N days (default: 7)
 * @param {boolean} options.dryRun - If true, don't actually delete (default: false)
 * @returns {{deleted: string[], kept: string[], errors: string[]}}
 */
function cleanupOldTraces(tracesDir, options = {}) {
  const { retentionDays = DEFAULT_RETENTION_DAYS, dryRun = false } = options;
  
  const result = {
    deleted: [],
    kept: [],
    errors: [],
    totalSizeBefore: 0,
    totalSizeAfter: 0
  };

  // Safety: Resolve to absolute path
  const resolvedTracesDir = path.resolve(tracesDir);

  // Check if directory exists
  if (!fs.existsSync(resolvedTracesDir)) {
    return result; // Nothing to clean
  }

  // Calculate cutoff date
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - retentionDays);
  const cutoffDateStr = cutoffDate.toISOString().slice(0, 10);

  try {
    const files = fs.readdirSync(resolvedTracesDir);

    for (const filename of files) {
      // SAFETY: Only process files matching trace pattern
      if (!isTraceFile(filename)) {
        continue; // Skip non-trace files
      }

      const filePath = path.join(resolvedTracesDir, filename);
      
      // SAFETY: Double-check path is within traces directory
      if (!isPathWithinTracesDir(resolvedTracesDir, filePath)) {
        result.errors.push(`Path traversal attempt blocked: ${filename}`);
        continue;
      }

      // SAFETY: Only process files (skip directories)
      try {
        const stats = fs.statSync(filePath);
        if (!stats.isFile()) {
          continue;
        }
        result.totalSizeBefore += stats.size;
      } catch {
        continue;
      }

      const parsed = parseTraceFilename(filename);
      if (!parsed) {
        continue; // Doesn't match pattern (shouldn't happen due to isTraceFile check)
      }

      // Check if file is within retention period
      if (parsed.date < cutoffDateStr) {
        // File is old, delete it
        if (!dryRun) {
          try {
            fs.unlinkSync(filePath);
            result.deleted.push(filename);
          } catch (e) {
            result.errors.push(`Failed to delete ${filename}: ${e.message}`);
          }
        } else {
          result.deleted.push(`${filename} (dry-run)`);
        }
      } else {
        result.kept.push(filename);
        // Recalculate size after (for dry run, same as before)
        try {
          result.totalSizeAfter += fs.statSync(filePath).size;
        } catch {}
      }
    }
  } catch (e) {
    result.errors.push(`Failed to read directory: ${e.message}`);
  }

  return result;
}

/**
 * Get trace files grouped by target_id
 * Useful for per-target retention policies
 * 
 * @param {string} tracesDir - Base traces directory
 * @returns {Map<string, Array<{filename: string, date: string, size: number}>>}
 */
function getTraceFilesByTarget(tracesDir) {
  const byTarget = new Map();

  if (!fs.existsSync(tracesDir)) {
    return byTarget;
  }

  const files = fs.readdirSync(tracesDir);

  for (const filename of files) {
    if (!isTraceFile(filename)) continue;

    const parsed = parseTraceFilename(filename);
    if (!parsed) continue;

    const filePath = path.join(tracesDir, filename);
    const size = getFileSize(filePath);

    if (!byTarget.has(parsed.targetId)) {
      byTarget.set(parsed.targetId, []);
    }

    byTarget.get(parsed.targetId).push({
      filename,
      date: parsed.date,
      size
    });
  }

  // Sort each target's files by date (oldest first)
  for (const [targetId, files] of byTarget) {
    files.sort((a, b) => a.date.localeCompare(b.date));
  }

  return byTarget;
}

/**
 * Cleanup old traces per target_id (keeps last N files per target)
 * 
 * @param {string} tracesDir - Base traces directory
 * @param {object} options - Cleanup options
 * @param {number} options.keepFiles - Number of files to keep per target (default: 7)
 * @param {boolean} options.dryRun - If true, don't actually delete
 * @returns {{deleted: string[], kept: string[], errors: string[]}}
 */
function cleanupOldTracesByCount(tracesDir, options = {}) {
  const { keepFiles = DEFAULT_RETENTION_DAYS, dryRun = false } = options;
  
  const result = {
    deleted: [],
    kept: [],
    errors: []
  };

  const resolvedTracesDir = path.resolve(tracesDir);

  if (!fs.existsSync(resolvedTracesDir)) {
    return result;
  }

  const byTarget = getTraceFilesByTarget(resolvedTracesDir);

  for (const [targetId, files] of byTarget) {
    // Keep last N files (already sorted oldest first)
    const toDelete = files.slice(0, Math.max(0, files.length - keepFiles));

    for (const file of toDelete) {
      const filePath = path.join(resolvedTracesDir, file.filename);

      // Safety check
      if (!isPathWithinTracesDir(resolvedTracesDir, filePath)) {
        result.errors.push(`Path traversal blocked: ${file.filename}`);
        continue;
      }

      if (!dryRun) {
        try {
          fs.unlinkSync(filePath);
          result.deleted.push(file.filename);
        } catch (e) {
          result.errors.push(`Failed to delete ${file.filename}: ${e.message}`);
        }
      } else {
        result.deleted.push(`${file.filename} (dry-run)`);
      }
    }

    result.kept.push(...files.slice(-keepFiles).map(f => f.filename));
  }

  return result;
}

/**
 * Get statistics about trace files
 */
function getTraceStats(tracesDir) {
  const stats = {
    totalFiles: 0,
    totalSizeBytes: 0,
    byTarget: {},
    oldestFile: null,
    newestFile: null
  };

  const byTarget = getTraceFilesByTarget(tracesDir);

  for (const [targetId, files] of byTarget) {
    stats.byTarget[targetId] = {
      files: files.length,
      totalSizeBytes: files.reduce((sum, f) => sum + f.size, 0)
    };
    stats.totalFiles += files.length;
    stats.totalSizeBytes += files.reduce((sum, f) => sum + f.size, 0);

    for (const f of files) {
      if (!stats.oldestFile || f.date < stats.oldestFile) {
        stats.oldestFile = f.date;
      }
      if (!stats.newestFile || f.date > stats.newestFile) {
        stats.newestFile = f.date;
      }
    }
  }

  return stats;
}

module.exports = {
  // Core functions
  appendTrace,
  cleanupOldTraces,
  cleanupOldTracesByCount,
  
  // Utility functions
  getCurrentDateString,
  getTraceFilePath,
  isTraceFile,
  parseTraceFilename,
  isPathWithinTracesDir,
  getTraceFilesByTarget,
  getTraceStats,
  
  // Constants
  DEFAULT_RETENTION_DAYS,
  TRACE_FILE_PATTERN
};
