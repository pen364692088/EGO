# Emotiond Testing Guide

## Deterministic Testing

### test_mode=true
All test and bot "status reports" MUST use test_mode=true to ensure reproducible results.

### Bash Test Script
```bash
./tools/test_emotiond_deterministic.sh <agent_id> <counterparty_id> <subtype> [seconds]
```

**Examples:**
```bash
# Test care event for moonlight
./tools/test_emotiond_deterministic.sh agent moonlight care

# Test betrayal event for main
./tools/test_emotiond_deterministic.sh agent main betrayal

# Test time_passed event
./tools/test_emotiond_deterministic.sh agent moonlight time_passed 120
```

## Identity Separation (Moonlight vs main)

### Mapping Rules
| Source | counterparty_id | Description |
|--------|-----------------|-------------|
| Telegram direct message | moonlight | User's personal Telegram account |
| Session/agent spawn | main | Agent's internal sessions |
| External API call | (from meta.actor) | Determined by caller |

### Implementation
- `emotiond_world_event` must carry `counterparty_id` explicitly
- `emotiond_get_decision` must specify `counterparty_id`
- Both identities share same Telegram ID but have separate relationship tracks

### Verification
Run test with both identities and verify trust/grudge/bond don't cross-contaminate:
```bash
# Run identity separation verification
./tools/test_identity_separation.sh
```

## Audit Rules
1. Bot MUST NOT report status without actual API response
2. Every status report MUST include decision_id, selected action, and candidates
3. No hallucinated trust/energy/candidates allowed

## API Response Format

### World Event Response
```json
{
  "status": "success",
  "event_id": "evt_abc123",
  "emotional_state": {
    "trust": 0.75,
    "energy": 0.60,
    "grudge": 0.10
  }
}
```

### Decision Response
```json
{
  "status": "success",
  "decision_id": "dec_xyz789",
  "action": "approach",
  "candidates": ["approach", "observe", "withdraw"],
  "confidence": 0.85
}
```

## Test Commands Reference

### Test Individual Endpoints

**Health Check:**
```bash
curl -s http://127.0.0.1:18080/health | python3 -m json.tool
```

**Send World Event:**
```bash
curl -s -X POST http://127.0.0.1:18080/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "world_event",
    "actor": "moonlight",
    "target": "agent",
    "agent_id": "agent",
    "counterparty_id": "moonlight",
    "meta": {"subtype": "care"}
  }' | python3 -m json.tool
```

**Get Decision (Deterministic):**
```bash
curl -s -X POST "http://127.0.0.1:18080/decision?test_mode=true" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "agent",
    "user_text": "test",
    "focus_target": "moonlight"
  }' | python3 -m json.tool
```

## Valid Subtypes
- `care` - Positive interaction
- `apology` - Repair attempt
- `betrayal` - Trust violation
- `rejection` - Social rejection
- `ignored` - Being ignored
- `neutral` - No emotional valence
- `uncertain` - Ambiguous event
- `repair_success` - Successful relationship repair
- `time_passed` - Time decay event

---

## Enforcement (pre-send hook)

### Overview
The emotiond-enforcer hook intercepts bot responses before they are sent, ensuring they comply with emotiond decisions. It runs as a pre-send middleware in OpenClaw.

### Repository Structure
```
integrations/openclaw/hooks/
├── emotiond-bridge/
│   ├── HOOK.md              # Hook documentation (message:received)
│   ├── handler.js           # Hook implementation
│   ├── outcomeCapture.js    # Outcome tracking
│   └── traceManager.js      # Trace log management
└── emotiond-enforcer/
    ├── HOOK.md              # Hook documentation (pre-send)
    ├── handler.js           # Enforcement implementation
    └── hook.json            # Hook configuration
```

### Installation

