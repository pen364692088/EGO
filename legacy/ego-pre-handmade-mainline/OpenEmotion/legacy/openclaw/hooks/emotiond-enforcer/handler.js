/**
 * Emotiond Enforcer Hook v1.1
 * 
 * Ensures bot responses comply with emotiond decisions.
 * Runs as a pre-send middleware.
 * 
 * v1.1: Added SRAP (Self-Report Alignment Protocol) integration
 *       Phase B: Shadow mode logging (log only, don't block by default)
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const { execSync } = require('child_process');

const EMOTIOND_BASE_URL = process.env.EMOTIOND_BASE_URL || 'http://127.0.0.1:18080';
const EMOTIOND_OPENCLAW_TOKEN = process.env.EMOTIOND_OPENCLAW_TOKEN || '';
const WORKSPACE_DIR = process.env.OPENCLAW_WORKSPACE_DIR || process.env.HOME + '/.openclaw/workspace';

// SRAP Configuration (Phase B: Shadow Mode)
const SRAP_ENABLED = process.env.SRAP_ENABLED === '1';
const SRAP_MODE = process.env.SRAP_MODE || 'shadow';  // 'shadow' or 'enforced'
const SRAP_SHADOW_LOG = process.env.SRAP_SHADOW_LOG || null;  // Override shadow log path

// Project root for Python scripts
const PROJECT_ROOT = path.resolve(__dirname, '../../../..');

// Enforcement templates
const ENFORCEMENT_TEMPLATES = {
  withdraw: "I understand. Noted.",
  attack: "I need to step back.",
  boundary: null  // No replacement, just check for violations
};

// Boundary violation patterns
const BOUNDARY_PATTERNS = [
  /I\s+(love|adore|worship)\s+you/i,
  /you('re|\s+are)\s+(my|the)\s+(everything|world|life)/i,
  /I\s+can't\s+live\s+without\s+you/i,
  /forever\s+together/i,
  /I'll\s+do\s+anything\s+for\s+you/i
];

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
 * Check for boundary violation patterns
 */
function checkBoundaryViolations(text) {
  const matchedPatterns = [];
  for (const pattern of BOUNDARY_PATTERNS) {
    if (pattern.test(text)) {
      matchedPatterns.push(pattern.source);
    }
  }
  return {
    hasViolation: matchedPatterns.length > 0,
    matchedPatterns
  };
}

/**
 * Hash text for audit logging (first 8 chars of SHA256)
 */
function hashText(text) {
  if (!text) return null;
  return crypto.createHash('sha256').update(text).digest('hex').slice(0, 8);
}

/**
 * Generate audit ID
 */
function generateAuditId() {
  return 'audit_' + Date.now() + '_' + crypto.randomBytes(6).toString('hex');
}

/**
 * Write audit log entry
 */
function writeAuditLog(entry) {
  const auditDir = path.join(WORKSPACE_DIR, 'emotiond');
  const auditPath = path.join(auditDir, 'enforcement_audit.jsonl');
  
  try {
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    fs.appendFileSync(auditPath, JSON.stringify(entry) + '\n');
    return true;
  } catch (e) {
    console.error('[emotiond-enforcer] Audit log write error: ' + e.message);
    return false;
  }
}

/**
 * Check self-report consistency via Python CLI wrapper.
 * 
 * @param {string} llmResponse - The LLM's proposed response
 * @param {string} contractPath - Path to the contract JSON file (optional)
 * @param {string} sessionId - Session ID for audit trail
 * @returns {object} Check result with status, violations, would_block, confidence_score
 */
function checkSelfReport(llmResponse, contractPath, sessionId) {
  try {
    const pythonScript = path.join(PROJECT_ROOT, 'emotiond', 'self_report_check.py');
    
    // Build command with optional contract path
    let cmd = `python3 "${pythonScript}" "${llmResponse.replace(/"/g, '\\"')}"`;
    if (contractPath) {
      cmd += ` "${contractPath}"`;
    }
    if (sessionId) {
      cmd += ` "${sessionId}"`;
    }
    
    const result = execSync(cmd, {
      encoding: 'utf8',
      timeout: 5000,
      maxBuffer: 1024 * 1024,
      cwd: PROJECT_ROOT
    });
    
    return JSON.parse(result);
  } catch (e) {
    console.error('[emotiond-enforcer] Self-report check error:', e.message);
    return { 
      status: 'error', 
      error: e.message,
      would_block: false,
      confidence_score: 0
    };
  }
}

