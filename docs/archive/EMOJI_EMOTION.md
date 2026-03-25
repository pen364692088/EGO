# Emoji-Emotion 智能映射系统

## 概述

基于 EmoTag1200 数据集的上下文感知 emoji 情感分析系统。

## 功能

### 1. 基础情绪映射

150 个常用 emoji 映射到 8 维情绪空间：
- anger, anticipation, disgust, fear, joy, sadness, surprise, trust

转换为 emotiond 的 5 维情绪：
- joy, sadness, anger, anxiety, loneliness

### 2. 上下文感知

同一 emoji 在不同语境下含义不同：

| 文本 | Emoji | 关系 | 情绪 | World Event |
|------|-------|------|------|-------------|
| 你好！很高兴见到你 😄 | 😄 | bond=0.8, trust=0.7 | joy=1.20 | care |
| 呵呵，行吧 😄 | 😄 | bond=0.3, trust=0.2 | joy=-0.50 | rejection |
| 你开心就好 😄 | 😄 | bond=0.5, trust=0.3 | joy=-0.50 | rejection |

### 3. Sarcasm 检测

检测讽刺信号并翻转情绪：
- "呵呵", "哈哈", "哦", "嗯嗯", "行吧", "算了"
- "你开心就好", "随便", "无所谓"

### 4. 关系上下文

Bond 和 Trust 影响情绪放大/衰减：

| Bond | Trust | 效果 |
|------|-------|------|
| > 0.7 | > 0.7 | joy × 1.2, sadness × 0.8 |
| < 0.3 | < 0.3 | anger × 1.3, anxiety × 1.2 |

### 5. 个性化学习

记录用户特定的 emoji 使用模式：
- 存储 emoji + context + detected_emotion
- 支持用户纠正反馈
- 未来可训练个性化模型

## 使用方法

```python
from emotiond.emoji_emotion import analyze_message_emojis

result, world_event = analyze_message_emojis(
    text="你好！很高兴见到你 😄",
    actor="user",
    target="assistant",
    relationship={"bond": 0.8, "trust": 0.7},
    user_id="user_123"
)

# result['aggregated_vector'] → {'joy': 1.20, 'anger': 0.0, ...}
# world_event['meta']['subtype'] → 'care'
```

## 与 emotiond 集成

```python
# 在收到用户消息后调用
result, world_event = analyze_message_emojis(...)

if world_event:
    # 发送到 emotiond
    response = requests.post(
        "http://127.0.0.1:18080/event",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=world_event
    )
```

## 数据来源

- EmoTag1200: 150 emoji × 8 emotions
- 来源: https://github.com/abushoeb/EmoTag
- 论文: EMNLP 2020

## 扩展方向

1. **LLM 增强**: 使用 LLM 进行更精准的上下文分析
2. **动态学习**: 从用户反馈中持续学习
3. **多模态**: 支持 GIF、表情包等
4. **文化差异**: 不同文化背景下的 emoji 含义差异
