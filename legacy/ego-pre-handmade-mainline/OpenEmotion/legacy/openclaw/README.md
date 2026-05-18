# OpenEmotion ↔ OpenClaw Integration

This directory contains integration components for connecting OpenEmotion's emotiond daemon with OpenClaw.

## Quick Start

### 1. Start emotiond

```bash
cd /path/to/OpenEmotion
source .venv/bin/activate
python -m emotiond.main
# Running on http://127.0.0.1:18080
```

### 2. Configure OpenClaw

Add to `~/.openclaw/openclaw.json`:

```json
{
  "env": {
    "EMOTIOND_BASE_URL": "http://127.0.0.1:18080",
    "EMOTIOND_OPENCLAW_TOKEN": "your-secure-token-here"
  },
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

### 3. Install Hooks

```bash
# Option A: Symlink (recommended for development)
mkdir -p ~/.openclaw/hooks
ln -s $(pwd)/integrations/openclaw/hooks/emotiond-bridge ~/.openclaw/hooks/emotiond-bridge
ln -s $(pwd)/integrations/openclaw/hooks/emotiond-enforcer ~/.openclaw/hooks/emotiond-enforcer

# Option B: Copy to managed hooks
cp -r integrations/openclaw/hooks/emotiond-bridge ~/.openclaw/hooks/
cp -r integrations/openclaw/hooks/emotiond-enforcer ~/.openclaw/hooks/
```

### 4. Enable Hooks

```bash
openclaw hooks enable emotiond-bridge
openclaw hooks enable emotiond-enforcer
openclaw hooks list  # Verify both show ✓
```

### 5. Restart Gateway

```bash
openclaw gateway restart
```

### 6. Test

Send a message via your connected channel (Telegram, WhatsApp, etc.). Check:

```bash
# Context file should exist
cat ~/.openclaw/workspace/emotiond/context.json

# Gateway logs should show hook execution
tail -f ~/.openclaw/gateway.log | grep emotiond

# Enforcement audit log (if enforcer is active)
tail -f ~/.openclaw/workspace/emotiond/enforcement_audit.jsonl
```

## Components

### Skill: openemotion-emotiond

Location: `skills/openemotion-emotiond/SKILL.md`

Guides the agent to:
1. Classify user messages into event subtypes (care, apology, rejection, etc.)
2. Call `POST /event` to send events to emotiond
3. Call `GET /decision` to get action recommendations
4. Generate responses based on decision explanations

### Hook: emotiond-bridge

Location: `hooks/emotiond-bridge/`

Automatically:
1. Listens for `message:received` events
2. Extracts `conversationId` as `target_id`
3. Writes context to `emotiond/context.json`
4. Sends `time_passed` events when time delta > 10s

### Hook: emotiond-enforcer

Location: `hooks/emotiond-enforcer/`

Pre-send enforcement hook:
1. Intercepts bot responses before sending
2. Checks emotiond decision for the target
3. Applies enforcement rules (withdraw → replace, boundary → check, etc.)
4. Logs enforcement actions to audit file

**Enforcement Rules:**

| Action | Behavior |
|--------|----------|
| `withdraw` | Replace with neutral template |
| `boundary` | Check for boundary violations |
| `attack` | Replace with safe response |
| `approach/observe/repair` | Allow unchanged |

See [TESTING.md](./TESTING.md) for detailed enforcement testing instructions.



## API Contract (Phase D P1.1)

### PlanRequest 身份字段

为避免"关系账本随会话漂移"，`PlanRequest` 支持显式的身份字段：

| 字段 | 语义 | 用途 |
|------|------|------|
| `target_id` | 会话隔离键 | 预测查找、会话隔离 |
| `counterparty_id` | 关系对象 | 关系状态查找 |
| `agent_id` | 本体身份 | 情感/关系所属实体 |

### 字段分离原则

**问题**：将 `conversationId` 当成关系对象会导致：
- 换会话 → 关系重置
- 同用户不同会话 → 关系分裂

**解决**：
- `target_id` = conversationId（会话维度）
- `counterparty_id` = 用户标识（关系维度）

### 请求示例

```json
{
  "user_id": "user123",
  "user_text": "你好",
  "target_id": "telegram:8420019401",
  "counterparty_id": "moonlight",
  "agent_id": "agent"
}
```

### 向后兼容

不提供新字段时：
```
counterparty_id ← focus_target ← user_id
target_id ← counterparty_id
agent_id ← "agent"
```


## Architecture

```
┌─────────────────┐     message:received     ┌────────────────────┐
│   OpenClaw      │ ──────────────────────▶  │  emotiond-bridge   │
│   Gateway       │                          │  (hook)            │
└─────────────────┘                          └─────────┬──────────┘
         │                                            │
         │ pre-send                                   │ POST /event
         │                                            │ (time_passed)
         ▼                                            ▼
┌─────────────────┐                          ┌────────────────────┐
│ emotiond-       │                          │  emotiond          │
│ enforcer        │◄─────────────────────────│  (daemon)          │
│ (hook)          │   GET /decision          │                    │
└─────────────────┘                          └────────────────────┘
         │
         │ enforceDecision()
         ▼
