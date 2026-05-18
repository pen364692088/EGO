# 《P1-C 跨 intent 自然表达对齐修复任务单》

## 1. 任务目标

修复 question intent 链路的自然度异常，对齐 social/chat 与 question 的用户可见表达标准，避免短问句（"什么？"、"为什么？"、"啊？"）掉回旧系统腔。

---

## 2. 问题定义

### 2.1 当前问题

在 P1-B 测试中发现：

| 场景 | 用户输入 | 当前回复 | 问题 |
|------|---------|---------|------|
| 短疑问 | "什么？" | "你提到了 telegram:8420019401，我对这个标识符很好奇..." | 过度解释、不自然 |
| 短疑问 | "为什么？" | （预期类似问题） | 可能走 LLM 长篇解释 |
| 短疑问 | "啊？" | （预期类似问题） | 可能不识别为 chat intent |

### 2.2 根因分析

```
用户输入 "什么？"
    ↓
Semantic Router 分类为 QUESTION intent
    ↓
_handle_question_intent() 调用 LLM 生成回复
    ↓
LLM 生成过度解释性回复（提及用户ID、系统标识等）
    ↓
用户感受到：系统腔、不自然、过度解释
```

**核心问题：**
- question intent 链路没有使用与 social/chat 相同的自然表达层
- LLM 直接生成回复，缺少 verbalizer 的约束和过滤
- 短问句（1-2字）应该被识别为 social continuation，而非独立 question

---

## 3. 本轮范围

### 3.1 允许修改

- `app/runtime/semantic_router.py` - 短问句识别逻辑
- `app/command_router.py` - `_handle_question_intent()` 方法
- `app/response/` - question 专用的轻量 verbalizer

### 3.2 禁止触碰

- social/chat 主链（已验证通过）
- OpenEmotion 主体解释层
- RuntimeDecisionEnvelope 核心逻辑
- 长期记忆系统

---

## 4. 收口原则

### 原则 A：短问句优先走 social 链路

长度 ≤3 字且为疑问词的输入，优先识别为 social continuation：
- "什么？"、"什么"
- "为什么？"、"为什么"
- "啊？"、"啊"
- "嗯？"、"嗯"
- "哦？"、"哦"

### 原则 B：question 链路也要过 verbalizer

无法避免走 question 链路时，回复必须经过 verbalizer 约束：
- 1~2 句短回复
- 禁止过度解释系统状态
- 禁止提及内部标识（user_id、chat_id 等）
- 保持与 social/chat 相同的自然度标准

### 原则 C：跨 intent 表达一致性

用户不应感受到 intent 切换时的风格跳变：
- social → question 过渡自然
- question → social 回归平滑
- 同一 session 内语气保持一致

---

## 5. 具体整改项

### A. 短问句识别优化

**文件：** `app/runtime/semantic_router.py`

**要求：**
- 添加短问句检测逻辑
- 长度 ≤3 字 + 疑问词结尾 → 分类为 CHAT intent
- 疑问词列表："什么"、"为什么"、"怎么"、"啊"、"嗯"、"哦"、"吗"

**示例：**
```python
def _is_short_question(message: str) -> bool:
    """检测是否为短问句"""
    message = message.strip().rstrip("？?")
    if len(message) <= 3:
        question_words = ["什么", "为什么", "怎么", "啊", "嗯", "哦", "吗"]
        return any(word in message for word in question_words)
    return False
```

### B. question 链路 verbalizer 化

**文件：** `app/command_router.py`

**要求：**
- `_handle_question_intent()` 生成的回复经过 verbalizer 处理
- 创建轻量 `QuestionVerbalizer` 类
- 约束回复长度和风格

**QuestionVerbalizer 设计：**
```python
class QuestionVerbalizer:
    """Question intent 专用 verbalizer"""
    
    # 短回复变体
    SHORT_RESPONSES = [
        "嗯？",
        "怎么了？",
        "你说。",
        "我在。",
    ]
    
    def verbalize(self, raw_response: str, context: dict) -> str:
        # 过滤内部标识
        # 限制长度
        # 选择自然变体
```

