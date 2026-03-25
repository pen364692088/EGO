/**
 * Test suite for trace rotation and cleanup
 * 
 * Run with: node test_trace_rotation.js
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Import the module under test
const traceManager = require('../hooks/emotiond-bridge/traceManager');

// Test utilities
let testDir = null;
let testCount = 0;
let passCount = 0;
let failCount = 0;

function setup() {
  // Clean up previous test dir if exists
  if (testDir && fs.existsSync(testDir)) {
    fs.rmSync(testDir, { recursive: true, force: true });
  }
  testDir = fs.mkdtempSync('/tmp/trace-test-' + Date.now() + '-');
}

function teardown() {
  // Clean up test directory
  if (testDir && fs.existsSync(testDir)) {
    fs.rmSync(testDir, { recursive: true, force: true });
  }
  testDir = null;
}

function test(name, fn) {
  testCount++;
  try {
    fn();
    passCount++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failCount++;
    console.log(`  ✗ ${name}`);
    console.log(`    Error: ${e.message}`);
  }
}

function createTraceFile(targetId, date, lines = 1) {
  const filePath = traceManager.getTraceFilePath(testDir, targetId, date);
  for (let i = 0; i < lines; i++) {
    fs.appendFileSync(filePath, JSON.stringify({ test: i, date }) + '\n');
  }
  return filePath;
}

function getDateStr(daysAgo) {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

// ============ Tests ============

console.log('\n=== Trace Rotation Tests ===\n');

setup();

// Test 1: File naming convention
test('creates trace file with correct naming pattern', () => {
  const result = traceManager.appendTrace(testDir, 'test-target-1', { test: 'data' });
  assert(result.success, 'appendTrace should succeed');
  
  const expectedDate = new Date().toISOString().slice(0, 10);
  const expectedPath = path.join(testDir, `test-target-1-${expectedDate}.jsonl`);
  assert.strictEqual(result.path, expectedPath, 'Path should match expected pattern');
  assert(fs.existsSync(expectedPath), 'File should exist');
});

// Test 2: Date-based rotation (new file per day)
test('creates separate files for different dates', () => {
  const yesterdayStr = getDateStr(1);
  
  // Create file for yesterday
  const yesterdayPath = createTraceFile('date-test', yesterdayStr, 3);
  
  // Create file for today
  const todayResult = traceManager.appendTrace(testDir, 'date-test', { test: 'today' });
  
  // Should have two different files
  assert.notStrictEqual(yesterdayPath, todayResult.path, 'Should have different paths');
  
  // Both should exist
  assert(fs.existsSync(yesterdayPath), 'Yesterday file should exist');
  assert(fs.existsSync(todayResult.path), 'Today file should exist');
});

// Test 3: Same day appends to same file
test('appends to same file on same day', () => {
  traceManager.appendTrace(testDir, 'append-test', { id: 1 });
  traceManager.appendTrace(testDir, 'append-test', { id: 2 });
  traceManager.appendTrace(testDir, 'append-test', { id: 3 });
  
  const today = new Date().toISOString().slice(0, 10);
  const filePath = traceManager.getTraceFilePath(testDir, 'append-test', today);
  
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.trim().split('\n');
  
  assert.strictEqual(lines.length, 3, 'Should have 3 lines');
});

// Test 4: Target ID sanitization
test('sanitizes target IDs with special characters', () => {
  const safeId = 'test/target\\with\\slashes';
  const result = traceManager.appendTrace(testDir, safeId, { test: 'sanitized' });
  
  assert(result.success, 'Should handle special characters');
  assert(!result.path.includes('/target'), 'Path should not contain original slash');
});

teardown();

console.log('\n=== Trace Cleanup Tests ===\n');

setup();

// Test 5: Cleanup deletes old files
test('cleanup deletes files older than retention period', () => {
  // Create files for past 10 days
  for (let i = 0; i < 10; i++) {
    createTraceFile('cleanup-test', getDateStr(i));
  }
  
  // Cleanup with 7-day retention
  const result = traceManager.cleanupOldTraces(testDir, { retentionDays: 7 });
  
  // Days 8, 9, 10 (indices 7, 8, 9) should be deleted
  // But retention of 7 means keep files from last 7 days (today minus 0 to today minus 6)
  // Files older than today-7 should be deleted (today-8, today-9)
  // That's 2 files, not 3. Let me recalculate:
  // If retention is 7, cutoff date = today - 7
  // Files with date < cutoff should be deleted
  // Days 8 and 9 have dates < cutoff (today - 7), so 2 files
  assert.strictEqual(result.deleted.length, 2, 'Should delete 2 files (days 8, 9)');
  assert(result.kept.length >= 7, 'Should keep at least 7 files');
  assert.strictEqual(result.errors.length, 0, 'Should have no errors');
});

teardown();
setup();

// Test 6: Cleanup only affects trace files
test('cleanup does not affect non-trace files', () => {
  // Create a non-trace file
  const nonTracePath = path.join(testDir, 'important-data.txt');
  fs.writeFileSync(nonTracePath, 'important data');
  
  // Create old trace file
  createTraceFile('safety-test', getDateStr(10));
  
  // Cleanup
  traceManager.cleanupOldTraces(testDir, { retentionDays: 7 });
  
  // Non-trace file should still exist
  assert(fs.existsSync(nonTracePath), 'Non-trace file should not be deleted');
  
  // Trace file should be deleted
  const tracePath = traceManager.getTraceFilePath(testDir, 'safety-test', getDateStr(10));
  assert(!fs.existsSync(tracePath), 'Old trace file should be deleted');
});

teardown();
setup();

// Test 7: Cleanup dry-run
test('dry-run does not delete files', () => {
  createTraceFile('dryrun-test', getDateStr(10));
  
  const result = traceManager.cleanupOldTraces(testDir, { retentionDays: 7, dryRun: true });
  
  assert.strictEqual(result.deleted.length, 1, 'Should report 1 file to delete');
  assert(result.deleted[0].includes('dry-run'), 'Should indicate dry-run');
  
  // File should still exist
  const tracePath = traceManager.getTraceFilePath(testDir, 'dryrun-test', getDateStr(10));
  assert(fs.existsSync(tracePath), 'File should not be deleted in dry-run');
});

teardown();
setup();

// Test 8: Per-target cleanup
test('per-target cleanup keeps N files per target', () => {
  // Create 5 files for target-a and 10 files for target-b
  for (let i = 0; i < 10; i++) {
    if (i < 5) {
      createTraceFile('target-a', getDateStr(i));
    }
    createTraceFile('target-b', getDateStr(i));
  }
  
  // Keep 3 files per target
  const result = traceManager.cleanupOldTracesByCount(testDir, { keepFiles: 3 });
  
  // target-a: 5 files - 3 kept = 2 deleted
  // target-b: 10 files - 3 kept = 7 deleted
  assert.strictEqual(result.deleted.length, 9, 'Should delete 9 files total (2 + 7)');
});

teardown();

console.log('\n=== Safety Tests ===\n');

setup();

// Test 9: Path traversal protection
test('isPathWithinTracesDir blocks path traversal', () => {
  const tracesDir = '/tmp/safe-traces';
  
  assert(traceManager.isPathWithinTracesDir(tracesDir, '/tmp/safe-traces/file.jsonl'), 
    'Should allow files within traces dir');
  
  assert(!traceManager.isPathWithinTracesDir(tracesDir, '/tmp/safe-traces-backup/file.jsonl'), 
    'Should block similar but different directory');
  
  assert(!traceManager.isPathWithinTracesDir(tracesDir, '/etc/passwd'), 
    'Should block files outside traces dir');
});

// Test 10: Pattern validation
test('isTraceFile validates correct patterns', () => {
  assert(traceManager.isTraceFile('target-2024-01-15.jsonl'), 
    'Should match valid pattern');
  
  assert(traceManager.isTraceFile('telegram-8420019401-2024-01-15.jsonl'), 
    'Should match pattern with hyphens in target_id');
  
  assert(!traceManager.isTraceFile('target.jsonl'), 
    'Should reject pattern without date');
  
  assert(!traceManager.isTraceFile('target-2024-1-15.jsonl'), 
    'Should reject invalid date format');
  
  assert(!traceManager.isTraceFile('important.txt'), 
    'Should reject non-jsonl files');
});

// Test 11: Parse trace filename
test('parseTraceFilename extracts components correctly', () => {
  const result = traceManager.parseTraceFilename('telegram-8420019401-2024-01-15.jsonl');
  
  assert.strictEqual(result.targetId, 'telegram-8420019401', 'Should extract target_id');
  assert.strictEqual(result.date, '2024-01-15', 'Should extract date');
  
  const nullResult = traceManager.parseTraceFilename('invalid.txt');
  assert.strictEqual(nullResult, null, 'Should return null for invalid pattern');
});

teardown();

console.log('\n=== Utility Tests ===\n');

setup();

// Test 12: getTraceStats
test('getTraceStats returns correct statistics', () => {
  // Create multiple files
  createTraceFile('stats-test-1', getDateStr(0), 5);
  createTraceFile('stats-test-1', getDateStr(1), 3);
  createTraceFile('stats-test-2', getDateStr(0), 2);
  
  const stats = traceManager.getTraceStats(testDir);
  
  assert.strictEqual(stats.totalFiles, 3, 'Should count 3 files');
  assert(stats.totalSizeBytes > 0, 'Should have non-zero size');
  assert(stats.byTarget['stats-test-1'], 'Should have stats-test-1 in byTarget');
  assert.strictEqual(stats.byTarget['stats-test-1'].files, 2, 'stats-test-1 should have 2 files');
});

// Test 13: getTraceFilesByTarget
test('getTraceFilesByTarget groups files correctly', () => {
  createTraceFile('group-a', getDateStr(0));
  createTraceFile('group-a', getDateStr(1));
  createTraceFile('group-b', getDateStr(0));
  
  const byTarget = traceManager.getTraceFilesByTarget(testDir);
  
  assert(byTarget.has('group-a'), 'Should have group-a');
  assert(byTarget.has('group-b'), 'Should have group-b');
  assert.strictEqual(byTarget.get('group-a').length, 2, 'group-a should have 2 files');
  assert.strictEqual(byTarget.get('group-b').length, 1, 'group-b should have 1 file');
  
  // Check sorting (oldest first)
  const files = byTarget.get('group-a');
  assert(files[0].date < files[1].date, 'Files should be sorted oldest first');
});

teardown();

// ============ Summary ============

console.log('\n=== Test Summary ===\n');
console.log(`Total: ${testCount}`);
console.log(`Passed: ${passCount}`);
console.log(`Failed: ${failCount}`);
console.log('');

if (failCount > 0) {
  process.exit(1);
} else {
  console.log('All tests passed! ✓');
  process.exit(0);
}