**Step 1: Deploy hooks to OpenClaw**
```bash
# Option A: Symlink (recommended for development)
mkdir -p ~/.openclaw/hooks
ln -s $(pwd)/integrations/openclaw/hooks/emotiond-bridge ~/.openclaw/hooks/emotiond-bridge
ln -s $(pwd)/integrations/openclaw/hooks/emotiond-enforcer ~/.openclaw/hooks/emotiond-enforcer

# Option B: Copy for production
cp -r integrations/openclaw/hooks/emotiond-bridge ~/.openclaw/hooks/
cp -r integrations/openclaw/hooks/emotiond-enforcer ~/.openclaw/hooks/
```

**Step 2: Enable hooks in OpenClaw config**

Add to `~/.openclaw/openclaw.json`:
```json
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "emotiond-bridge": { "enabled": true },
        "emotiond-enforcer": { "enabled": true }
      }
    }
  }
}
```

**Step 3: Restart OpenClaw Gateway**
```bash
openclaw gateway restart
```

### Enforcement Rules

| Action | Enforcement | Template |
|--------|-------------|----------|
| `withdraw` | Replace with brief, neutral template | "I understand. Noted." |
| `boundary` | Check for violations, warn if detected | (no replacement) |
| `attack` | Sanitize to safe response | "I need to step back." |
| `approach` | Allow (no enforcement) | - |
| `repair_offer` | Allow (no enforcement) | - |
| `observe` | Allow (no enforcement) | - |

### Boundary Violation Patterns

The enforcer checks for these patterns when action is `boundary`:
- `I (love|adore|worship) you`
- `you('re| are) (my|the) (everything|world|life)`
- `I can't live without you`
- `forever together`
- `I'll do anything for you`

### Testing Enforcement

**Test 1: Verify hook is loaded**
```bash
openclaw hooks list
# Should show both emotiond-bridge and emotiond-enforcer with ✓
```

**Test 2: Test withdraw enforcement via API**
```bash
# Trigger a withdraw action
curl -s -X POST http://127.0.0.1:18080/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "world_event",
    "actor": "moonlight",
    "target": "agent",
    "meta": {"subtype": "betrayal"}
  }'

# Verify decision is withdraw
curl -s "http://127.0.0.1:18080/decision/target/telegram:8420019401" | jq '.action'

# Send a message that would be modified by enforcement
# The bot response should be replaced with the withdraw template
```

**Test 3: Programmatic test**
```bash
# Check if enforceDecision is exported
node -e "
const handler = require('$HOME/.openclaw/hooks/emotiond-enforcer/handler.js');
console.log('enforceDecision:', typeof handler.enforceDecision);
console.log('checkBoundaryViolations:', typeof handler.checkBoundaryViolations);
"

# Expected output:
# enforceDecision: function
# checkBoundaryViolations: function
```

**Test 4: Verify enforcement audit log**
```bash
# After sending messages, check the audit log
tail -f ~/.openclaw/workspace/emotiond/enforcement_audit.jsonl

# Each entry should include:
# - audit_id, timestamp, target_id
# - decision.action, decision.decision_id
# - enforcement.action_taken, original_response, final_response
```

**Test 5: End-to-end pre-send verification**
```bash
# 1. Ensure emotiond is running
curl http://127.0.0.1:18080/health

# 2. Send a message via Telegram/WhatsApp
# 3. Check gateway logs for enforcement execution
tail -f ~/.openclaw/gateway.log | grep -i "enforc"

# 4. Verify the response matches the enforcement rules
```

### Audit Log Format

All enforcement decisions are logged to:
```
~/.openclaw/workspace/emotiond/enforcement_audit.jsonl
```

**Audit Record Format:**
```json
{
  "audit_id": "audit_1709123456789_abc123",
  "timestamp": "2026-03-02T22:47:00.000Z",
  "target_id": "moonlight",
  "proposed_response_hash": "a1b2c3d4",
  "decision": {
    "action": "withdraw",
    "decision_id": "dec_xyz",
    "confidence": 0.85
  },
  "enforcement": {
    "action_taken": "replaced",
    "original_response": "I would love to help you!",
    "final_response": "I understand. Noted.",
    "reason": "withdraw_action_enforced"
  }
}
```

### Troubleshooting Enforcement

