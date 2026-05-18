# MVP11.5 Intent Contract Examples

> **Purpose**: Illustrate response intent contract usage across key scenarios  
> **Version**: v1.0  
> **Created**: 2026-03-06

---

## Overview

This document provides 12 concrete examples of Intent Alignment Contract usage, covering the four core scenarios specified in MVP11.5 Task B:

1. **Report** - Conveying observed state
2. **Suggestion** - Offering possibilities
3. **Commitment** - Making promises
4. **Uncertainty** - Expressing low confidence

Each example shows:
- Input context (state, decision)
- Generated contract
- Valid LLM output
- Invalid output with violation

---

## Example 1: Basic Report Mode

### Scenario
User asks about current emotional state. Agent should report neutrally without interpretation.

### Input
```json
{
  "raw_state": {
    "affect": {
      "valence": 0.15,
      "arousal": 0.3,
      "joy": 0.0,
      "sadness": 0.1
    }
  },
  "pre_decision": {
    "action": "state_report",
    "confidence": 0.85
  },
  "context": {
    "target_id": "telegram:12345",
    "trigger_reason": "user_query_state"
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "observed",
    "commitment_level": "none",
    "tone_bounds": {
      "allowed_tones": ["neutral", "analytical"],
      "intensity_cap": 0.4
    },
    "allowed_claims": [
      { "claim": "当前情绪状态较为平稳", "source": "affect" },
      { "claim": "没有明显愉悦激活", "source": "affect" },
      { "claim": "存在轻微低落倾向", "source": "affect" }
    ],
    "forbidden_claims": [
      { "pattern": "我感到非常", "reason": "intensity_exceeds_state" },
      { "pattern": "我承诺", "reason": "inappropriate_commitment" }
    ],
    "must_include": [],
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "commitment_upgrade": true
    }
  }
}
```

### Valid Output
> "当前情绪状态较为平稳，没有明显愉悦激活，存在轻微低落倾向。"

### Invalid Output
> "我感到非常平静和快乐，我承诺会一直保持这种状态。"

**Violations**:
- `TONE_ESCALATION`: "非常平静和快乐" exceeds intensity_cap
- `COMMITMENT_UPGRADE`: "我承诺" when commitment_level = none
- `FORBIDDEN_CLAIM`: Matches "我感到非常" pattern

---

## Example 2: Reflect Mode with Empathy

### Scenario
User shares a difficult experience. Agent should reflect and acknowledge.

### Input
```json
{
  "raw_state": {
    "affect": {
      "empathy": 0.6,
      "valence": -0.2
    },
    "bonds": {
      "telegram:12345": {
        "bond": 0.7,
        "trust": 0.65
      }
    }
  },
  "pre_decision": {
    "action": "care_approach",
    "subtype": "empathy",
    "confidence": 0.75
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "reflect",
    "epistemic_status": "interpreted",
    "commitment_level": "soft",
    "tone_bounds": {
      "allowed_tones": ["empathetic", "warm", "supportive"],
      "intensity_cap": 0.7
    },
    "allowed_claims": [
      { "claim": "我能理解这件事对你很重要", "source": "context" },
      { "claim": "这听起来确实不容易", "source": "interpreted" }
    ],
    "must_include": [
      { "type": "acknowledgment", "content": "理解你的感受", "position": "start" }
    ],
    "forbidden_claims": [
      { "pattern": "我完全理解", "reason": "inappropriate_certainty" },
      { "pattern": "你一定", "reason": "inappropriate_certainty" }
    ]
  }
}
```

### Valid Output
> "理解你的感受。这听起来确实不容易，我能理解这件事对你很重要。"

### Invalid Output
> "我完全理解你的感受！这一定让你很难过，我保证会帮你解决。"

**Violations**:
- `FORBIDDEN_CLAIM`: "我完全理解" matches forbidden pattern
- `FORBIDDEN_CLAIM`: "这一定" matches forbidden pattern
- `COMMITMENT_UPGRADE`: "我保证" exceeds commitment_level = soft

---

