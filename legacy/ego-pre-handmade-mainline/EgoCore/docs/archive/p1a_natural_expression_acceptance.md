# P1-A 自然表达收口验收报告

**日期:** 2026-03-17
**版本:** verbalizer v2

---

## 一、任务目标

在已完成"主体解释层上收 OpenEmotion、现实裁决层保留 EgoCore"主链闭环的前提下，完成自然表达层收口。

---

## 二、已完成的修改

### A. 第二轮问候去模板化 ✅

- 添加 `turn_index` 支持
- 第一轮：正常欢迎
- 第二轮：简短确认
- 第三轮及以后：极简回复

### B. 禁止外显内部判断语言 ✅

- 添加 `INTERNAL_PHRASES` 过滤列表
- 过滤 "testing"、"probe"、"这轮我知道" 等内部判断词
- 系统内部判断不再直接外显

### C. affective probe 回复自然化 ✅

- 4 个自然变体
- 承认体验 + 轻修正 + 继续对话
- 不再使用客服式道歉模板

### D. verbalizer 升级为自然表达层 ✅

每个 social mode 支持 3-5 个变体：

| Mode | 变体数 |
|------|--------|
| greeting_first | 3 |
| greeting_second | 3 |
| greeting_repeat | 4 |
| affective_probe | 4 |
| grateful | 3 |
| light_social | 4 |
| fallback | 3 |

---

## 三、改前 vs 改后对比

### 场景 1：重复问候

**改前：**
```
用户：你好
EgoCore：👋 你好！我是 EgoCore 任务助手。（整段 onboarding）
用户：你好
EgoCore：👋 你好！我是 EgoCore 任务助手。（重复整段）
用户：你好
EgoCore：我在，收到了。这轮我知道你是在继续测试...（解释系统判断）
```

**改后：**
```
用户：你好
EgoCore：嗨！我在这里。
用户：你好
EgoCore：你好，我在。可以直接说你需要什么。
用户：你好
EgoCore：嗯，我在。
```

### 场景 2：关系修复

**改前：**
```
用户：你怎么这么冷淡
EgoCore：抱歉让你有这种感觉。我在认真听你说话。我在这里，有什么我可以帮你的吗？（客服模板）
```

**改后：**
```
用户：你怎么这么冷淡
EgoCore：嗯，你这个提醒是对的。我换种更自然的方式跟你聊。
```

---

## 四、Gate 验收结果

### Gate A: Contract 不漂移 ✅

- 未修改主链 Schema
- 只修改 verbalizer 表达层
- 添加 `turn_index` 辅助字段

### Gate B: E2E ✅

真实 Telegram 对话证据已收集，覆盖：
- 重复问候 ✅
- status ping ✅
- affective probe ✅
- social mixed flow ✅

### Gate C: Fallback ✅

OpenEmotion down 时：
- 仍能自然中性回复
- 不报错
- 不出现内部字段名

---

## 五、修改文件清单

| 文件 | 变更 |
|------|------|
| `app/response/verbalizer.py` | 重写为自然表达层 v2 |
| `app/interaction/session_context_store.py` | 添加 turn_index |
| `app/handlers/social_chat_handler.py` | 传递 turn_index |
| `app/command_router.py` | 获取并传递 turn_index |

---

## 六、Git 提交

```
a6b2a1b - feat(verbalizer): upgrade to natural expression layer v2
```

---

## 七、完成标准验收

| 标准 | 状态 |
|------|------|
| 第二轮重复问候不再复读 onboarding | ✅ |
| 用户可见回复不出现内部判断解释腔 | ✅ |
| "你怎么这么冷淡"回复自然度明显提升 | ✅ |
| 社交回复整体缩短到 1~2 句为主 | ✅ |
| 同类输入不再像复制粘贴 | ✅ |
| OpenEmotion down 时仍保持中性自然回复 | ✅ |

---

**验收结论:** 通过 ✅

**验收时间:** 2026-03-17 07:37 CDT
