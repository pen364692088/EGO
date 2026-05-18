---
name: openemotion-emotiond
description: "OpenEmotion emotiond integration for OpenClaw agents"
metadata:
  clawdbot:
    emoji: "🧠"
version: 2.0.0
---

# OpenEmotion Emotiond Integration

## Overview

This skill enables OpenClaw agents to:
1. Read emotiond runtime context from TOOLS.md
2. Classify user messages into semantic subtypes
3. Apply confidence gating for high-impact events
4. Send world_events to emotiond
5. Get post-event decisions for response generation

## World Event Classification (Contract)

### Agent Workflow (每条用户消息必须执行)

1. **读取 runtime context**
   - 从 TOOLS.md 的 `<!-- EMOTIOND_RUNTIME_BEGIN -->` 区块读取 JSON
   - 获取: target_id, request_id_base, dt_seconds, allowed_subtypes_infer

2. **语义分类 → 输出 JSON**
   输出必须完全符合 JSON Schema（见 schemas/world_event_classification.schema.json）

3. **置信度门控**
   根据分类结果决定是否发送 world_event

4. **发送 world_event (如果 should_send=true)**
   POST /event with subtype, target_id

5. **获取 post-decision**
   GET /decision?target_id=xxx

6. **生成回复**
   根据 action + guidance 生成回复

### Subtype 定义

| Subtype | 定义 | is_high_impact | 置信度门槛 |
|---------|------|----------------|-----------|
| care | 对方表达关心/支持/安慰/愿意陪伴 | false | ≥0.55 |
| apology | 对方承认过错/表达歉意/愿意弥补 | false | ≥0.55 |
| ignored | 对方持续不回应/敷衍/多次跳过关键点 | false | ≥0.60 |
| rejection | 对方明确拒绝你/否定关系/表示不想继续 | 视强度 | ≥0.75 |
| betrayal | 对方违背承诺/欺骗/背刺/泄密 | true | ≥0.90 |
| neutral | 信息性沟通/日常闲聊/无法映射上述 | false | 不发送 |
| uncertain | 不确定 subtype | false | 不发送 |

### 置信度标定

**起始值**: 0.55

**加分项** (每条 +0.10，最多 0.95):
- 明确关键词 ("对不起/抱歉/我错了")
- 明确动作 ("我会补偿/我来修复")
- 明确关系意图 ("我在乎你/我会陪你")
- 明确拒绝句式 ("不要/别再/不想/结束")
- 明确证据的背叛 (承诺+违背/欺骗+证据)

**减分项** (每条 -0.10，最低 0.05):
- 明显玩笑/阴阳怪气/夸张修辞
- 语境不足 (单句短文本)
- 多义 ("行吧/随你/呵呵")

### 门控规则

| Subtype | 门槛 | should_send | fallback |
|---------|------|-------------|----------|
| betrayal | ≥0.90 | true if ≥0.90 | ask_clarifying_question |
| rejection | ≥0.75 | true if ≥0.75 | ask_clarifying_question |
| ignored | ≥0.60 | true if ≥0.60 | no_event_reply_observe |
| care/apology | ≥0.55 | true if ≥0.55 | no_event_reply_observe |
| neutral/uncertain | - | false | no_event_reply_observe |

### 常见误判对照

| 用户消息 | ❌ 错误分类 | ✅ 正确处理 |
|---------|-----------|-----------|
| "我现在很忙" | ignored | neutral (一次说明) |
| "你别闹了（笑）" | rejection | neutral/uncertain (调侃) |
| "算了" | rejection | ignored 前兆或 neutral |
| "解释原因" | apology | neutral (无歉意/弥补意图) |
| "我不想现在谈" | rejection | neutral 或低强度 rejection |

## Action Reference