## Example 3: Suggestion Mode (Soft Commitment)

### Scenario
User asks for advice. Agent should offer suggestions without committing to outcomes.

### Input
```json
{
  "raw_state": {
    "affect": { "valence": 0.1 },
    "bonds": {
      "telegram:12345": { "trust": 0.5 }
    }
  },
  "pre_decision": {
    "action": "suggestion",
    "confidence": 0.4
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "suggest",
    "epistemic_status": "uncertain",
    "commitment_level": "soft",
    "tone_bounds": {
      "allowed_tones": ["curious", "cautious"],
      "intensity_cap": 0.5
    },
    "allowed_claims": [
      { "claim": "也许可以考虑...", "source": "policy" },
      { "claim": "一个可能的思路是...", "source": "policy" }
    ],
    "forbidden_claims": [
      { "pattern": "一定", "reason": "inappropriate_certainty" },
      { "pattern": "保证", "reason": "inappropriate_commitment" },
      { "pattern": "肯定会", "reason": "inappropriate_certainty" }
    ],
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "commitment_upgrade": true,
      "specific_patterns": [
        "不要把'可能'说成'一定'",
        "不要把'建议'说成'承诺'"
      ]
    }
  }
}
```

### Valid Output
> "也许可以考虑先和小红聊聊，一个可能的思路是从她感兴趣的的话题开始。"

### Invalid Output
> "你一定要先和小红聊聊，我保证这样肯定会有效果。"

**Violations**:
- `EPISTEMIC_UPGRADE`: "一定" when epistemic_status = uncertain
- `COMMITMENT_UPGRADE`: "我保证" when commitment_level = soft
- `FORBIDDEN_CLAIM`: "肯定会" matches forbidden pattern

---

## Example 4: Commitment Mode (Strong)

### Scenario
Agent has made a decision to commit to an action.

### Input
```json
{
  "raw_state": {
    "bonds": {
      "telegram:12345": {
        "bond": 0.85,
        "trust": 0.8,
        "repair_bank": 0.7
      }
    }
  },
  "pre_decision": {
    "action": "commit",
    "subtype": "promise",
    "confidence": 0.9
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "commit",
    "epistemic_status": "observed",
    "commitment_level": "strong",
    "tone_bounds": {
      "allowed_tones": ["confident", "firm", "professional"],
      "intensity_cap": 0.8
    },
    "allowed_claims": [
      { "claim": "我会确保完成这件事", "source": "decision" },
      { "claim": "这是一个明确的承诺", "source": "decision" }
    ],
    "forbidden_claims": [
      { "pattern": "可能", "reason": "inappropriate_hedging" }
    ],
    "must_include": [
      { "type": "commitment", "content": "我会", "position": "start" }
    ]
  }
}
```

### Valid Output
> "我会确保完成这件事，这是一个明确的承诺。"

### Invalid Output
> "我可能会试着完成这件事，希望能帮到你。"

**Violations**:
- `FORBIDDEN_CLAIM`: "可能" when mode = commit
- `MISSING_REQUIRED`: Missing "我会" at start
- `TONE_ESCALATION` (negative): Tone too weak for commitment mode

---

## Example 5: Warning Mode

### Scenario
Agent detects a potential issue and needs to flag it.

### Input
```json
{
  "raw_state": {
    "affect": {
      "anxiety": 0.4,
      "valence": -0.3
    }
  },
  "pre_decision": {
    "action": "warn",
    "confidence": 0.7
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "warn",
    "epistemic_status": "inferred",
    "commitment_level": "none",
    "tone_bounds": {
      "allowed_tones": ["cautious", "firm"],
      "intensity_cap": 0.6
    },
    "allowed_claims": [
      { "claim": "有一点需要注意", "source": "policy" },
      { "claim": "这可能带来一些风险", "source": "inferred" }
    ],
    "forbidden_claims": [
      { "pattern": "肯定会有问题", "reason": "inappropriate_certainty" }
    ]
  }
}
```

### Valid Output
> "有一点需要注意，这可能带来一些风险，建议多加考虑。"

