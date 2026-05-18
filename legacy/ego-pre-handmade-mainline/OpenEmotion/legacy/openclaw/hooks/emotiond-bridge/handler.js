/**
 * Emotiond Bridge Hook v1.5
 * 
 * Integration-3: Security + Reliability + User Affect v0
 * 
 * v1.5 features:
 * - Injection size limit (3KB hard limit)
 * - Degradation strategy (emotiond unavailable → minimal marker)
 * - Safe API wrappers (never throw)
 * - Date-based trace rotation + retention
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const traceManager = require('./traceManager');

const EMOTIOND_BASE_URL = process.env.EMOTIOND_BASE_URL || 'http://127.0.0.1:18080';
const EMOTIOND_OPENCLAW_TOKEN = process.env.EMOTIOND_OPENCLAW_TOKEN || '';
const TIME_PASSED_MIN_DELTA = parseInt(process.env.EMOTIOND_TIME_PASSED_MIN_DELTA || '10', 10);
const TIME_PASSED_MAX_SECONDS = parseInt(process.env.EMOTIOND_TIME_PASSED_MAX_SECONDS || '300', 10);
const CONTEXT_FILE = 'emotiond/context.json';

// Injection size limits (Integration-3 D2)
const INJECTION_MAX_SIZE = 3072; // 3KB hard limit
const INJECTION_MIN_SIZE = 2048; // 2KB target minimum

// Trace configuration
const TRACE_RETENTION_DAYS = parseInt(process.env.EMOTIOND_TRACE_RETENTION_DAYS || '7', 10);
const TRACE_CLEANUP_INTERVAL_MS = parseInt(process.env.EMOTIOND_TRACE_CLEANUP_INTERVAL_MS || '3600000', 10);

// Hardcoded workspace path for this setup
const WORKSPACE_DIR = process.env.OPENCLAW_WORKSPACE_DIR || process.env.HOME + '/.openclaw/workspace';

// Markers for runtime context block
const RUNTIME_BEGIN = '<!-- EMOTIOND_RUNTIME_BEGIN -->';
const RUNTIME_END = '<!-- EMOTIOND_RUNTIME_END -->';

// v1.3: Per-target_id timestamp tracking
const lastMessageTimestamps = new Map();

// Track last cleanup time
let lastCleanupTime = 0;

function clampSeconds(seconds) {
  return Math.max(1, Math.min(TIME_PASSED_MAX_SECONDS, Math.floor(seconds)));
}

/**
 * v1.3 A3: Hash text for trace logging
 */
function hashText(text) {
  if (!text) return null;
  return crypto.createHash('sha256').update(text).digest('hex').slice(0, 8);
}

function getActionGuidance(action) {
  const g = {
    approach: { tone: 'warm, open, friendly', intent: 'engage warmly', phrases: ['glad to hear', 'I appreciate'] },
    withdraw: { tone: 'brief, neutral', intent: 'conserve energy', phrases: ['I understand', 'noted'] },
    boundary: { tone: 'clear, firm', intent: 'establish limits', phrases: ['I need to be clear', 'not comfortable'] },
    repair_offer: { tone: 'gentle, conciliatory', intent: 'rebuild trust', phrases: ['I value our connection', 'let me make this right'] },
    observe: { tone: 'curious, neutral', intent: 'gather info', phrases: ['tell me more', 'help me understand'] },
    attack: { tone: 'defensive, sharp', intent: 'push back', phrases: ['I have to push back', 'not acceptable'] }
  };
  return g[action] || g.observe;
}

// ============================================
// Integration-3 D2: Safe API Wrappers (never throw)
// ============================================

/**
 * Safe fetch decision - returns { success, data, error }
 */
async function safeFetchDecision(targetId) {
  return new Promise((resolve) => {
    const url = new URL('/decision/target/' + encodeURIComponent(targetId), EMOTIOND_BASE_URL);
    const req = http.request(url, {
      method: 'GET',
      headers: { 'Authorization': 'Bearer ' + EMOTIOND_OPENCLAW_TOKEN },
      timeout: 3000
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        if (res.statusCode < 400) {
          try { 
            resolve({ success: true, data: JSON.parse(data), error: null }); 
          } catch (e) { 
            resolve({ success: false, data: null, error: 'parse_error: ' + e.message }); 
          }
        } else { 
          resolve({ success: false, data: null, error: 'HTTP ' + res.statusCode }); 
        }
      });
    });
    req.on('error', (e) => resolve({ success: false, data: null, error: e.message }));
    req.on('timeout', () => { 
      req.destroy(); 
      resolve({ success: false, data: null, error: 'timeout' }); 
    });
    req.end();
  });
}

/**
 * Safe send time_passed - returns { success, error }
 */