┌─────────────────┐
│   Final         │
│   Response      │
└─────────────────┘
```

## Event Flow

### Per-Message Flow

1. **User sends message** → OpenClaw receives
2. **Hook fires** → `emotiond-bridge` extracts context, sends `time_passed`
3. **Agent processes** → Skill guides agent to:
   - Classify message subtype
   - Call `POST /event` with world_event
   - Call `GET /decision` for guidance
   - Generate response based on decision
4. **Pre-send** → `emotiond-enforcer` checks decision, applies rules
5. **Response sent** → Modified or unchanged based on enforcement

### Target Isolation (MVP-3.1)

- `target_id` = `conversationId` (from hook context)
- Each conversation has independent learning residuals
- Changing conversations starts fresh (no cross-contamination)

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMOTIOND_BASE_URL` | Yes | `http://127.0.0.1:18080` | emotiond API endpoint |
| `EMOTIOND_OPENCLAW_TOKEN` | Yes | - | Bearer token for authenticated requests |
| `EMOTIOND_TIME_PASSED_MIN_DELTA` | No | `10` | Minimum seconds before sending time_passed |
| `EMOTIOND_TIME_PASSED_MAX_SECONDS` | No | `300` | Maximum seconds to report (clamped) |

## Verification Checklist

### Basic Integration

- [ ] emotiond running on configured port
- [ ] Both hooks enabled (`openclaw hooks list` shows ✓)
- [ ] Context file created after first message
- [ ] No errors in gateway logs

### Event Flow

- [ ] world_event sent for each user message
- [ ] time_passed sent when delay > 10s
- [ ] decision returned with explanation

### Enforcement

- [ ] Enforcement audit log exists
- [ ] Withdraw responses replaced correctly
- [ ] Boundary violations detected

### Target Isolation

- [ ] Same conversationId accumulates learning
- [ ] Different conversationId has independent residuals
- [ ] residuals don't cross-contaminate

## Troubleshooting

### Hook Not Executing

1. Check hook is enabled: `openclaw hooks list`
2. Check internal hooks enabled in config
3. Restart gateway: `openclaw gateway restart`
4. Check logs: `tail -f ~/.openclaw/gateway.log`

### emotiond Connection Errors

1. Verify emotiond is running: `curl http://127.0.0.1:18080/health`
2. Check `EMOTIOND_BASE_URL` matches
3. Verify token is configured correctly (see Token Security below)

### Context File Not Created

1. Check workspace directory exists
2. Check write permissions
3. Look for errors in hook logs

### Enforcement Not Working

1. Verify emotiond-enforcer is enabled
2. Check audit log for errors
3. Verify `enforceDecision` is exported from emotiond-enforcer/handler.js

## Security Notes

1. **Tokens are secrets**: Never commit to git
2. **Source validation**: emotiond validates `source` server-side
3. **Target isolation**: `target_id` comes from hook context, not user input
4. **Rate limiting**: emotiond enforces 10s windows

## Next Steps

After Integration-0 is verified:

1. **Integration-1**: Map decision actions to response style templates
2. **Integration-2**: Add multi-channel identity binding
3. **Integration-3**: Plugin HTTP routes (when security model is resolved)

## Files

```
integrations/openclaw/
├── README.md                    # This file
├── TESTING.md                   # Testing guide (includes enforcement testing)
├── skills/
│   └── openemotion-emotiond/
│       └── SKILL.md             # Skill documentation
└── hooks/
    ├── emotiond-bridge/
    │   ├── HOOK.md              # Hook documentation
    │   ├── handler.js           # Hook implementation
    │   ├── outcomeCapture.js    # Outcome tracking
    │   └── traceManager.js      # Trace log management
    └── emotiond-enforcer/
        ├── HOOK.md              # Hook documentation
        ├── handler.js           # Enforcement implementation
        └── hook.json            # Hook configuration
```

---

## Token Security

### Token Configuration Priority

emotiond reads tokens in this order (first match wins):

1. **Environment variable** `EMOTIOND_SYSTEM_TOKEN` or `EMOTIOND_OPENCLAW_TOKEN` — **Recommended for production**
2. **Token file** `.emotiond_token` in project root — Fallback, auto-generated if missing

### How Tokens Are Written

- Scripts (e.g., test scripts, setup tools) write tokens to: **`.emotiond_token`** (project root)
- This path is excluded via `.gitignore`
- The file is created with `0600` permissions (owner read/write only)

### Quick Token Setup

```bash
# Option 1: Environment variable (recommended for production)
export EMOTIOND_SYSTEM_TOKEN=$(openssl rand -hex 32)

# Option 2: Let emotiond auto-generate
python -m emotiond.main
# Token will be written to .emotiond_token in project root
# Check startup logs for confirmation
```

### Verifying Token Configuration

```bash
# Check if environment variable is set
echo $EMOTIOND_SYSTEM_TOKEN

# Check token file
cat .emotiond_token
```

### Token Rotation

To rotate a compromised or stale token:

```bash
# Generate new token
openssl rand -hex 32 > .emotiond_token
chmod 600 .emotiond_token

# Or set via environment variable
export EMOTIOND_SYSTEM_TOKEN=$(openssl rand -hex 32)

# Update OpenClaw config if using EMOTIOND_OPENCLAW_TOKEN
# Edit ~/.openclaw/openclaw.json with the new token

# Restart services
openclaw gateway restart
```

### Never Commit Tokens

Token files are excluded via `.gitignore`:
```
.emotiond_token
**/.emotiond_token
emotiond_token
```

### If Token Was Committed to Git

See `docs/SECURITY.md` for instructions on cleaning git history using `git filter-branch` or BFG Repo-Cleaner.

**Important**: Always rotate a token that was ever committed to version control.

For comprehensive security documentation, see [`docs/SECURITY.md`](../../docs/SECURITY.md).
