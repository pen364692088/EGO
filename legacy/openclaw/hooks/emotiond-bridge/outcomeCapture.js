/**
 * Outcome Capture Module (D4)
 * 
 * Captures tool_result, env_outcome, and interaction_outcome from
 * post-turn or transcript/tool messages and sends to emotiond safely.
 * 
 * Features:
 * - Safe wrapper (never throws if emotiond unavailable)
 * - 3KB injection cap enforcement
 * - Only latest consequence summary + body state summary + trace pointer
 * - Replayable trace verification
 */

const http = require('http');
const crypto = require('crypto');

// Get config at runtime (not module load) to allow test environment changes
function getEmotiondConfig() {
  return {
    baseUrl: process.env.EMOTIOND_BASE_URL || 'http://127.0.0.1:18080',
    token: process.env.EMOTIOND_OPENCLAW_TOKEN || ''
  };
}

// Injection size limits
const INJECTION_MAX_SIZE = 3072; // 3KB hard limit

// Outcome types
const OUTCOME_TYPES = {
  TOOL_RESULT: 'tool_result',
  ENV_OUTCOME: 'env_outcome',
  INTERACTION_OUTCOME: 'interaction_outcome'
};

// Tool result statuses
const TOOL_STATUSES = {
  SUCCESS: 'success',
  FAILURE: 'failure',
  TIMEOUT: 'timeout',
  ERROR: 'error',
  PARTIAL: 'partial'
};

/**
 * Hash text for trace logging
 */
function hashText(text) {
  if (!text) return null;
  return crypto.createHash('sha256').update(String(text)).digest('hex').slice(0, 8);
}

/**
 * Clamp a value between min and max
 */
function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Safe send outcome event to emotiond - returns { success, error }
 * Never throws - always returns a result object
 */
async function safeSendOutcomeEvent(targetId, outcomeType, outcomeData, requestId) {
  return new Promise((resolve) => {
    const config = getEmotiondConfig();
    const url = new URL('/event', config.baseUrl);
    
    const body = JSON.stringify({
      type: 'world_event',
      actor: 'system',
      target: 'assistant',
      text: null,
      meta: {
        subtype: outcomeType,
        target_id: targetId,
        request_id: requestId,
        source: 'openclaw',
        outcome: outcomeData
      }
    });

    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + config.token
      },
      timeout: 3000
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        const success = res.statusCode < 400;
        resolve({ 
          success, 
          error: success ? null : `HTTP ${res.statusCode}`,
          statusCode: res.statusCode
        });
      });
    });

    req.on('error', (e) => resolve({ success: false, error: e.message, statusCode: null }));
    req.on('timeout', () => { 
      req.destroy(); 
      resolve({ success: false, error: 'timeout', statusCode: null }); 
    });

    req.write(body);
    req.end();
  });
}

/**
 * Build consequence summary from tool result
 * Returns compact summary within size budget
 */
function buildConsequenceSummary(toolResult) {
  if (!toolResult) return null;

  const summary = {
    t: toolResult.tool_name || toolResult.tool || 'unknown',  // tool name (abbreviated)
    s: toolResult.status || 'unknown',  // status
    d: clamp(Math.round((toolResult.duration_ms || 0) / 100) / 10, 0, 999),  // duration in seconds, 1 decimal
  };

  // Add error code if present (abbreviated)
  if (toolResult.error_code || toolResult.error) {
    summary.e = (toolResult.error_code || String(toolResult.error).slice(0, 20));
  }

  // Add result hash for traceability
  if (toolResult.result_hash || toolResult.output) {
    summary.h = hashText(toolResult.result_hash || toolResult.output);
  }

  return summary;
}

/**
 * Build body state summary from affect/mood state
 */
function buildBodyStateSummary(affectState) {
  // Default neutral state
  const defaultState = {
    v: 0,    // valence: -1 to 1, scaled to -9 to 9
    a: 3,    // arousal: 0 to 1, scaled to 0-9
    e: 7,    // energy: 0 to 1, scaled to 0-9
    s: 6,    // social_safety: 0 to 1, scaled to 0-9
    u: 5     // uncertainty: 0 to 1, scaled to 0-9
  };

  if (!affectState) return defaultState;

  return {
    v: clamp(Math.round((affectState.valence || 0) * 9), -9, 9),
    a: clamp(Math.round((affectState.arousal || 0.3) * 9), 0, 9),
    e: clamp(Math.round((affectState.energy || 0.7) * 9), 0, 9),
    s: clamp(Math.round((affectState.social_safety || 0.6) * 9), 0, 9),
    u: clamp(Math.round((affectState.uncertainty || 0.5) * 9), 0, 9)
  };
}