async function safeSendTimePassed(targetId, seconds, reqId, fromUser) {
  return new Promise((resolve) => {
    const url = new URL('/event', EMOTIOND_BASE_URL);
    // MVP-7.4: Use explicit counterparty_id for relationship semantics
    const body = JSON.stringify({
      type: 'world_event',
      actor: 'system',
      target: 'agent',
      counterparty_id: fromUser || 'unknown',  // Who the time_passed affects (user identity)
      text: null,
      meta: { subtype: 'time_passed', seconds, source: 'openclaw', target_id: targetId, request_id: reqId }
    });
    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + EMOTIOND_OPENCLAW_TOKEN
      },
      timeout: 3000
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({ success: res.statusCode < 400, error: res.statusCode >= 400 ? 'HTTP ' + res.statusCode : null }));
    });
    req.on('error', (e) => resolve({ success: false, error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'timeout' }); });
    req.write(body);
    req.end();
  });
}

/**
 * Safe send user_message event - returns { success, error }
 */
async function safeSendUserMessageEvent(conversationId, messageLength, fromUser) {
  return new Promise((resolve) => {
    const url = new URL('/event', EMOTIOND_BASE_URL);
    // MVP-7.4: Use explicit counterparty_id for relationship semantics
    const body = JSON.stringify({
      type: 'world_event',
      actor: fromUser || 'user',
      counterparty_id: fromUser || 'user',  // Who the relationship is with (user identity, not conversation)
      target: 'agent',
      text: null,
      meta: {
        subtype: 'user_message',
        target_id: conversationId,
        message_length: messageLength,
        source: 'openclaw'
      }
    });
    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + EMOTIOND_OPENCLAW_TOKEN
      },
      timeout: 3000
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({ success: res.statusCode < 400, error: res.statusCode >= 400 ? 'HTTP ' + res.statusCode : null }));
    });
    req.on('error', (e) => resolve({ success: false, error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'timeout' }); });
    req.write(body);
    req.end();
  });
}

// ============================================
// Integration-3 D2: Injection Size Limit + Degradation
// ============================================

/**
 * Build minimal runtime context (for when emotiond unavailable or injection too large)
 */
function buildMinimalRuntimeContext(targetId, chan, msgId, ts, deltaSeconds, tracePath) {
  return {
    target_id: targetId,
    ts: ts,
    dt_seconds: deltaSeconds,
    emotiond: 'unavailable',
    trace: tracePath
  };
}

/**
 * Build full runtime context with size check
 * Returns { runtime, truncated } where truncated is true if size exceeded
 */
function buildRuntimeContext(targetId, chan, from, convId, msgId, ts, deltaSeconds, decision) {
  const runtime = {
    target_id: targetId,
    channel: chan,
    from: from,
    conversation_id: convId,
    message_id: msgId,
    ts: ts,
    dt_seconds: deltaSeconds,
    request_id_base: chan + ':' + msgId,
    pre_decision: decision ? {
      action: decision.action,
      decision_id: decision.decision_id
    } : null,
    allowed_subtypes_infer: ["care","apology","ignored","rejection","betrayal","neutral","uncertain"]
  };

  const blockStr = JSON.stringify(runtime);
  const size = Buffer.byteLength(blockStr, 'utf8');
  
  if (size > INJECTION_MAX_SIZE) {
    // Truncate to minimal
    const minimal = {
      target_id: targetId,
      ts: ts,
      decision: decision ? { action: decision.action, id: decision.decision_id } : null,
      dt_seconds: deltaSeconds
    };
    console.error('[emotiond-bridge] Injection block size ' + size + ' bytes exceeds limit ' + INJECTION_MAX_SIZE + ', truncating to minimal');
    return { runtime: minimal, truncated: true, size: Buffer.byteLength(JSON.stringify(minimal), 'utf8') };
  }
  
  return { runtime, truncated: false, size };
}

/**
 * v1.3 A1: Write runtime context to TOOLS.md with markers and size limit
 */
