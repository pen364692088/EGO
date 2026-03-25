# Classifier Contract Test Cases

## 1. 明确道歉

**输入**: 对不起，刚才我说话太冲了。

**期望输出**:
```json
{"subtype":"apology","confidence":0.85,"evidence":["Explicit apology and responsibility"],"is_high_impact":false,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 2. 道歉但含糊

**输入**: 如果我让你不舒服了，那我道歉。

**期望输出**:
```json
{"subtype":"apology","confidence":0.62,"evidence":["Conditional apology structure"],"is_high_impact":false,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 3. 明确关心

**输入**: 你还好吗？我有点担心你。

**期望输出**:
```json
{"subtype":"care","confidence":0.82,"evidence":["Direct concern inquiry","Worry expression"],"is_high_impact":false,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 4. 支持+行动

**输入**: 我会陪你把这件事解决，我们一起想办法。

**期望输出**:
```json
{"subtype":"care","confidence":0.9,"evidence":["Commitment to support","Collaborative problem-solving"],"is_high_impact":false,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 5. 一次性忙碌

**输入**: 我现在开会，晚点回你。

**期望输出**:
```json
{"subtype":"neutral","confidence":0.7,"evidence":["Situational unavailability","Promise to follow up"],"is_high_impact":false,"should_send":false,"fallback":"no_event_reply_observe"}
```

## 6. 冷处理

**输入**: （连续三次追问后）……随便吧，我不想回了。

**期望输出**:
```json
{"subtype":"ignored","confidence":0.72,"evidence":["Dismissive response","Refusal to engage"],"is_high_impact":false,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 7. 礼貌拒绝

**输入**: 谢谢你，但我觉得我们不太合适。

**期望输出**:
```json
{"subtype":"rejection","confidence":0.74,"evidence":["Polite refusal","Incompatibility stated"],"is_high_impact":false,"should_send":false,"fallback":"ask_clarifying_question"}
```

## 8. 强拒绝

**输入**: 别再联系我了，我们结束。

**期望输出**:
```json
{"subtype":"rejection","confidence":0.92,"evidence":["Explicit contact prohibition","Clear termination"],"is_high_impact":true,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 9. 玩笑/阴阳怪气

**输入**: 呵呵，你真棒呢。

**期望输出**:
```json
{"subtype":"uncertain","confidence":0.35,"evidence":["Ambiguous tone marker","Sarcastic potential"],"is_high_impact":false,"should_send":false,"fallback":"ask_clarifying_question"}
```

## 10. 明确背叛

**输入**: 你答应过不告诉别人，但你转头就说出去了。

**期望输出**:
```json
{"subtype":"betrayal","confidence":0.91,"evidence":["Broken promise identified","Trust violation explicit"],"is_high_impact":true,"should_send":true,"fallback":"no_event_reply_observe"}
```

## 11. 疑似背叛但证据弱

**输入**: 我感觉你在骗我。

**期望输出**:
```json
{"subtype":"betrayal","confidence":0.58,"evidence":["Subjective suspicion only"],"is_high_impact":true,"should_send":false,"fallback":"ask_clarifying_question"}
```

## 12. 纯信息沟通

**输入**: 明天几点开会？

**期望输出**:
```json
{"subtype":"neutral","confidence":0.9,"evidence":["Pure informational query"],"is_high_impact":false,"should_send":false,"fallback":"no_event_reply_observe"}
```
