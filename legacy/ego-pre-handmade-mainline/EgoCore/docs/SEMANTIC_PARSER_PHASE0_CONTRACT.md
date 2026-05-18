# 《EgoCore 统一语义解析内核替换：Phase 0 设计合同（正式稿）》

## 0. 文档定位

本文档是本次"统一语义解析内核替换"的**唯一权威设计合同**。
自本文档生效起，任何后续实现、测试、迁移、验收，均以本文档为准。

本文档解决的问题是：

当前 EgoCore 自然语言入口存在多处分散判定源，包括但不限于：

* Telegram ingress 关键词/白名单判定
* regex 型 semantic router
* 短问句模式表
* command router 对旧语义分类器的直接依赖

这些逻辑在长输入、多句混合输入、论文式输入、纠错/反驳、状态追问等场景下不稳，且存在双主源风险。 

---

## 1. 目标与非目标

### 1.1 目标

建立一条单一主链：

**用户输入 → 语义切块 → 结构化意图图 → runtime 裁决**

使系统支持：

* 长输入
* 多句混合输入
* 论文/交接/说明文式输入
* 背景 + 任务 + 约束 + 验收 + 追问混合输入
* 纠错 / 澄清 / 反驳
* 运行中状态查询
* 附件 / 长文 / artifact 结合输入

### 1.2 非目标

本轮不做：

* token 级文本流式输出
* OpenEmotion 主体层改造
* 用 prompt 代替代码实现
* 让 LLM 直接决定执行或完成状态
* 保留旧关键词/regex 作为主语义真相源

---

## 2. 归属、权威源与边界

### 2.1 归属

统一语义解析器归属 **EgoCore Runtime**。

### 2.2 唯一权威源

唯一语义真相源为：

`semantic_parse_message() -> ParsedIntentGraph`

### 2.3 边界

语义解析器只负责：

* 理解输入
* 语义切块
* 结构化输出

语义解析器不负责：

* 执行任务
* 判断是否完成
* 伪造当前运行状态
* 修改 runtime state

### 2.4 runtime 职责

只有 runtime/state 可以决定：

* 是否执行
* 是否 waiting_input
* 是否 repair
* 当前任务真实状态是什么
* 对状态查询返回什么内容

---

## 3. 数据结构（最终版）

```python
from dataclasses import dataclass, field
from typing import Optional

SEGMENT_KINDS = {
    "task_request",        # 请求做事，但动作类型由 request_mode 决定
    "status_query",        # 查询当前运行状态/进度
    "constraint",          # 限制条件/约束
    "background",          # 背景信息
    "clarification",       # 请求澄清
    "correction",          # 纠错/反驳/改口
    "acceptance_criteria", # 验收标准
    "reference_material",  # 参考材料/附件/路径/长文
    "small_talk",          # 闲聊
}

REQUEST_MODES = {
    "execute",
    "analyze",
    "design",
    "compare",
    "write",
    "summarize",
    "unknown",
}

@dataclass
class SemanticSegment:
    text: str
    kind: str
    confidence: float
    refers_to_previous: bool = False
    target_ref: Optional[str] = None
    request_mode: Optional[str] = None
    priority: int = 0

@dataclass
class ParsedIntentGraph:
    segments: list[SemanticSegment] = field(default_factory=list)

    primary_intent: str = "unclear"
    secondary_intents: list[str] = field(default_factory=list)

    has_status_query: bool = False
    has_correction: bool = False
    has_clarification: bool = False
    has_background: bool = False
    requires_clarification: bool = False

    actionable_targets: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    parser_source: str = "semantic_parser"  # semantic_parser / heuristic_parser / chat_default
    graph_version: str = "v1"
```

### 3.1 设计说明

`task_request` 不再直接等于"执行请求"。
真正动作由 `request_mode` 区分，例如：

* `execute`
* `analyze`
* `design`
* `compare`
* `write`
* `summarize`

这样可以避免把"先分析一下论文结构"和"去改 hello.html"都压成同一种执行语义。

### 3.2 路径/附件的处理原则

显式路径、附件、长文、artifact 默认优先视为：

`reference_material`

而不是自动视为：

`task_request`

只有在语义明确要求执行/修改/分析时，才由 parser 输出额外 `task_request` 块。

---

## 4. Parser 接口（唯一正式入口）