/**
 * Build trace pointer for replay verification
 */
function buildTracePointer(targetId, tracePath, sequenceNum) {
  return {
    tid: targetId,
    path: tracePath ? hashText(tracePath) : null,  // hash of path, not full path
    seq: sequenceNum || 0
  };
}

/**
 * Build compact outcome payload with 3KB cap
 * Only includes: latest consequence summary + body state summary + trace pointer
 */
function buildOutcomePayload(targetId, outcomeType, toolResult, affectState, traceInfo) {
  const payload = {
    // Consequence summary (tool outcome)
    c: buildConsequenceSummary(toolResult),
    // Body state summary (affect snapshot)
    b: buildBodyStateSummary(affectState),
    // Trace pointer for replay
    p: buildTracePointer(targetId, traceInfo?.path, traceInfo?.sequence),
    // Timestamp
    ts: Date.now()
  };

  // Size check
  const payloadStr = JSON.stringify(payload);
  const size = Buffer.byteLength(payloadStr, 'utf8');

  if (size > INJECTION_MAX_SIZE) {
    // Truncate: keep only essential fields
    const minimalPayload = {
      c: { t: toolResult?.tool_name || 'unknown', s: toolResult?.status || 'unknown' },
      b: { v: 0, a: 3, e: 7, s: 6, u: 5 },
      p: { tid: targetId, seq: 0 },
      ts: Date.now()
    };
    return { payload: minimalPayload, truncated: true, originalSize: size };
  }

  return { payload, truncated: false, originalSize: size };
}

/**
 * Capture tool result outcome
 * Safe wrapper - never throws
 */
async function captureToolResult(targetId, toolResult, affectState, traceInfo) {
  const requestId = `tool_${Date.now()}_${hashText(toolResult?.tool_name || 'unknown')}`;
  
  try {
    const { payload, truncated, originalSize } = buildOutcomePayload(
      targetId,
      OUTCOME_TYPES.TOOL_RESULT,
      toolResult,
      affectState,
      traceInfo
    );

    const outcomeData = {
      type: 'tool_result',
      status: toolResult?.status || 'unknown',
      tool_name: toolResult?.tool_name || toolResult?.tool || 'unknown',
      duration_ms: toolResult?.duration_ms || 0,
      payload: payload,
      truncated: truncated,
      original_size: originalSize
    };

    const result = await safeSendOutcomeEvent(
      targetId,
      OUTCOME_TYPES.TOOL_RESULT,
      outcomeData,
      requestId
    );

    return {
      success: result.success,
      requestId,
      error: result.error,
      truncated,
      size: originalSize
    };
  } catch (e) {
    // Never throw - return error result
    return {
      success: false,
      requestId,
      error: e.message,
      truncated: false,
      size: 0
    };
  }
}

/**
 * Capture environment outcome
 * Safe wrapper - never throws
 */
async function captureEnvOutcome(targetId, envData, affectState, traceInfo) {
  const requestId = `env_${Date.now()}_${hashText(envData?.env_type || 'unknown')}`;
  
  try {
    const toolResult = {
      tool_name: envData?.env_type || 'env',
      status: envData?.status || 'unknown',
      duration_ms: envData?.duration_ms || 0,
      error_code: envData?.error_code
    };

    const { payload, truncated, originalSize } = buildOutcomePayload(
      targetId,
      OUTCOME_TYPES.ENV_OUTCOME,
      toolResult,
      affectState,
      traceInfo
    );

    const outcomeData = {
      type: 'env_outcome',
      env_type: envData?.env_type || 'unknown',
      status: envData?.status || 'unknown',
      payload: payload,
      truncated: truncated,
      original_size: originalSize
    };

    const result = await safeSendOutcomeEvent(
      targetId,
      OUTCOME_TYPES.ENV_OUTCOME,
      outcomeData,
      requestId
    );

    return {
      success: result.success,
      requestId,
      error: result.error,
      truncated,
      size: originalSize
    };
  } catch (e) {
    return {
      success: false,
      requestId,
      error: e.message,
      truncated: false,
      size: 0
    };
  }
}