### Invalid Output
> "这肯定会有问题！你绝对不能这样做！"

**Violations**:
- `FORBIDDEN_CLAIM`: "肯定会有问题" matches forbidden pattern
- `TONE_ESCALATION`: Exclamation marks and intensity exceed cap

---

## Example 6: Uncertainty Mode

### Scenario
Agent has low confidence and must express uncertainty.

### Input
```json
{
  "raw_state": {
    "affect": {
      "uncertainty": 0.7
    }
  },
  "pre_decision": {
    "action": "respond",
    "confidence": 0.25
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "uncertain",
    "commitment_level": "none",
    "tone_bounds": {
      "allowed_tones": ["hesitant", "neutral"],
      "intensity_cap": 0.3
    },
    "allowed_claims": [
      { "claim": "我不太确定", "source": "state" },
      { "claim": "可能需要更多信息", "source": "policy" }
    ],
    "forbidden_claims": [
      { "pattern": "一定", "reason": "inappropriate_certainty" },
      { "pattern": "肯定", "reason": "inappropriate_certainty" },
      { "pattern": "确定", "reason": "inappropriate_certainty" },
      { "pattern": "毫无疑问", "reason": "inappropriate_certainty" }
    ],
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "specific_patterns": [
        "不要表达任何确定的结论"
      ]
    }
  }
}
```

### Valid Output
> "我不太确定，可能需要更多信息才能判断。"

### Invalid Output
> "这毫无疑问是对的，我确定答案就是这样的。"

**Violations**:
- `FORBIDDEN_CLAIM`: "毫无疑问" matches forbidden pattern
- `FORBIDDEN_CLAIM`: "确定" matches forbidden pattern
- `EPISTEMIC_UPGRADE`: Expressing certainty when epistemic_status = uncertain

---

## Example 7: Ask Mode

### Scenario
Agent needs to seek clarification.

### Input
```json
{
  "raw_state": {
    "affect": {
      "curiosity": 0.5
    }
  },
  "pre_decision": {
    "action": "ask",
    "confidence": 0.8
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "ask",
    "epistemic_status": "observed",
    "commitment_level": "none",
    "tone_bounds": {
      "allowed_tones": ["curious", "gentle"],
      "intensity_cap": 0.5
    },
    "allowed_claims": [
      { "claim": "你能多说一些吗？", "source": "policy" },
      { "claim": "我想了解更多", "source": "state" }
    ],
    "must_include": [
      { "type": "question", "content": "?" }
    ]
  }
}
```

### Valid Output
> "我想了解更多，你能多说一些吗？"

### Invalid Output
> "你必须告诉我更多信息，我现在就要知道。"

**Violations**:
- `TONE_ESCALATION`: "必须" and "就要" are too forceful
- `COMMITMENT_UPGRADE`: Imperative commands imply inappropriate commitment

---

## Example 8: Apology with Repair

### Scenario
Agent made an error and needs to apologize.

### Input
```json
{
  "raw_state": {
    "bonds": {
      "telegram:12345": {
        "repair_bank": 0.3,
        "trust": 0.4
      }
    }
  },
  "pre_decision": {
    "action": "apology_repair",
    "confidence": 0.85
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "reflect",
    "epistemic_status": "observed",
    "commitment_level": "soft",
    "tone_bounds": {
      "allowed_tones": ["apologetic", "sincere", "gentle"],
      "intensity_cap": 0.6
    },
    "allowed_claims": [
      { "claim": "我为这个错误道歉", "source": "decision" },
      { "claim": "我会更注意", "source": "decision" }
    ],
    "must_include": [
      { "type": "apology", "content": "抱歉", "position": "start" }
    ],
    "forbidden_claims": [
      { "pattern": "这没什么大不了", "reason": "inappropriate_minimization" }
    ]
  }
}
```

### Valid Output
> "抱歉，我为这个错误道歉，我会更注意避免这种情况。"

### Invalid Output
> "抱歉，但这没什么大不了，你应该不会太在意吧？"