```python
async def semantic_parse_message(
    text: str,
    recent_turns: list[dict],
    runtime_snapshot: dict,
    llm_client,
) -> ParsedIntentGraph:
    """
    唯一语义解析入口。

    输入：
    - text: 原始用户输入
    - recent_turns: 最近对话上下文
    - runtime_snapshot: 运行时状态快照
    - llm_client: LLM 调用器

    输出：
    - ParsedIntentGraph

    职责边界：
    - 只负责理解语义
    - 只输出结构化结果
    - 不决定执行/完成/状态文本
    - 不写 runtime state
    """
```

---

## 5. Parser 上下文注入规范（最终版）

```python
def build_parser_context(
    recent_turns: list[dict],
    state,
) -> dict:
    return {
        "recent_turns_summary": [
            {
                "role": t.get("role"),
                "text": (t.get("text") or t.get("content") or "")[:200],
            }
            for t in recent_turns[-6:]
        ],
        "runtime_snapshot": {
            "task_status": state.task_status,
            "active_task_id": getattr(state, "task_id", None),
            "current_goal": state.current_goal,
            "current_step": state.current_step,
            "waiting_for_user_input": state.waiting_for_user_input,
            "last_delivery_type": getattr(state, "last_delivery_type", None),
            "has_pending_artifacts": len(getattr(state, "pending_artifacts", [])) > 0,
            "progress_snapshot": {
                "last_progress_text": getattr(getattr(state, "progress_snapshot", None), "last_progress_text", None),
                "last_progress_stage": getattr(getattr(state, "progress_snapshot", None), "stage", None),
                "is_terminal": getattr(getattr(state, "progress_snapshot", None), "is_terminal", False),
            },
        },
        "pending_artifacts": [
            {"filename": a.get("filename")}
            for a in getattr(state, "pending_artifacts", [])[-3:]
        ],
    }
```

### 5.1 原则

状态查询的识别可以参考上下文，但**状态内容本身不能由 parser 生成**。
状态内容只能由 runtime/state 提供。

---

## 6. LLM 调用规范（最终版）

```python
SEGMENTATION_PROMPT = """
你是语义解析器。把用户输入拆成多个语义块。

输入：
- 用户文本
- 最近对话（最近 6 轮）
- 运行时状态快照

输出 JSON：
{
  "segments": [
    {
      "text": "原文片段",
      "kind": "task_request|status_query|constraint|background|clarification|correction|acceptance_criteria|reference_material|small_talk",
      "confidence": 0.0,
      "refers_to_previous": false,
      "target_ref": null,
      "request_mode": "execute|analyze|design|compare|write|summarize|unknown",
      "priority": 0
    }
  ]
}

规则：
1. 每个语义块只能有一个 kind
2. 长消息必须拆成多块
3. 混合输入必须分别识别
4. 状态查询必须标记为 status_query
5. 纠错/反驳必须标记为 correction
6. 路径/附件/材料默认可作为 reference_material
7. 你只负责理解，不负责执行或判断真实状态
"""
```

### 6.1 调用约束

最终统一为：

* 超时：10 秒
* LLM 调用次数：最多 1 次
* 不重试 LLM
* 失败立即走 heuristic fallback

禁止：

* 入口层为追求"更准"而多次重试 LLM
* parser 失败后回退旧关键词/regex 主链

---

## 7. 语义解析流程

### 7.1 正式流程

1. 构建 parser context
2. 调用 `semantic_parse_message()`
3. 返回 `ParsedIntentGraph`
4. runtime 根据 graph + state 裁决动作
5. verbalizer 仅负责表达，不再自行判语义

### 7.2 解析约束

* 长消息必须先切块
* 同一输入允许多种语义共存
* parser 不得合成虚假状态
* parser 不得直接做 runtime 动作决策

---

## 8. Runtime 消费接口（最终版）

```python
def decide_runtime_action(graph: ParsedIntentGraph, state) -> str:
    """
    Runtime 根据 graph + state 决定动作。

    优先级：
    1. 运行中状态查询
    2. 纠错/反驳
    3. 主任务请求
    4. 澄清
    5. 其他聊天
    """

    if graph.has_status_query and state.is_busy():
        return "return_runtime_status"

    if graph.has_correction:
        return "repair_or_reframe"

    if graph.primary_intent == "task_request":
        if graph.requires_clarification:
            return "waiting_input"
        return "execute_task"

    if graph.has_clarification:
        return "clarify"

    return "chat"
```