| Action | Tone | Intent | When | Example Phrases |
|--------|------|--------|------|-----------------|
| approach | Warm, open | Engage warmly | Bond/trust high, safe to engage | "glad to hear", "I appreciate" |
| withdraw | Brief, neutral | Self-protect | Low energy, self-protect | "I understand. Noted." |
| boundary | Clear, firm | Set limits | Limits being tested | "I need to be clear about..." |
| repair_offer | Gentle, healing | Rebuild trust | Trust low, repair possible | "Let me try to make this right" |
| observe | Curious, neutral | Gather info | Uncertain, need more info | "Tell me more about..." |
| attack | Defensive, sharp | Defend | Active threat | "That's not acceptable" |

## How to Use

### Reading Context (Pre-Response)

Before responding, read the emotiond context:

```bash
cat ~/.openclaw/workspace/emotiond/context.json
```

The hook writes to `<workspace>/emotiond/context.json`:

```json
{
  "target_id": "telegram:8420019401",
  "decision": {
    "action": "approach",
    "explanation": { ... }
  },
  "guidance": {
    "tone": "warm, open, friendly",
    "intent": "engage warmly",
    "phrases": ["glad to hear", "I appreciate"]
  }
}
```

### Matching Response to Guidance

- **tone**: Style of your response
- **intent**: What you're trying to achieve
- **phrases**: Suggested phrases to use naturally

## Example Responses

**approach** guidance:
> "Glad to hear from you! I appreciate you sharing that..."

**withdraw** guidance:
> "I understand. Noted."

**repair_offer** guidance:
> "I value our connection. Let me try to make this right..."

**boundary** guidance:
> "I need to be clear about my limits here..."

**observe** guidance:
> "Interesting. Tell me more about what's on your mind..."

## Workflow

```
User message 
  → Classify subtype + confidence
  → Apply confidence gating
  → Send world_event (if should_send)
  → Get decision from emotiond
  → Context written
  → Agent reads context
  → Response matches action
```

## Files

- Hook: `~/.openclaw/hooks/emotiond-bridge/handler.js`
- Context: `~/.openclaw/workspace/emotiond/context.json`
- emotiond: `http://127.0.0.1:18080`

## Fallback

If context missing/stale:
- Default to `observe` action
- Use curious, neutral tone
- Do not block user interaction

## Environment Variables

- `EMOTIOND_URL`: emotiond server URL (default: `http://127.0.0.1:18080`)
- `EMOTIOND_TIMEOUT`: Request timeout in ms (default: 5000)

## Token Usage

- Classification: ~50-100 tokens per message
- Context read: ~100-200 tokens
- Total overhead: ~150-300 tokens per interaction

## ⚠️ Critical: Emotion Ownership

**The emotion field represents the AGENT's own emotional state, NOT the user's.**

### Three-Layer State Model (MVP-7.4)

| Layer | Subject | Description |
|-------|---------|-------------|
| **Self** | `agent_id` (YOU) | Your own emotional state: joy/anger/sadness/anxiety/loneliness |
| **Relation** | `agent_id` → `counterparty_id` | Your relationship with the user: bond/trust/grudge/repair_bank |
| **Other** | `counterparty_id` | Your *inference* about the user's state (separate field) |

### Example

When you call `/decision/target/moonlight?agent_id=testbot`:

```json
{
  "emotion": {
    "sadness": 0.12,   // ← This is TESTBOT's sadness, NOT moonlight's
    "loneliness": 0.07 // ← This is TESTBOT's loneliness
  },
  "relationships": {
    "bond": 0.06,      // ← testbot's bond with moonlight
    "trust": 0.009     // ← testbot's trust in moonlight
  }
}
```

### How to Report

When explaining your state to users:

✅ **Correct:**
> "I'm feeling a bit sad (0.12) because trust is still building."

❌ **Wrong:**
> "You seem sad (0.12)." ← This is YOUR sadness, not theirs!

### Inferring User Emotion

If you want to guess the user's emotion:
1. Look at their message content
2. Look at your relationship state (low trust = user may be distant)
3. **DO NOT** use your own emotion field as their state

---

**Remember**: `emotion` is YOUR internal state, generated by your interactions with this user. It's YOUR feelings, not theirs.