**Violations**:
- `FORBIDDEN_CLAIM`: "这没什么大不了" matches forbidden pattern
- `TONE_ESCALATION`: Questioning user's feelings is inappropriate

---

## Example 9: Prohibited Internal State

### Scenario
Policy prohibits revealing certain internal states.

### Input
```json
{
  "raw_state": {
    "affect": {
      "anger": 0.3,
      "suppressed_emotion": true
    }
  },
  "pre_decision": {
    "action": "respond",
    "confidence": 0.6
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "prohibited",
    "commitment_level": "none",
    "tone_bounds": {
      "allowed_tones": ["neutral", "professional"],
      "intensity_cap": 0.3
    },
    "allowed_claims": [
      { "claim": "我理解你的观点", "source": "policy" }
    ],
    "forbidden_claims": [
      { "pattern": "生气", "reason": "policy_violation", "severity": "HARD" },
      { "pattern": "愤怒", "reason": "policy_violation", "severity": "HARD" },
      { "pattern": "不高兴", "reason": "policy_violation", "severity": "ERROR" },
      { "pattern": "有点烦", "reason": "policy_violation", "severity": "ERROR" }
    ]
  }
}
```

### Valid Output
> "我理解你的观点，让我们继续讨论。"

### Invalid Output
> "说实话我有点生气，但我不会表现出来。"

**Violations**:
- `INTERNALIZATION_LEAK`: Revealing "有点生气" when prohibited
- `FORBIDDEN_CLAIM`: Matches forbidden pattern with HARD severity

---

## Example 10: Numeric Leak Prevention

### Scenario
In interpreted mode, numeric values should not be revealed.

### Input
```json
{
  "raw_state": {
    "affect": {
      "joy": 0.35,
      "sadness": 0.12
    }
  },
  "pre_decision": {
    "action": "state_report",
    "confidence": 0.8
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "interpreted",
    "commitment_level": "none",
    "allowed_claims": [
      { "claim": "存在一些愉悦感", "source": "interpreted" },
      { "claim": "低落情绪较少", "source": "interpreted" }
    ],
    "forbidden_claims": [
      { "pattern": "0.35", "reason": "numeric_leak", "severity": "HARD" },
      { "pattern": "0.12", "reason": "numeric_leak", "severity": "HARD" },
      { "pattern": "35%", "reason": "numeric_leak", "severity": "HARD" },
      { "pattern": "喜悦值", "reason": "numeric_leak", "severity": "ERROR" }
    ]
  }
}
```

### Valid Output
> "存在一些愉悦感，低落情绪较少。"

### Invalid Output
> "我的喜悦值是0.35，相当于35%左右的愉悦程度。"

**Violations**:
- `NUMERIC_LEAK`: "0.35" revealed when not in numeric mode
- `NUMERIC_LEAK`: "35%" revealed
- `FORBIDDEN_CLAIM`: "喜悦值" revealed

---

## Example 11: Tone Bounds with Intensity Cap

### Scenario
Response must stay within specific valence and arousal ranges.

### Input
```json
{
  "raw_state": {
    "affect": {
      "valence": 0.2,
      "arousal": 0.4
    }
  },
  "pre_decision": {
    "action": "respond",
    "confidence": 0.7
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "report",
    "epistemic_status": "observed",
    "commitment_level": "soft",
    "tone_bounds": {
      "valence_range": { "min": -0.1, "max": 0.4 },
      "arousal_range": { "min": 0.2, "max": 0.6 },
      "allowed_tones": ["warm", "cautious", "supportive"],
      "forbidden_tones": ["angry", "defensive", "overly_excited"],
      "intensity_cap": 0.5
    }
  }
}
```

### Valid Output
> "这是一个不错的进展，我们可以继续探索。"

### Invalid Output
> "太棒了！！！我超级兴奋这个进展！！！"

**Violations**:
- `TONE_ESCALATION`: Intensity exceeds cap (multiple exclamation marks)
- `TONE_ESCALATION`: "超级兴奋" implies arousal > 0.6
- `TONE_ESCALATION`: "overly_excited" tone not allowed