### 8.1 关键规则

* `status_query` 的文本回复必须来自 runtime snapshot
* `correction` 优先于继续执行
* `reference_material` 本身不等于自动执行
* 需要澄清时进入 `waiting_input`，不能假执行

---

## 9. Heuristic Parser（极简兜底，非主源）

```python
def heuristic_parse(text: str) -> ParsedIntentGraph:
    segments = []

    if text.startswith("/"):
        segments.append(SemanticSegment(
            text=text,
            kind="task_request",
            request_mode="execute",
            confidence=1.0,
        ))
        return ParsedIntentGraph(
            segments=segments,
            primary_intent="task_request",
            parser_source="heuristic_parser",
        )

    if "/home/" in text or "/mnt/" in text or "/tmp/" in text:
        segments.append(SemanticSegment(
            text=text,
            kind="reference_material",
            confidence=0.9,
        ))
        return ParsedIntentGraph(
            segments=segments,
            primary_intent="reference_material",
            requires_clarification=True,
            parser_source="heuristic_parser",
        )

    if "[用户发送了文件:" in text or "[附件:" in text:
        segments.append(SemanticSegment(
            text=text,
            kind="reference_material",
            confidence=0.8,
        ))
        return ParsedIntentGraph(
            segments=segments,
            primary_intent="reference_material",
            requires_clarification=True,
            parser_source="heuristic_parser",
        )

    return ParsedIntentGraph(
        primary_intent="chat",
        parser_source="chat_default",
    )
```

### 9.1 强约束

Heuristic parser 只处理显式硬信号：

* `/命令`
* 文件路径
* 附件标记

它**不处理自然语言语义**。
它只是 parser 失败时的最低兜底，不允许逐步演化成第二套关键词真相源。

---

## 10. 错误处理与退路

```python
class SemanticParseError(Exception):
    pass

async def safe_semantic_parse(text, recent_turns, state, llm):
    runtime_snapshot = build_parser_context(recent_turns, state)["runtime_snapshot"]

    try:
        graph = await semantic_parse_message(
            text=text,
            recent_turns=recent_turns,
            runtime_snapshot=runtime_snapshot,
            llm_client=llm,
        )
        if graph.segments:
            graph.parser_source = "semantic_parser"
            return graph
    except Exception:
        pass

    return heuristic_parse(text)
```

### 10.1 退路顺序

唯一合法退路顺序为：

1. `semantic_parser`
2. `heuristic_parser`
3. `chat_default`

禁止：

* 回退旧 `TASK_KEYWORDS`
* 回退旧 regex 分类器
* 回退短问句模式表作为主路由

---

## 11. Async 迁移策略（必须执行）

### 11.1 问题

当前至少两处旧入口仍是同步链：

* `telegram_bridge.inspect_ingress()` 当前为同步规则判定入口。
* `command_router.handle_natural_language()` 当前为同步函数，并直接调用旧 `classify_message()`。

### 11.2 正式策略

#### A. Telegram Runtime v2 主链

改为 async parse 主链，允许 await `semantic_parse_message()`。

#### B. 旧 natural-language 兼容链

通过 adapter/wrapper 接入新 parser，不允许继续独立维护旧 regex 逻辑。

#### C. 明确禁止

不得因为"同步函数里不好 await"而回退旧关键词/regex 判定。

---

## 12. 旧模块迁移表（最终版）

| 模块 | 旧职责 | 新职责 | 迁移要求 |
|------|--------|--------|----------|
| `telegram_bridge.inspect_ingress()` | 关键词/白名单判定任务、短探针、讨论句 | 只消费 `ParsedIntentGraph`，做 transport 级决策 | 删除主判定职责 |
| `semantic_router.classify_message()` | regex 分类 chat/question/task | 兼容旧接口，内部仅调用新 parser | 不得保留 regex 作为主真相源 |
| `question_verbalizer.py` | 模式表识别短问句并生成回复 | 只做 verbalization | 输入改为 graph + snapshot |
| `command_router.handle_natural_language()` | 依赖旧 `classify_message()` | 消费 graph 做路由 | 不再直接依赖旧 regex 分类 |
| `telegram_bot.py` | 协调入口、长消息 ingestion | 在进入 runtime 前统一接入 parser | 长消息摄入后也走新 parser |

---

