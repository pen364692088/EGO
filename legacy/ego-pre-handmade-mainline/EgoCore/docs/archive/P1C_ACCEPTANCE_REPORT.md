# P1-C Acceptance Report

**Status:** CLOSED  
**Date:** 2026-03-17  
**Scope:** 跨 intent 自然表达对齐修复 (Cross-Intent Natural Expression Alignment)

---

## 1. 目标

修复 question intent 短问句在 expressive_intent_candidate → outward_response_contract 映射中的过度压缩问题，消除 "收到"/"好"/"我在"/"嗯？" 等机械占位回复。

---

## 2. 交付物

### 2.1 核心组件

| 组件 | 路径 | 说明 |
|------|------|------|
| QuestionVerbalizer | `app/response/question_verbalizer.py` | 短问句专用 verbalizer |
| SocialChatHandler 集成 | `app/handlers/social_chat_handler.py` | 短问句检测与路由 |
| 测试套件 | `tools/test_p1c_implementation.py` | P1-C 验证测试 |

### 2.2 短问句类型覆盖

| 类型 | 触发词 | 回复示例 |
|------|--------|----------|
| SHORT_CLARIFICATION | 什么？/啥？ | "具体指哪部分？" / "展开讲讲？" |
| WHY_PROBE | 为什么？/为啥？ | "哪块让你想问了？" / "突然好奇这个？" |
| SURPRISED_FOLLOWUP | 啊？/嗯？ | "有点意外，怎么了？" / "出什么事了？" |
| MEANING_PROBE | 啥意思？/我不太懂/没明白/说清楚点 | "我没说明白？" / "需要我换个说法？" |
| REPEAT_REQUEST | 你说什么？/再说一遍 | "我说：{context}" / "简单来说：{context}" |
| INVITATION | 说吧/请讲/然后呢 | "嗯，你说。" / "我听着，你说。" |

---

## 3. 验收测试

### 3.1 P1-C.1 基础覆盖

| 输入 | 输出 | 状态 |
|------|------|------|
| 什么？ | "具体指哪部分？" | ✅ |
| 为什么？ | "哪块让你想问了？" | ✅ |
| 啊？ | "有点意外，怎么了？" | ✅ |
| 啥意思？ | "我没说明白？" | ✅ |
| 你说什么？ | "我说：{context}" | ✅ |

### 3.2 P1-C.2 扩展覆盖

| 输入 | 输出 | 状态 |
|------|------|------|
| 我不太懂 | "需要我换个说法？" | ✅ |
| 说清楚点 | "我没说明白？" | ✅ |
| 说吧 | "嗯，你说。" | ✅ |
| ？ | "没太跟上，你再说说？" | ✅ |

### 3.3 禁用词清除验证

| 禁用词 | 验证结果 |
|--------|----------|
| "收到" | 不再作为独立回复 |
| "好。" | 不再作为独立回复 |
| "我在" | 不再作为独立回复 |
| "嗯？" | 不再作为独立回复 |

---

## 4. 架构合规

### 4.1 双核边界保持

- ✅ OpenEmotion 保留：interaction_interpretation, social_signal, relationship_implication, appraisal_state_delta, response_tendency, expressive_intent_candidate, reply_urge, reflection_note, policy_hint
- ✅ EgoCore 保留：runtime_route, should_reply, should_start_task, should_call_tool, should_wait, should_block, should_escalate, outward_response_contract, execution_guard_result, safety_decision

### 4.2 强制拆分遵守

- ✅ interaction_interpretation (OpenEmotion) ≠ runtime_route (EgoCore)
- ✅ expressive_intent_candidate (OpenEmotion) ≠ outward_response_contract (EgoCore)
- ✅ reply_urge (OpenEmotion) ≠ should_reply (EgoCore)

---

## 5. Git Commits

```
1698b1c feat(question-verbalizer): P1-C.1 短问句自然表达增强
7da73f3 feat(social-chat): P1-C.1 集成 QuestionVerbalizer
5ddb2d5 feat(response): export QuestionVerbalizer in response module
036421f fix(question-verbalizer): P1-C.2 收口微补丁
198fd9f fix(question-verbalizer): 扩展短问句覆盖
```

---

## 6. 结论

P1-C 跨 intent 自然表达对齐修复完成。短问句表达已与 P1-A/P1-B 自然标准对齐，禁用词清除验证通过，双核边界保持完整。

**状态：CLOSED**

---

## 7. 下一步

回到主线：MVP11.5 / SRAP Stabilization + Intent Alignment