function writeRuntimeContext(wsDir, runtime, traceRecord) {
  const toolsMdPath = path.join(wsDir, "TOOLS.md");
  try {
    let content = '';
    try {
      content = fs.readFileSync(toolsMdPath, 'utf8');
    } catch (e) {
      content = '';
    }

    const runtimeBlock = RUNTIME_BEGIN + '\n```json\n' + JSON.stringify(runtime, null, 2) + '\n```\n' + RUNTIME_END;
    const blockSize = Buffer.byteLength(runtimeBlock, 'utf8');
    
    // Size check
    if (blockSize > INJECTION_MAX_SIZE) {
      console.error('[emotiond-bridge] Injection block size ' + blockSize + ' exceeds limit, skipping');
      traceRecord.errors.push({ operation: 'injection_size_check', error: 'block_size_' + blockSize + '_exceeds_' + INJECTION_MAX_SIZE });
      return false;
    }

    const beginIdx = content.indexOf(RUNTIME_BEGIN);
    const endIdx = content.indexOf(RUNTIME_END);

    let newContent;
    if (beginIdx !== -1 && endIdx !== -1 && endIdx > beginIdx) {
      newContent = content.slice(0, beginIdx) + runtimeBlock + content.slice(endIdx + RUNTIME_END.length);
    } else {
      newContent = content.trimEnd() + '\n\n' + runtimeBlock + '\n';
    }

    fs.writeFileSync(toolsMdPath, newContent, 'utf8');
    console.log('[emotiond-bridge] Runtime context written to TOOLS.md (' + blockSize + ' bytes)');
    return true;
  } catch (e) {
    console.error('[emotiond-bridge] TOOLS.md write error: ' + e.message);
    traceRecord.errors.push({ operation: 'write_tools_md', error: e.message });
    return false;
  }
}

/**
 * Write unavailable marker when emotiond is down
 */
function writeUnavailableMarker(wsDir, targetId, ts, error, traceRecord) {
  const toolsMdPath = path.join(wsDir, "TOOLS.md");
  try {
    let content = '';
    try {
      content = fs.readFileSync(toolsMdPath, 'utf8');
    } catch (e) {
      content = '';
    }

    const minimal = {
      target_id: targetId,
      ts: ts,
      emotiond: 'unavailable',
      error: error
    };
    
    const runtimeBlock = RUNTIME_BEGIN + '\n```json\n' + JSON.stringify(minimal, null, 2) + '\n```\n' + RUNTIME_END;

    const beginIdx = content.indexOf(RUNTIME_BEGIN);
    const endIdx = content.indexOf(RUNTIME_END);

    let newContent;
    if (beginIdx !== -1 && endIdx !== -1 && endIdx > beginIdx) {
      newContent = content.slice(0, beginIdx) + runtimeBlock + content.slice(endIdx + RUNTIME_END.length);
    } else {
      newContent = content.trimEnd() + '\n\n' + runtimeBlock + '\n';
    }

    fs.writeFileSync(toolsMdPath, newContent, 'utf8');
    console.log('[emotiond-bridge] Unavailable marker written to TOOLS.md');
    return true;
  } catch (e) {
    console.error('[emotiond-bridge] Unavailable marker write error: ' + e.message);
    return false;
  }
}

/**
 * v1.4: Perform trace cleanup with throttling
 */
function performTraceCleanup(tracesDir) {
  const now = Date.now();
  if (now - lastCleanupTime < TRACE_CLEANUP_INTERVAL_MS) {
    return null;
  }
  
  lastCleanupTime = now;
  const result = traceManager.cleanupOldTraces(tracesDir, { retentionDays: TRACE_RETENTION_DAYS });
  
  if (result.deleted.length > 0 || result.errors.length > 0) {
    console.log('[emotiond-bridge] Trace cleanup: deleted ' + result.deleted.length + ' files, kept ' + result.kept.length);
    if (result.errors.length > 0) {
      console.error('[emotiond-bridge] Trace cleanup errors: ' + result.errors.join(', '));
    }
  }
  
  return result;
}

// ============================================
// Main Handler (with degradation)
// ============================================