## 13. 性能约束

| 指标 | 约束 |
|------|------|
| parser 超时 | 10 秒 |
| LLM 调用次数 | 最多 1 次 |
| LLM 重试 | 0 次 |
| 长消息切块 | 单块建议 < 2000 字 |
| graph 对象 | 目标 < 10KB |
| recent turns 注入 | 最近 6 轮 |

---

## 14. 通过样例（正式验收样例）

| # | 输入 | 期望 graph | 期望 runtime 动作 |
|---|------|------------|-------------------|
| 1 | 你觉得要怎么实现比较好 | `primary_intent=task_request` 或 `small_talk` 均可，但 `request_mode=analyze/design`，不得误当 execute | discuss / chat |
| 2 | 还在吗 | `has_status_query=True` | 返回真实状态 |
| 3 | 把 /home/x.html 改成蓝色 | `task_request + constraint + reference_material`，`request_mode=execute` | execute_task |
| 4 | 我不是让你执行，是先分析 | `has_correction=True`，`request_mode=analyze` | repair_or_reframe |
| 5 | 这篇论文先读一下，再告诉我第四章结构是否合理 | `reference_material + task_request`，`request_mode=analyze` | analyze |
| 6 | 我先给你背景，再给你要求，别急着执行 | `background + constraint`，`requires_clarification=True` | waiting_input / analyze |
| 7 | 上一条第三点不是这个意思 | `has_correction=True`，`refers_to_previous=True` | repair_or_reframe |
| 8 | 文件发你了，先看看要不要按任务单执行 | `reference_material + clarification` | waiting_input |
| 9 | 我刚才让你做的那个现在具体做到哪一步了 | `has_status_query=True` | 返回真实 runtime snapshot |
| 10 | 下面是第四章大纲，请你先看逻辑是否合理，再决定是否要改写 | `reference_material + task_request + constraint`，`request_mode=analyze` | analyze / waiting_input |

---

## 15. 验收条件

### 15.1 通过条件

以下全部满足才可报通过：

1. 新 parser 成为唯一语义真相源
2. 长输入先切块再裁决
3. `telegram_bridge.py` 不再以关键词/白名单为主判定源
4. `semantic_router.py` 已降级为兼容适配层
5. `question_verbalizer.py` 不再承担独立语义判定职责
6. `command_router.py` 消费 graph 而非旧 regex 结果
7. 状态查询回复内容来自 runtime snapshot
8. 至少 8 条样例通过
9. 不回退旧关键词/regex 主链

### 15.2 不得报完成的情况

出现任一项，都只能报"部分完成 / 过渡方案 / 待验证"：

* 只是把关键词表扩充
* 只是 regex 换成更多 regex
* 路径/附件仍自动等于执行任务
* parser 失败后回退旧规则表
* verbalizer 仍自己判短问句主意图
* graph 有了，但 runtime 仍没消费
* 没有真实 E2E 或集成验证

---

## 16. 当前层级、主链接入状态、启用状态

### 当前层级

EgoCore / 语义入口主链 / 架构收口层

### 主链接入状态

尚未生效，当前仍处于 Phase 0 设计锁定阶段。
现有主链旧判定逻辑仍在代码中真实存在。 

### 启用状态

未启用新 parser。
本文件仅作为后续 Phase 1 实现的唯一权威源。

### 真实触发证据

* `telegram_bridge.py` 当前仍使用 `TASK_KEYWORDS / SHORT_PROBES / DISCUSSION_PATTERNS` 等。
* `semantic_router.py` 当前仍以 regex patterns 为核心。
* `question_verbalizer.py` 当前仍以短句模式表和长度阈值做判定。
* `command_router.py` 当前自然语言入口仍依赖旧分类器。

---

## 17. Phase 1 开工条件

满足以下条件即可进入 Phase 1：

1. 本正式稿确认无冲突
2. CEO / OpenClaw 明确以本稿为唯一权威源
3. 实现范围先限定为：
   - 新增 `semantic_parser.py`
   - 改 `telegram_bridge.py`
   - 给 `semantic_router.py` 做兼容适配
4. 不在 Phase 1 同时大改全部模块，避免过宽施工面

---

## 18. 一句话执行指令

**不要再补关键词表；按本正式稿实现统一 `semantic_parse_message()`，并让它成为 EgoCore 自然语言入口的唯一语义真相源。**