/**
 * Capture interaction outcome
 * Safe wrapper - never throws
 */
async function captureInteractionOutcome(targetId, interactionData, affectState, traceInfo) {
  const requestId = `int_${Date.now()}_${hashText(interactionData?.interaction_type || 'unknown')}`;
  
  try {
    const toolResult = {
      tool_name: interactionData?.interaction_type || 'interaction',
      status: interactionData?.status || 'unknown',
      duration_ms: interactionData?.duration_ms || 0
    };

    const { payload, truncated, originalSize } = buildOutcomePayload(
      targetId,
      OUTCOME_TYPES.INTERACTION_OUTCOME,
      toolResult,
      affectState,
      traceInfo
    );

    const outcomeData = {
      type: 'interaction_outcome',
      interaction_type: interactionData?.interaction_type || 'unknown',
      status: interactionData?.status || 'unknown',
      payload: payload,
      truncated: truncated,
      original_size: originalSize
    };

    const result = await safeSendOutcomeEvent(
      targetId,
      OUTCOME_TYPES.INTERACTION_OUTCOME,
      outcomeData,
      requestId
    );

    return {
      success: result.success,
      requestId,
      error: result.error,
      truncated,
      size: originalSize
    };
  } catch (e) {
    return {
      success: false,
      requestId,
      error: e.message,
      truncated: false,
      size: 0
    };
  }
}

/**
 * Extract tool result from post-turn context
 * Handles various formats from OpenClaw transcript/tool messages
 */
function extractToolResultFromContext(context) {
  if (!context) return null;

  // Try various paths where tool results might be found
  const paths = [
    context.tool_result,
    context.last_tool_result,
    context.turn?.tool_result,
    context.post_turn?.tool_result,
    context.transcript?.slice(-1)[0]?.tool_result,
    context.messages?.slice(-1)[0]?.tool_result,
    context.tools?.slice(-1)[0]?.result,
    context.tool_calls?.slice(-1)[0]?.result
  ];

  for (const result of paths) {
    if (result) {
      return normalizeToolResult(result);
    }
  }

  return null;
}

/**
 * Extract environment outcome from context
 */
function extractEnvOutcomeFromContext(context) {
  if (!context) return null;

  const paths = [
    context.env_outcome,
    context.environment_result,
    context.exec_result,
    context.command_result,
    context.shell_result
  ];

  for (const result of paths) {
    if (result) {
      return normalizeEnvOutcome(result);
    }
  }

  return null;
}

/**
 * Extract interaction outcome from context
 */
function extractInteractionOutcomeFromContext(context) {
  if (!context) return null;

  const paths = [
    context.interaction_outcome,
    context.user_response,
    context.reply_result,
    context.message_result
  ];

  for (const result of paths) {
    if (result) {
      return normalizeInteractionOutcome(result);
    }
  }

  return null;
}

/**
 * Normalize tool result to standard format
 */
function normalizeToolResult(raw) {
  if (typeof raw === 'string') {
    return {
      tool_name: 'unknown',
      status: raw.toLowerCase().includes('error') ? TOOL_STATUSES.ERROR : TOOL_STATUSES.SUCCESS,
      output: raw,
      duration_ms: 0
    };
  }

  if (typeof raw === 'object') {
    const status = raw.status || raw.result || 'unknown';
    return {
      tool_name: raw.tool || raw.tool_name || raw.name || 'unknown',
      status: normalizeStatus(status),
      output: raw.output || raw.result || raw.data,
      error: raw.error || raw.error_message,
      error_code: raw.error_code || raw.code,
      duration_ms: raw.duration_ms || raw.duration || raw.elapsed || 0,
      result_hash: raw.result_hash || hashText(JSON.stringify(raw))
    };
  }

  return null;
}

/**
 * Normalize environment outcome to standard format
 */