**Hook not executing:**
```bash
# Check hook is enabled
openclaw hooks list

# Verify hook.json syntax
cat ~/.openclaw/hooks/emotiond-enforcer/hook.json | python3 -m json.tool

# Check gateway logs
tail -f ~/.openclaw/gateway.log | grep -i "enforcer\|emotiond"
```

**Functions not exported:**
```bash
# Verify handler.js has the required exports
node -e "console.log(Object.keys(require('$HOME/.openclaw/hooks/emotiond-enforcer/handler.js')))"
# Should include: enforceDecision, checkBoundaryViolations
```

**Enforcement not applied:**
```bash
# Verify decision action matches enforcement rules
curl -s "http://127.0.0.1:18080/decision/target/<target_id>" | jq '.action'

# Check audit log for errors
jq 'select(.enforcement.action_taken == "error")' ~/.openclaw/workspace/emotiond/enforcement_audit.jsonl
```

---

## Token Configuration

### Token Priority Order

emotiond reads tokens in this order (first match wins):

1. **Environment variable** `EMOTIOND_SYSTEM_TOKEN` or `EMOTIOND_OPENCLAW_TOKEN`
2. **Token file** `.emotiond_token` in project root (auto-generated if missing)

### Verifying Token Configuration

```bash
# Check environment variables
echo "EMOTIOND_SYSTEM_TOKEN: ${EMOTIOND_SYSTEM_TOKEN:+[SET]}"
echo "EMOTIOND_OPENCLAW_TOKEN: ${EMOTIOND_OPENCLAW_TOKEN:+[SET]}"

# Check token file
cat .emotiond_token 2>/dev/null || echo "Token file not found"
```

### Token File Location

- Scripts write tokens to: **`.emotiond_token`** (project root)
- This is the fallback if no environment variable is set
- File permissions should be `0600` (owner read/write only)

---

## Troubleshooting

### emotiond not responding
```bash
# Check if process is running
pgrep -f emotiond

# Check port availability
ss -tlnp | grep 18080
```

### Token Issues
```bash
# Check environment variables first
echo "EMOTIOND_SYSTEM_TOKEN: ${EMOTIOND_SYSTEM_TOKEN:+[SET]}"

# Then check token file
cat .emotiond_token 2>/dev/null || echo "Token file not found at .emotiond_token"
```

### Non-deterministic Results
Ensure `test_mode=true` is set in the decision query parameter.

### Hook Not Loading
```bash
# Verify hook directory structure
ls -la ~/.openclaw/hooks/emotiond-bridge/
ls -la ~/.openclaw/hooks/emotiond-enforcer/

# Check OpenClaw config
cat ~/.openclaw/openclaw.json | jq '.hooks.internal.entries'
```

---

## Audit Trail (MVP-7.5)

### Overview
All emotiond API responses now include machine-parseable audit fields for request tracing and replay compatibility.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `correlation_id` | string | Trace ID for request correlation across hook → tool → emotiond → enforcer |
| `policy_version` | string | Policy version for replay compatibility (default: "7.5.0") |
| `schema_version` | string | Response schema version for log parsing (default: "1.0") |

### Correlation ID Format
```
corr_<timestamp>_<random_hex>
```
Example: `corr_1709123456789_a1b2c3d4`

### Flow

```
┌─────────────────┐
│  Hook Entry     │  → Generate correlation_id
│  (handler.js)   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Tool Call      │  → Pass correlation_id to emotiond
│  (index.ts)     │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  emotiond API   │  → Include in response + logs
│  (api.py)       │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Enforcer       │  → Include in audit log
│  (handler.js)   │
└─────────────────┘
```

### API Response Examples

**Decision Response with Audit Fields:**
```json
{
  "status": "ok",
  "decision_id": 123,
  "action": "approach",
  "explanation": {...},
  "target_id": "moonlight",
  "created_at": "2026-03-02T17:00:00Z",
  "correlation_id": "corr_1709123456789_a1b2c3d4",
  "policy_version": "7.5.0",
  "schema_version": "1.0"
}
```