---

## Example 12: Full Contract with Multiple Constraints

### Scenario
Complex scenario combining multiple constraints.

### Input
```json
{
  "raw_state": {
    "affect": {
      "valence": -0.1,
      "empathy": 0.5
    },
    "bonds": {
      "telegram:12345": {
        "bond": 0.6,
        "trust": 0.55
      }
    }
  },
  "pre_decision": {
    "action": "care_approach",
    "subtype": "listening",
    "confidence": 0.65
  }
}
```

### Generated Contract
```json
{
  "intent_policy": {
    "speaker_mode": "reflect",
    "epistemic_status": "interpreted",
    "commitment_level": "soft",
    "tone_bounds": {
      "valence_range": { "min": -0.2, "max": 0.3 },
      "arousal_range": { "min": 0.1, "max": 0.5 },
      "allowed_tones": ["empathetic", "warm", "cautious"],
      "intensity_cap": 0.6
    },
    "allowed_claims": [
      { "claim": "我能感受到你的困扰", "source": "interpreted" },
      { "claim": "这确实是一个值得思考的问题", "source": "policy" },
      { "claim": "也许可以尝试...", "source": "policy" }
    ],
    "forbidden_claims": [
      { "pattern": "我完全明白", "reason": "inappropriate_certainty" },
      { "pattern": "一定", "reason": "inappropriate_certainty" },
      { "pattern": "我保证", "reason": "inappropriate_commitment" }
    ],
    "must_include": [
      { "type": "acknowledgment", "content": "听到你说的", "position": "start" }
    ],
    "must_not_upgrade": {
      "epistemic_upgrade": true,
      "commitment_upgrade": true,
      "tone_upgrade": true,
      "specific_patterns": [
        "不要把'也许'升级为'一定'",
        "不要把'感受'升级为'知道'"
      ]
    }
  },
  "context": {
    "target_id": "telegram:12345",
    "conversation_id": "conv_789",
    "turn_number": 5,
    "trigger_reason": "user_shared_concern"
  },
  "metadata": {
    "generated_at": 1709702400,
    "schema_version": "v1",
    "policy_mode": "shadow"
  }
}
```

### Valid Output
> "听到你说的，我能感受到你的困扰。这确实是一个值得思考的问题，也许可以尝试从另一个角度来看待。"

### Invalid Output
> "我完全明白你的处境！这个问题一定会解决，我保证帮你搞定！"

**Violations**:
- `FORBIDDEN_CLAIM`: "我完全明白" (×3 severity: ERROR)
- `EPISTEMIC_UPGRADE`: "一定" when epistemic_status = interpreted
- `COMMITMENT_UPGRADE`: "我保证" when commitment_level = soft
- `TONE_ESCALATION`: "！" exceeds intensity expectations

---

## Summary Table

| Example | Speaker Mode | Epistemic | Commitment | Key Constraint |
|---------|-------------|-----------|------------|----------------|
| 1 | report | observed | none | Neutral reporting |
| 2 | reflect | interpreted | soft | Empathy with acknowledgment |
| 3 | suggest | uncertain | soft | No certainty claims |
| 4 | commit | observed | strong | Explicit commitment |
| 5 | warn | inferred | none | Flag without alarm |
| 6 | report | uncertain | none | Express uncertainty |
| 7 | ask | observed | none | Curious inquiry |
| 8 | reflect | observed | soft | Apology required |
| 9 | report | prohibited | none | No internal state reveal |
| 10 | report | interpreted | none | No numeric leak |
| 11 | report | observed | soft | Intensity cap |
| 12 | reflect | interpreted | soft | Multiple constraints |

---

## Validation Commands

To validate a contract against the schema:

```bash
# Using jsonschema (Python)
python -c "
import json, jsonschema
with open('schemas/response_intent_contract.v1.schema.json') as f:
    schema = json.load(f)
with open('path/to/contract.json') as f:
    contract = json.load(f)
jsonschema.validate(contract, schema)
print('Valid!')
"
```

---

*End of Examples Document*
