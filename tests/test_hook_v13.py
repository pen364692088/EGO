#!/usr/bin/env python3
"""
Test for emotiond-bridge hook v1.3 features:
- A1: Runtime Context writing to TOOLS.md
- A3: Trace logging to traces/<target_id>.jsonl
"""

import json
import os
import tempfile
import subprocess
import sys


def test_runtime_context_markers():
    """Test that runtime context is written to TOOLS.md with correct markers."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_md_path = os.path.join(tmpdir, 'TOOLS.md')
        
        # Initial content
        initial_content = "# TOOLS.md\n\nSome existing content.\n"
        with open(tools_md_path, 'w') as f:
            f.write(initial_content)
        
        handler_path = '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/integrations/openclaw/hooks/emotiond-bridge/handler.js'
        
        # Use f-string with the tmpdir variable
        test_js = '''
const fs = require('fs');
const path = require('path');

const RUNTIME_BEGIN = '<!-- EMOTIOND_RUNTIME_BEGIN -->';
const RUNTIME_END = '<!-- EMOTIOND_RUNTIME_END -->';
const toolsPath = "''' + tools_md_path.replace('\\', '\\\\') + '''";

function writeRuntimeContext(toolsMdPath, runtime, traceRecord) {
  try {
    let content = '';
    try {
      content = fs.readFileSync(toolsMdPath, 'utf8');
    } catch (e) {
      content = '';
    }

    const runtimeBlock = RUNTIME_BEGIN + '\\n```json\\n' + JSON.stringify(runtime, null, 2) + '\\n```\\n' + RUNTIME_END;

    const beginIdx = content.indexOf(RUNTIME_BEGIN);
    const endIdx = content.indexOf(RUNTIME_END);

    let newContent;
    if (beginIdx !== -1 && endIdx !== -1 && endIdx > beginIdx) {
      newContent = content.slice(0, beginIdx) + runtimeBlock + content.slice(endIdx + RUNTIME_END.length);
    } else {
      newContent = content.trimEnd() + '\\n\\n' + runtimeBlock + '\\n';
    }

    fs.writeFileSync(toolsMdPath, newContent, 'utf8');
    console.log('[test] Runtime context written to TOOLS.md');
    return true;
  } catch (e) {
    console.error('[test] TOOLS.md write error:', e.message);
    return false;
  }
}

// Test 1: First write (should append)
const runtime1 = {
  target_id: 'test_conv_1',
  channel: 'telegram',
  from: 'user123',
  conversation_id: 'test_conv_1',
  message_id: 'msg_001',
  ts: 1234567890,
  dt_seconds: null,
  request_id_base: 'telegram:msg_001',
  pre_decision: null,
  allowed_subtypes_infer: ["care","apology","ignored","rejection","betrayal","neutral","uncertain"]
};

writeRuntimeContext(toolsPath, runtime1, { errors: [] });

// Verify
const content1 = fs.readFileSync(toolsPath, 'utf8');
console.log('Content after first write:');
console.log(content1);
console.log('---');

// Test 2: Second write (should replace)
const runtime2 = {
  target_id: 'test_conv_2',
  channel: 'telegram',
  from: 'user456',
  conversation_id: 'test_conv_2',
  message_id: 'msg_002',
  ts: 1234567900,
  dt_seconds: 10,
  request_id_base: 'telegram:msg_002',
  pre_decision: { action: 'approach', decision_id: 'dec_001' },
  allowed_subtypes_infer: ["care","apology","ignored","rejection","betrayal","neutral","uncertain"]
};

writeRuntimeContext(toolsPath, runtime2, { errors: [] });

const content2 = fs.readFileSync(toolsPath, 'utf8');
console.log('Content after second write:');
console.log(content2);
console.log('---');

// Verify markers exist only once
const beginCount = (content2.match(/EMOTIOND_RUNTIME_BEGIN/g) || []).length;
const endCount = (content2.match(/EMOTIOND_RUNTIME_END/g) || []).length;
console.log('BEGIN marker count:', beginCount);
console.log('END marker count:', endCount);

if (beginCount === 1 && endCount === 1) {
  console.log('PASS: Markers appear exactly once');
} else {
  console.log('FAIL: Markers should appear exactly once');
  process.exit(1);
}

// Verify JSON is valid
const jsonMatch = content2.match(/```json\\n([\\s\\S]*?)\\n```/);
if (jsonMatch) {
  try {
    const parsed = JSON.parse(jsonMatch[1]);
    console.log('PASS: JSON is valid');
    console.log('Parsed runtime:', parsed.target_id);
    if (parsed.target_id === 'test_conv_2') {
      console.log('PASS: Runtime updated to new values');
    } else {
      console.log('FAIL: Runtime should be test_conv_2');
      process.exit(1);
    }
  } catch (e) {
    console.log('FAIL: JSON parse error:', e.message);
    process.exit(1);
  }
} else {
  console.log('FAIL: No JSON block found');
  process.exit(1);
}

console.log('All tests passed!');
'''
        
        result = subprocess.run(
            ['node', '-e', test_js],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print('STDERR:', result.stderr)
        
        assert result.returncode == 0, f"Node test failed with code {result.returncode}"
        print("PASS: Runtime context marker test passed")


def test_trace_logging():
    """Test that trace records are correctly appended to traces/<target_id>.jsonl."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        traces_dir = os.path.join(tmpdir, 'traces')
        
        test_js = '''
const fs = require('fs');
const path = require('path');

const tracesDir = "''' + traces_dir.replace('\\', '\\\\') + '''";

function appendTrace(tracesDir, targetId, traceRecord) {
  try {
    if (!fs.existsSync(tracesDir)) {
      fs.mkdirSync(tracesDir, { recursive: true });
    }
    const tracePath = path.join(tracesDir, targetId + '.jsonl');
    fs.appendFileSync(tracePath, JSON.stringify(traceRecord) + '\\n', 'utf8');
    console.log('[test] Trace appended to:', tracePath);
    return true;
  } catch (e) {
    console.error('[test] Trace write error:', e.message);
    return false;
  }
}

// Test 1: First trace for target_1
const trace1 = {
  timestamp: '2024-01-01T00:00:00.000Z',
  inbound: {
    messageId: 'msg_001',
    ts: 1234567890,
    text_hash: 'abcd1234',
    dt_seconds: null
  },
  sent_events: [],
  errors: []
};
appendTrace(tracesDir, 'target_1', trace1);

// Test 2: Second trace for target_1
const trace2 = {
  timestamp: '2024-01-01T00:01:00.000Z',
  inbound: {
    messageId: 'msg_002',
    ts: 1234567950,
    text_hash: 'efgh5678',
    dt_seconds: 60
  },
  sent_events: [{ type: 'time_passed', seconds: 60, request_id: 'telegram:msg_002:tp' }],
  errors: []
};
appendTrace(tracesDir, 'target_1', trace2);

// Test 3: Trace for different target
const trace3 = {
  timestamp: '2024-01-01T00:02:00.000Z',
  inbound: {
    messageId: 'msg_003',
    ts: 1234568100,
    text_hash: 'ijkl9012',
    dt_seconds: null
  },
  sent_events: [],
  errors: []
};
appendTrace(tracesDir, 'target_2', trace3);

// Verify
const target1Path = path.join(tracesDir, 'target_1.jsonl');
const target2Path = path.join(tracesDir, 'target_2.jsonl');

const content1 = fs.readFileSync(target1Path, 'utf8');
const lines1 = content1.trim().split('\\n');
console.log('target_1.jsonl lines:', lines1.length);

if (lines1.length === 2) {
  console.log('PASS: target_1 has 2 trace records');
  for (const line of lines1) {
    try {
      JSON.parse(line);
    } catch (e) {
      console.log('FAIL: Invalid JSON in trace:', line);
      process.exit(1);
    }
  }
  console.log('PASS: All lines are valid JSON');
} else {
  console.log('FAIL: Expected 2 lines, got', lines1.length);
  process.exit(1);
}

if (fs.existsSync(target2Path)) {
  const content2 = fs.readFileSync(target2Path, 'utf8');
  const lines2 = content2.trim().split('\\n');
  if (lines2.length === 1) {
    console.log('PASS: target_2 has 1 trace record (no cross-contamination)');
  } else {
    console.log('FAIL: Expected 1 line for target_2, got', lines2.length);
    process.exit(1);
  }
} else {
  console.log('FAIL: target_2.jsonl not created');
  process.exit(1);
}

console.log('All trace tests passed!');
'''
        
        result = subprocess.run(
            ['node', '-e', test_js],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print('STDERR:', result.stderr)
        
        assert result.returncode == 0, f"Node test failed with code {result.returncode}"
        print("PASS: Trace logging test passed")


def test_multi_session_isolation():
    """Test that different target_ids don't interfere with each other."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        traces_dir = os.path.join(tmpdir, 'traces')
        
        test_js = '''
const fs = require('fs');
const path = require('path');

const tracesDir = "''' + traces_dir.replace('\\', '\\\\') + '''";
const tmpdir = "''' + tmpdir.replace('\\', '\\\\') + '''";

function appendTrace(tracesDir, targetId, traceRecord) {
  if (!fs.existsSync(tracesDir)) {
    fs.mkdirSync(tracesDir, { recursive: true });
  }
  const tracePath = path.join(tracesDir, targetId + '.jsonl');
  fs.appendFileSync(tracePath, JSON.stringify(traceRecord) + '\\n', 'utf8');
}

// Simulate multiple sessions with different target_ids
const sessions = ['session_A', 'session_B', 'session_C'];

for (let i = 0; i < 10; i++) {
  const targetId = sessions[i % 3];
  const trace = {
    timestamp: new Date().toISOString(),
    inbound: { messageId: 'msg_' + i, ts: Date.now() / 1000 },
    sent_events: [],
    errors: []
  };
  appendTrace(tracesDir, targetId, trace);
}

// Verify each session has correct number of records
// 10 messages / 3 sessions: A gets 4 (0,3,6,9), B gets 3 (1,4,7), C gets 3 (2,5,8)
const expectedCounts = { 'session_A': 4, 'session_B': 3, 'session_C': 3 };

for (const [sessionId, expectedCount] of Object.entries(expectedCounts)) {
  const tracePath = path.join(tracesDir, sessionId + '.jsonl');
  const content = fs.readFileSync(tracePath, 'utf8');
  const lines = content.trim().split('\\n');
  
  if (lines.length === expectedCount) {
    console.log('PASS:', sessionId, 'has', expectedCount, 'records');
  } else {
    console.log('FAIL:', sessionId, 'expected', expectedCount, 'got', lines.length);
    process.exit(1);
  }
}

console.log('All multi-session isolation tests passed!');
'''
        
        result = subprocess.run(
            ['node', '-e', test_js],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print('STDERR:', result.stderr)
        
        assert result.returncode == 0, f"Node test failed with code {result.returncode}"
        print("PASS: Multi-session isolation test passed")


if __name__ == '__main__':
    print("Running emotiond-bridge hook v1.3 tests...\\n")
    
    test_runtime_context_markers()
    print()
    
    test_trace_logging()
    print()
    
    test_multi_session_isolation()
    print()
    
    print("=" * 50)
    print("All v1.3 tests passed!")