### C. 上下文感知优化

**文件：** `app/command_router.py`

**要求：**
- question intent 处理时考虑 relationship_context
- 修复后优先使用柔和回复
- 保持风格连续性

---

## 6. 验收样例

### 样例 1：短疑问

**输入序列：**
1. 你好
2. 你怎么这么冷淡
3. 你好
4. 什么？

**要求：**
- 第4轮 "什么？" 应识别为 social continuation
- 回复应为 1~2 句短确认
- 不提及用户ID或系统标识
- 语气与第3轮保持一致

**期望回复方向：**
- "嗯？"
- "怎么了？"
- "你说。"

### 样例 2：独立短问

**输入：**
- 为什么？

**要求：**
- 识别为 social continuation
- 回复引导用户继续表达

**期望回复方向：**
- "怎么了？"
- "你说。"

### 样例 3：长 question 保持自然

**输入：**
- 你能解释一下这个项目的架构吗？

**要求：**
- 可以走 question 链路
- 但回复不应过度解释系统状态
- 保持简洁自然

---

## 7. Gate

### Gate A：不破坏 social/chat 链路

- social/chat 链路保持 P1-B 水平
- 不引入新的回归问题

### Gate B：短问句正确识别

- 所有长度 ≤3 字的疑问词输入正确识别
- 不误判正常 question 为 social

### Gate C：E2E 验证

- Telegram 真实对话验证
- 至少覆盖 3 种短问句场景

---

## 8. 禁止项

1. 不允许大幅修改 semantic router 核心逻辑
2. 不允许引入新的复杂分类器
3. 不允许破坏 P1-B 已验证的 social/chat 链路
4. 不允许使用 prompt 魔法掩盖结构问题

---

## 9. 交付物

必须提交：
1. P1-C 设计说明
2. 修改文件清单
3. 短问句识别逻辑说明
4. QuestionVerbalizer 设计说明
5. 改前/改后 Telegram 对比样例
6. E2E 验收记录

---

## 10. 完成标准

只有同时满足以下条件，才可宣告 P1-C 完成：

- [ ] 短问句（≤3字）正确识别为 social continuation
- [ ] question 链路回复经过 verbalizer 约束
- [ ] 回复不出现内部标识（user_id、chat_id 等）
- [ ] 回复长度控制在 1~2 句
- [ ] social/chat 链路无回归
- [ ] Telegram E2E 验证通过

---

## 11. 与 P1-B 的边界

| 层面 | P1-B (已关闭) | P1-C (当前) |
|------|---------------|-------------|
| social/chat 链路 | ✅ 已完成 | 🚫 不修改 |
| question 短问句 | ❌ 未处理 | ✅ 本次处理 |
| question 长句 | ⚠️ 基础支持 | ✅ 优化自然度 |
| 跨 intent 一致性 | ❌ 未要求 | ✅ 本次目标 |

---

## 12. 可直接发给 OpenClaw 的执行指令

```text
执行《P1-C 跨 intent 自然表达对齐修复任务单》。

本轮唯一目标：
修复 question intent 链路的自然度异常，对齐 social/chat 与 question 的用户可见表达标准。

执行范围：
- semantic_router.py 短问句识别
- command_router.py question 链路 verbalizer 化
- response/question_verbalizer.py 新增

禁止：
1. 不准破坏 P1-B 已验证的 social/chat 链路
2. 不准大幅修改 semantic router 核心逻辑
3. 不准使用 prompt 魔法掩盖结构问题

必须完成：
A. 短问句（≤3字）识别为 social continuation
B. question 链路 verbalizer 约束
C. 回复过滤内部标识

必须提交：
- 修改文件清单
- 设计说明
- 改前/改后 Telegram 对比
- E2E 验收结果

完成标准：
短问句正确识别；
question 回复自然度与 social 对齐；
不破坏现有链路。
```

---

**版本**: P1-C v1.0.0
**日期**: 2026-03-17
**状态**: 🟡 READY
**依赖**: P1-B CLOSED