**Event with Correlation ID:**
```json
{
  "type": "world_event",
  "actor": "user",
  "target": "agent",
  "correlation_id": "corr_1709123456789_a1b2c3d4",
  "meta": {
    "subtype": "care",
    "target_id": "moonlight"
  }
}
```

### Tool Parameters

**emotiond_world_event:**
```json
{
  "counterparty_id": "moonlight",
  "subtype": "care",
  "correlation_id": "corr_optional_custom_id"
}
```

**emotiond_get_decision:**
```json
{
  "counterparty_id": "moonlight",
  "test_mode": true,
  "correlation_id": "corr_optional_custom_id"
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMOTIOND_POLICY_VERSION` | "7.5.0" | Override policy version |
| `EMOTIOND_SCHEMA_VERSION` | "1.0" | Override schema version |

### Testing Audit Trail

```bash
# Send event with correlation_id
curl -s -X POST http://127.0.0.1:18080/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "world_event",
    "actor": "moonlight",
    "target": "agent",
    "correlation_id": "corr_test_123",
    "meta": {"subtype": "care"}
  }' | python3 -m json.tool

# Get decision with correlation_id
curl -s "http://127.0.0.1:18080/decision/target/moonlight?test_mode=true&correlation_id=corr_test_456" | python3 -m json.tool
```

### Log Parsing

Use `jq` to extract audit fields from logs:

```bash
# Extract all correlation IDs from enforcement audit
jq '.correlation_id' ~/.openclaw/workspace/emotiond/enforcement_audit.jsonl

# Filter by policy version
jq 'select(.policy_version == "7.5.0")' /var/log/emotiond.log

# Group by correlation_id for trace reconstruction
jq -s 'group_by(.correlation_id)' traces/moonlight.jsonl
```

---

## Log Format Specification

### Standard Audit Log Entry
```json
{
  "timestamp": "2026-03-02T17:30:00Z",
  "correlation_id": "corr_abc123def456",
  "policy_version": "7.5.0",
  "schema_version": "1.0",
  "target_id": "moonlight",
  "counterparty_id": "moonlight",
  "decision_id": 42,
  "action": "withdraw",
  "enforcement_result": "replaced",
  "original_content_hash": "sha256...",
  "enforced_content": "I understand. Noted."
}
```

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| timestamp | ISO8601 | UTC timestamp |
| correlation_id | string | Trace ID across hook → tool → emotiond → enforcer |
| policy_version | string | Policy version for replay compatibility |
| schema_version | string | Log schema version |
| target_id | string | Target/conversation ID |
| counterparty_id | string | Identity (moonlight/main/etc) |
| decision_id | integer | Decision ID from emotiond |
| action | string | Decision action (withdraw/approach/boundary/etc) |
| enforcement_result | string | One of: allowed, replaced, blocked, error |
| original_content_hash | string | SHA256 of original proposed response (if replaced/blocked) |
| enforced_content | string | Final content after enforcement (if replaced) |

---

## SelfModel 测试 (MVP-7.6)

### SelfModel 是什么
SelfModel 是"自我一致性驱动的状态模拟"，不是宣称真实意识。它维护内部价值观权重、能力信念和身份稳定性，影响决策时的 action bias。

### 如何运行 SelfModel 回归
```bash
# 运行所有 MVP-7.6 测试（SelfModel + SelfConflict + Scenarios）
pytest tests/test_mvp76_*.py -v

# 预期结果：92 passed, 2 skipped
```

### 如何读取审计字段解释决策

**核心审计字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `self_conflict` | float 0-1 | 内部冲突程度。0 = 无冲突，1 = 最大冲突。高冲突通常来自 value_conflict 或 identity_threat |
| `self_model_hash` | string | SelfModel 状态的 SHA256 哈希，用于 replay 验证 |
| `bias_selected` | float | action bias 值，影响最终选择的 action |

**示例解读**：
```json
{
  "self_conflict": 0.35,
  "self_model_hash": "a1b2c3d4...",
  "bias_selected": 0.12
}
```
- `self_conflict: 0.35` → 中等内部冲突，可能是 value_conflict 导致
- `bias_selected: 0.12` → 正向 bias，略微倾向 approach/repair 类 action