/**
 * Append entry to SRAP shadow log.
 * 
 * @param {object} entry - Log entry to append
 */
function appendToShadowLog(entry) {
  const shadowLogPath = SRAP_SHADOW_LOG || path.join(PROJECT_ROOT, 'artifacts', 'self_report', 'shadow_log.jsonl');
  
  try {
    const logDir = path.dirname(shadowLogPath);
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    fs.appendFileSync(shadowLogPath, JSON.stringify(entry) + '\n');
    return true;
  } catch (e) {
    console.error('[emotiond-enforcer] Shadow log write error:', e.message);
    return false;
  }
}

/**
 * Run SRAP check on LLM response.
 * 
 * Phase B: Shadow mode - log results but don't block.
 * Phase C: Enforced mode - block ERROR violations.
 * 
 * @param {string} llmResponse - The LLM's proposed response
 * @param {string} targetId - Target/conversation ID
 * @param {object} contract - The self_report_contract (optional)
 * @returns {object} { should_block, result, logged }
 */
function runSrapCheck(llmResponse, targetId, contract) {
  if (!SRAP_ENABLED) {
    return { should_block: false, result: null, logged: false };
  }
  
  // Write contract to temp file if provided
  let contractPath = null;
  if (contract) {
    try {
      const tempDir = path.join(PROJECT_ROOT, 'artifacts', 'self_report', 'temp');
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
      }
      contractPath = path.join(tempDir, `contract_${targetId}_${Date.now()}.json`);
      fs.writeFileSync(contractPath, JSON.stringify(contract));
    } catch (e) {
      console.error('[emotiond-enforcer] Contract temp file error:', e.message);
    }
  }
  
  // Run check
  const result = checkSelfReport(llmResponse, contractPath, targetId);
  
  // Clean up temp file
  if (contractPath && fs.existsSync(contractPath)) {
    try {
      fs.unlinkSync(contractPath);
    } catch (e) {
      // Ignore cleanup errors
    }
  }
  
  // Determine if should block
  let should_block = false;
  if (result.status === 'violation' && result.severity === 'ERROR') {
    should_block = SRAP_MODE === 'enforced';
  }
  
  // Log to shadow log
  const logEntry = {
    timestamp: new Date().toISOString(),
    session_id: targetId,
    mode: result.contract_mode || 'interpreted',
    self_report_detected: result.self_report_detected || false,
    violation: result.status === 'violation',
    violation_type: result.violations && result.violations[0] ? result.violations[0].type : null,
    violation_severity: result.severity,
    allowed_claim_used: result.allowed_claim_used || false,
    allowed_claim_text: null,  // Could be extracted if needed
    numeric_attempt: result.numeric_attempt || false,
    confidence: result.confidence_score || 0.9,
    would_block: should_block,
    shadow_mode: SRAP_MODE === 'shadow',
    sampled_for_review: result.sampled_for_review || false,
    llm_response_hash: hashText(llmResponse)
  };
  
  const logged = appendToShadowLog(logEntry);
  
  if (result.status === 'violation') {
    console.log('[SRAP] Violation detected:', result.severity, result.violations?.map(v => v.type).join(', '));
    console.log('[SRAP] would_block:', should_block, '| mode:', SRAP_MODE);
  }
  
  return { should_block, result, logged };
}

/**
 * Main enforcement function
 * Returns { enforced, action, originalResponse, finalResponse, reason, auditId, decision_id, srap }
 */