function normalizeEnvOutcome(raw) {
  if (typeof raw === 'string') {
    return {
      env_type: 'exec',
      status: raw.toLowerCase().includes('error') ? 'failure' : 'success',
      output: raw
    };
  }

  if (typeof raw === 'object') {
    return {
      env_type: raw.type || raw.env_type || 'exec',
      status: normalizeStatus(raw.status || raw.result),
      output: raw.output || raw.stdout,
      error_code: raw.error_code || raw.exit_code,
      duration_ms: raw.duration_ms || raw.duration || 0
    };
  }

  return null;
}

/**
 * Normalize interaction outcome to standard format
 */
function normalizeInteractionOutcome(raw) {
  if (typeof raw === 'string') {
    return {
      interaction_type: 'message',
      status: 'completed',
      content: raw
    };
  }

  if (typeof raw === 'object') {
    return {
      interaction_type: raw.type || raw.interaction_type || 'message',
      status: normalizeStatus(raw.status || raw.result || 'completed'),
      content: raw.content || raw.text || raw.message,
      user_affect: raw.user_affect || raw.affect
    };
  }

  return null;
}

/**
 * Normalize various status strings to standard format
 */
function normalizeStatus(status) {
  if (!status) return 'unknown';
  
  const s = String(status).toLowerCase();
  
  if (['success', 'ok', 'done', 'completed', 'true', '1'].includes(s)) {
    return TOOL_STATUSES.SUCCESS;
  }
  if (['failure', 'fail', 'failed', 'error', 'false', '0'].includes(s)) {
    return TOOL_STATUSES.FAILURE;
  }
  if (['timeout', 'timedout', 'expired'].includes(s)) {
    return TOOL_STATUSES.TIMEOUT;
  }
  if (['partial', 'incomplete'].includes(s)) {
    return TOOL_STATUSES.PARTIAL;
  }
  
  return s;
}

/**
 * Main capture function - captures all available outcomes
 * Safe wrapper - never throws
 */
async function captureAllOutcomes(targetId, context, affectState, traceInfo) {
  const results = {
    tool_result: null,
    env_outcome: null,
    interaction_outcome: null,
    errors: []
  };

  try {
    // Capture tool result
    const toolResult = extractToolResultFromContext(context);
    if (toolResult) {
      results.tool_result = await captureToolResult(targetId, toolResult, affectState, traceInfo);
      if (!results.tool_result.success) {
        results.errors.push({ type: 'tool_result', error: results.tool_result.error });
      }
    }

    // Capture env outcome
    const envOutcome = extractEnvOutcomeFromContext(context);
    if (envOutcome) {
      results.env_outcome = await captureEnvOutcome(targetId, envOutcome, affectState, traceInfo);
      if (!results.env_outcome.success) {
        results.errors.push({ type: 'env_outcome', error: results.env_outcome.error });
      }
    }

    // Capture interaction outcome
    const interactionOutcome = extractInteractionOutcomeFromContext(context);
    if (interactionOutcome) {
      results.interaction_outcome = await captureInteractionOutcome(
        targetId, 
        interactionOutcome, 
        affectState, 
        traceInfo
      );
      if (!results.interaction_outcome.success) {
        results.errors.push({ type: 'interaction_outcome', error: results.interaction_outcome.error });
      }
    }

    return results;
  } catch (e) {
    // Never throw - return error result
    return {
      tool_result: null,
      env_outcome: null,
      interaction_outcome: null,
      errors: [{ type: 'capture_all', error: e.message }]
    };
  }
}

module.exports = {
  // Main capture functions
  captureToolResult,
  captureEnvOutcome,
  captureInteractionOutcome,
  captureAllOutcomes,
  
  // Extraction functions
  extractToolResultFromContext,
  extractEnvOutcomeFromContext,
  extractInteractionOutcomeFromContext,
  
  // Building functions
  buildConsequenceSummary,
  buildBodyStateSummary,
  buildTracePointer,
  buildOutcomePayload,
  
  // Utility functions
  safeSendOutcomeEvent,
  normalizeToolResult,
  normalizeEnvOutcome,
  normalizeInteractionOutcome,
  normalizeStatus,
  hashText,
  clamp,
  getEmotiondConfig,
  
  // Constants
  OUTCOME_TYPES,
  TOOL_STATUSES,
  INJECTION_MAX_SIZE
};