### Manifest Replay 验证
```bash
# 1. 运行 deterministic 测试并生成 manifest
./tools/test_emotiond_deterministic.sh agent moonlight care --manifest out.json

# 2. Replay 验证
./tools/replay_manifest.sh out.json

# 预期：Events 和 Decisions 都应 match
```

### SelfConflict 组件权重
```python
# 默认权重
COMPONENT_WEIGHTS = {
    "value_conflict": 0.35,      # 价值观冲突（最高）
    "capability_failure": 0.25,  # 能力不足
    "identity_threat": 0.25,     # 身份威胁
    "relationship_state": 0.15   # 关系状态
}

# 总冲突 = 加权和
self_conflict = sum(component * weight)
```

---

## Phase D (P1.1): 身份字段契约

### 概述
为避免将 conversationId 当成关系对象导致"关系账本"随会话漂移，PlanRequest 现在支持显式的身份字段。

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | str | 是 | 用户标识（向后兼容） |
| `user_text` | str | 是 | 用户输入文本 |
| `focus_target` | str | 否 | Legacy: 关系目标，默认 user_id |
| `target_id` | str | 否 | **会话隔离键** (conversationId) |
| `counterparty_id` | str | 否 | **关系对象** - 关系状态的主体 |
| `agent_id` | str | 否 | **本体身份** - 情感/关系所属实体 |

### 字段语义

- **target_id**: 会话隔离键，用于预测查找和会话隔离
- **counterparty_id**: 关系对象，用于关系状态查找
- **agent_id**: 本体身份，表示"谁的"情感/关系被管理

### 回退规则

```
counterparty_id → focus_target → user_id
target_id → counterparty_id
agent_id → "agent"
```

### API 示例

**显式指定所有字段（推荐）：**
```bash
curl -s -X POST http://127.0.0.1:18080/plan   -H "Content-Type: application/json"   -d '{
    "user_id": "user123",
    "user_text": "你好",
    "target_id": "telegram:8420019401",
    "counterparty_id": "moonlight",
    "agent_id": "agent"
  }' | python3 -m json.tool
```

**向后兼容（不指定新字段）：**
```bash
curl -s -X POST http://127.0.0.1:18080/plan   -H "Content-Type: application/json"   -d '{
    "user_id": "moonlight",
    "user_text": "你好"
  }' | python3 -m json.tool
```

### 验证测试

```bash
# 1. 验证字段回退逻辑
curl -s -X POST http://127.0.0.1:18080/plan   -H "Content-Type: application/json"   -d '{"user_id": "test", "user_text": "test"}' | jq '.focus_target'
# 期望: "test"

# 2. 验证显式 counterparty_id
curl -s -X POST http://127.0.0.1:18080/plan   -H "Content-Type: application/json"   -d '{"user_id": "test", "user_text": "test", "counterparty_id": "moonlight"}' | jq '.focus_target'
# 期望: "moonlight"

# 3. 验证 target_id 独立性
curl -s -X POST http://127.0.0.1:18080/plan   -H "Content-Type: application/json"   -d '{
    "user_id": "test", 
    "user_text": "test",
    "target_id": "telegram:8420019401",
    "counterparty_id": "moonlight"
  }' | jq '.focus_target'
# 期望: "moonlight" (counterparty_id 作为关系对象)
```

### 迁移指南

**Hook 集成：**
```javascript
// emotiond-bridge/handler.js
const planRequest = {
  user_id: from,
  user_text: messageText,
  target_id: conversationId,     // 会话隔离键
  counterparty_id: userIdentity, // 关系对象
  agent_id: "agent"              // 本体身份
};
```

**Skill 调用：**
```typescript
// skills/openemotion-emotiond/index.ts
const response = await emotiondGetDecision({
  counterparty_id: "moonlight",
  target_id: "telegram:8420019401",
  user_text: "用户消息"
});
```