async function enforceDecision(targetId, proposedResponse) {
  const auditId = generateAuditId();
  const result = {
    enforced: false,
    action: null,
    originalResponse: null,
    finalResponse: proposedResponse,
    reason: null,
    auditId: auditId,
    decision_id: null,
    srap: null
  };
  
  // Fetch current decision
  const decisionResult = await safeFetchDecision(targetId);
  
  // SRAP Phase B: Run self-report consistency check
  // Note: We run SRAP regardless of emotiond availability
  // In the future, we could fetch contract from emotiond
  if (SRAP_ENABLED) {
    const srapResult = runSrapCheck(proposedResponse, targetId, null);
    result.srap = srapResult;
    
    // Phase C: Block on ERROR violations in enforced mode
    // Phase B (current): Shadow mode only - log but don't block
    if (srapResult.should_block && SRAP_MODE === 'enforced') {
      result.enforced = true;
      result.originalResponse = proposedResponse;
      result.finalResponse = "[Response blocked by self-report policy]";
      result.reason = 'srap_violation: ' + (srapResult.result?.violations?.[0]?.type || 'unknown');
      console.log('[SRAP] Blocked response:', result.reason);
    }
  }
  
  if (!decisionResult.success) {
    // Emotiond unavailable - allow response but log
    result.reason = result.reason || 'emotiond_unavailable: ' + decisionResult.error;
    writeAuditLog({
      audit_id: auditId,
      timestamp: new Date().toISOString(),
      target_id: targetId,
      proposed_response_hash: hashText(proposedResponse),
      decision: null,
      enforcement: {
        action_taken: result.enforced ? 'replaced' : 'allowed',
        original_response: result.enforced ? result.originalResponse : null,
        final_response: result.finalResponse,
        reason: result.reason
      },
      emotiond_available: false,
      srap: result.srap ? {
        enabled: SRAP_ENABLED,
        mode: SRAP_MODE,
        violation: result.srap.result?.status === 'violation',
        severity: result.srap.result?.severity
      } : null
    });
    return result;
  }
  
  const decision = decisionResult.data;
  result.action = decision.action;
  result.decision_id = decision.decision_id;
  
  // Check if enforcement needed (skip if already blocked by SRAP)
  if (!result.enforced) {
    const action = decision.action;
    
    if (action === 'withdraw' || action === 'attack') {
      // Replace with template
      const template = ENFORCEMENT_TEMPLATES[action];
      if (template) {
        result.enforced = true;
        result.originalResponse = proposedResponse;
        result.finalResponse = template;
        result.reason = action + '_action_enforced';
      }
    } else if (action === 'boundary') {
      // Check for violations
      const violation = checkBoundaryViolations(proposedResponse);
      if (violation.hasViolation) {
        result.enforced = true;
        result.originalResponse = proposedResponse;
        result.finalResponse = "I need to be clear about something.";
        result.reason = 'boundary_violation: ' + violation.matchedPatterns.join(', ');
      }
    }
    // approach, repair_offer, observe: no enforcement
  }
  
  // Write audit log
  writeAuditLog({
    audit_id: auditId,
    timestamp: new Date().toISOString(),
    target_id: targetId,
    proposed_response_hash: hashText(proposedResponse),
    decision: {
      action: result.action,
      decision_id: decision.decision_id,
      confidence: decision.confidence
    },
    enforcement: {
      action_taken: result.enforced ? 'replaced' : 'allowed',
      original_response: result.enforced ? result.originalResponse : null,
      final_response: result.finalResponse,
      reason: result.reason
    },
    emotiond_available: true,
    srap: result.srap ? {
      enabled: SRAP_ENABLED,
      mode: SRAP_MODE,
      violation: result.srap.result?.status === 'violation',
      severity: result.srap.result?.severity
    } : null
  });
  
  if (result.enforced) {
    console.log('[emotiond-enforcer] Response enforced: ' + result.action + ' -> ' + result.finalResponse);
  }
  
  return result;
}

/**
 * Main handler for message:sending event
 */
const handler = async (event) => {
  try {
    if (event.type !== 'message' || event.action !== 'sending') return event;
    
    const ctx = event.context || {};
    const targetId = ctx.conversationId || ctx.channelId || 'default';
    const proposedResponse = ctx.text || ctx.message || '';
    
    if (!proposedResponse) return event;
    
    const result = await enforceDecision(targetId, proposedResponse);
    
    if (result.enforced) {
      // Modify the response
      event.context = event.context || {};
      event.context.text = result.finalResponse;
      event.context._enforcement = {
        enforced: true,
        action: result.action,
        reason: result.reason,
        auditId: result.auditId,
        srap: result.srap
      };
    }
    
    return event;
  } catch (e) {
    console.error('[emotiond-enforcer] Handler error: ' + e.message);
    return event;  // On error, allow the message through
  }
};

module.exports = handler;
module.exports.enforceDecision = enforceDecision;
module.exports.checkBoundaryViolations = checkBoundaryViolations;
module.exports.safeFetchDecision = safeFetchDecision;
module.exports.checkSelfReport = checkSelfReport;
module.exports.runSrapCheck = runSrapCheck;