const handler = async (event) => {
  // Top-level try-catch: never let handler throw
  try {
    if (event.type !== 'message' || event.action !== 'received') return;

    const ctx = event.context || {};
    const wsDir = ctx.workspaceDir || WORKSPACE_DIR;
    const convId = ctx.conversationId || ctx.channelId || 'default';
    const msgId = ctx.messageId || 'msg_' + Date.now();
    const ts = ctx.timestamp || Date.now() / 1000;
    const from = ctx.from || 'unknown';
    const chan = ctx.channelId || 'unknown';
    const messageText = ctx.text || ctx.message || '';
    const messageLength = messageText.length;

    const targetId = convId;

    // Initialize trace record
    const traceRecord = {
      timestamp: new Date().toISOString(),
      inbound: {
        messageId: msgId,
        ts: ts,
        text_hash: hashText(messageText),
        dt_seconds: null
      },
      sent_events: [],
      errors: []
    };

    const lastTs = lastMessageTimestamps.get(targetId) || ts;
    const delta = ts - lastTs;
    traceRecord.inbound.dt_seconds = delta >= TIME_PASSED_MIN_DELTA ? clampSeconds(delta) : null;

    // Time passed (with safe wrapper)
    if (delta >= TIME_PASSED_MIN_DELTA) {
      const secs = clampSeconds(delta);
      const reqId = chan + ':' + msgId + ':tp';
      const result = await safeSendTimePassed(targetId, secs, reqId, from);
      if (result.success) {
        console.log('[emotiond-bridge] time_passed: ' + secs + 's -> ' + targetId);
        traceRecord.sent_events.push({ type: 'time_passed', seconds: secs, request_id: reqId });
      } else {
        console.error('[emotiond-bridge] time_passed error: ' + result.error);
        traceRecord.errors.push({ operation: 'send_time_passed', error: result.error });
      }
    }
    lastMessageTimestamps.set(targetId, ts);

    // Fetch decision (with safe wrapper)
    const decisionResult = await safeFetchDecision(targetId);
    let decision = null;
    let guidance = null;
    let emotiondAvailable = decisionResult.success;
    
    if (decisionResult.success && decisionResult.data && decisionResult.data.action) {
      decision = decisionResult.data;
      guidance = getActionGuidance(decision.action);
      console.log('[emotiond-bridge] Decision: ' + decision.action + ' for ' + targetId);
    } else if (!decisionResult.success) {
      console.error('[emotiond-bridge] Decision fetch error: ' + decisionResult.error);
      traceRecord.errors.push({ operation: 'fetch_decision', error: decisionResult.error });
    }

    // Write runtime context (with size limit and degradation)
    if (emotiondAvailable) {
      const { runtime } = buildRuntimeContext(
        targetId, chan, from, convId, msgId, ts,
        delta >= TIME_PASSED_MIN_DELTA ? clampSeconds(delta) : null,
        decision
      );
      writeRuntimeContext(wsDir, runtime, traceRecord);
    } else {
      // Degradation: write unavailable marker
      writeUnavailableMarker(wsDir, targetId, ts, decisionResult.error, traceRecord);
    }

    // Write context file (legacy compatibility)
    const context = {
      target_id: targetId,
      channel_id: chan,
      conversation_id: convId,
      message_id: msgId,
      from: from,
      timestamp: ts,
      decision: decision ? { action: decision.action, decision_id: decision.decision_id, explanation: decision.explanation } : null,
      guidance: guidance,
      emotiond_available: emotiondAvailable,
      generated_at: new Date().toISOString()
    };

    const ctxPath = path.join(wsDir, CONTEXT_FILE);
    const ctxDir = path.dirname(ctxPath);
    try {
      if (!fs.existsSync(ctxDir)) fs.mkdirSync(ctxDir, { recursive: true });
      fs.writeFileSync(ctxPath, JSON.stringify(context, null, 2));
      console.log('[emotiond-bridge] Context written to: ' + ctxPath);
    } catch (e) {
      console.error('[emotiond-bridge] Context write error: ' + e.message);
      traceRecord.errors.push({ operation: 'write_context_json', error: e.message });
    }

    // Send user_message event (with safe wrapper)
    if (messageLength > 0) {
      const result = await safeSendUserMessageEvent(targetId, messageLength, from);
      if (result.success) {
        console.log('[emotiond-bridge] user_message event sent: len=' + messageLength + ' -> ' + targetId);
        traceRecord.sent_events.push({ type: 'user_message', message_length: messageLength });
      } else {
        console.error('[emotiond-bridge] user_message event error: ' + result.error);
        traceRecord.errors.push({ operation: 'send_user_message', error: result.error });
      }
    }

    // Write trace record
    const tracesDir = path.join(wsDir, 'integrations/openclaw/traces');
    const traceResult = traceManager.appendTrace(tracesDir, targetId, traceRecord);
    
    if (traceResult.success) {
      console.log('[emotiond-bridge] Trace appended to: ' + traceResult.path);
    } else {
      console.error('[emotiond-bridge] Trace write failed: ' + traceResult.error);
    }

    // Perform cleanup
    performTraceCleanup(tracesDir);

    console.log('[emotiond-bridge] Processed: ' + msgId + ' -> ' + (decision?.action || 'unavailable'));
    
  } catch (e) {
    // Top-level catch: never throw
    console.error('[emotiond-bridge] Handler error (caught): ' + e.message);
  }
};

module.exports = handler;
module.exports.traceManager = traceManager;
module.exports.performTraceCleanup = performTraceCleanup;
module.exports.buildRuntimeContext = buildRuntimeContext;
module.exports.buildMinimalRuntimeContext = buildMinimalRuntimeContext;
module.exports.safeFetchDecision = safeFetchDecision;
module.exports.safeSendTimePassed = safeSendTimePassed;
module.exports.safeSendUserMessageEvent = safeSendUserMessageEvent;
module.exports.INJECTION_MAX_SIZE = INJECTION_MAX_SIZE;
