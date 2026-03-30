"""
EgoCore 统一语义解析器

Phase 0 设计合同的唯一权威实现。

唯一语义真相源：semantic_parse_message() -> ParsedIntentGraph

职责边界：
- 只负责理解语义
- 只输出结构化结果
- 不决定执行/完成/状态文本
- 不写 runtime state
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SHORT_STATUS_PATTERNS = {
    "还在吗",
    "还在不",
    "在吗",
    "到哪了",
    "进度呢",
    "怎么样了",
    "好了没",
    "好了吗",
    "完成了吗",
    "处理到哪了",
}

SHORT_CORRECTION_PATTERNS = {
    "你没改啊",
    "没改啊",
    "你没做啊",
    "还是不对",
    "不是这个",
    "不是这个意思",
    "我说的不是这个",
    "没看到改动",
}

WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() -]+[\\/])*[A-Za-z0-9._() -]+")
UNIX_PATH_RE = re.compile(r"(?:/mnt|/home|/tmp|/Users)(?:/[A-Za-z0-9._() -]+)+")

EXPLICIT_FILE_TASK_PATTERNS = (
    (("创建", "新建", "生成", "做", "制作", "写"), ("页面", "网页", "html", "html网页", "html页面", "page", "webpage", "website")),
    (("读取", "读", "查看", "打开", "检查", "看"), tuple()),
    (("修改", "改", "更新", "重写", "修复", "优化", "换"), tuple()),
    (("read", "open", "view", "inspect", "check", "show"), tuple()),
    (("create", "generate", "write", "make", "build"), ("html", "page", "webpage", "website", "file")),
    (("modify", "update", "edit", "fix", "rewrite"), tuple()),
)

READ_ONLY_FILE_TASK_MARKERS = (
    "读取", "读", "查看", "打开", "检查", "看",
    "read", "open", "view", "inspect", "check", "show",
    "完整内容", "全部内容", "全文", "不要截断", "别截断", "继续读取", "读完整",
)


# =============================================================================
# 数据结构（最终版）
# =============================================================================

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
    """语义块"""
    text: str
    kind: str
    confidence: float
    refers_to_previous: bool = False
    target_ref: Optional[str] = None
    request_mode: Optional[str] = None
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind,
            "confidence": self.confidence,
            "refers_to_previous": self.refers_to_previous,
            "target_ref": self.target_ref,
            "request_mode": self.request_mode,
            "priority": self.priority,
        }


@dataclass
class ParsedIntentGraph:
    """
    结构化意图图

    唯一语义解析输出对象。
    """
    segments: List[SemanticSegment] = field(default_factory=list)

    primary_intent: str = "unclear"
    secondary_intents: List[str] = field(default_factory=list)

    has_status_query: bool = False
    has_correction: bool = False
    has_clarification: bool = False
    has_background: bool = False
    requires_clarification: bool = False

    actionable_targets: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)

    parser_source: str = "semantic_parser"  # semantic_parser / heuristic_parser / chat_default
    graph_version: str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "primary_intent": self.primary_intent,
            "secondary_intents": self.secondary_intents,
            "has_status_query": self.has_status_query,
            "has_correction": self.has_correction,
            "has_clarification": self.has_clarification,
            "has_background": self.has_background,
            "requires_clarification": self.requires_clarification,
            "actionable_targets": self.actionable_targets,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "parser_source": self.parser_source,
            "graph_version": self.graph_version,
        }


# =============================================================================
# LLM 调用规范
# =============================================================================

SEGMENTATION_PROMPT = """你是语义解析器。把用户输入拆成多个语义块。

输入：
- 用户文本
- 最近对话（最近 6 轮）
- 运行时状态快照

输出 JSON：
{{
  "segments": [
    {{
      "text": "原文片段",
      "kind": "task_request|status_query|constraint|background|clarification|correction|acceptance_criteria|reference_material|small_talk",
      "confidence": 0.0,
      "refers_to_previous": false,
      "target_ref": null,
      "request_mode": "execute|analyze|design|compare|write|summarize|unknown",
      "priority": 0
    }}
  ]
}}

规则：
1. 每个语义块只能有一个 kind
2. 长消息必须拆成多块
3. 混合输入必须分别识别
4. 状态查询（还在吗/到哪了/怎么了）必须标记为 status_query
5. 纠错/反驳（不是这个意思/我说的不是）必须标记为 correction
6. 路径/附件/材料默认可作为 reference_material
7. 你只负责理解，不负责执行或判断真实状态

用户文本：
{text}

最近对话：
{recent_turns}

运行时状态：
{runtime_snapshot}
"""


# =============================================================================
# Parser 上下文注入规范
# =============================================================================

def build_parser_context(
    recent_turns: List[Dict[str, Any]],
    state: Any,
) -> Dict[str, Any]:
    """
    构建 parser 可用的上下文。

    注入内容：
    - 最近 6 轮对话摘要
    - 当前任务状态
    - 挂起的 artifacts
    """
    # 处理 recent_turns 可能是对象而不是字典的情况
    turns_summary = []
    for t in recent_turns[-6:]:
        if isinstance(t, dict):
            text_val = t.get("text") or t.get("content") or ""
        else:
            # 可能是对象
            text_val = getattr(t, "text", None) or getattr(t, "content", "") or ""
        turns_summary.append({
            "role": t.get("role") if isinstance(t, dict) else getattr(t, "role", "user"),
            "text": str(text_val)[:200] if text_val else "",
        })

    return {
        "recent_turns_summary": turns_summary,
        "runtime_snapshot": {
            "task_status": getattr(state, "task_status", "idle"),
            "active_task_id": getattr(state, "task_id", None),
            "current_goal": getattr(state, "current_goal", None),
            "current_step": getattr(state, "current_step", None),
            "waiting_for_user_input": getattr(state, "waiting_for_user_input", False),
            "last_delivery_type": getattr(state, "last_delivery_type", None),
            "has_pending_artifacts": len(getattr(state, "pending_artifacts", [])) > 0,
        },
        "pending_artifacts": [
            {"filename": a.get("filename") if isinstance(a, dict) else getattr(a, "filename", None)}
            for a in getattr(state, "pending_artifacts", [])[-3:]
        ],
    }


# =============================================================================
# Heuristic Parser（极简兜底）
# =============================================================================

def heuristic_parse(text: str) -> ParsedIntentGraph:
    """
    极简规则兜底，只识别显式硬信号。

    处理：
    - 显式命令（/xxx，但不是路径）
    - 文件路径（/home/..., /mnt/..., /tmp/...）
    - 附件标记（[用户发送了文件:...]）

    不处理：
    - 自然语言语义
    - 执行动词匹配（交给 semantic_parser 或 chat_default）

    强约束：
    1. 不允许逐步演化成第二套关键词真相源
    2. 纯讨论/背景/约束 → chat_default
    """
    # 审计日志：入口
    logger.debug(f"heuristic_parse: input text[:50]={text[:50] if len(text) > 50 else text}")

    segments = []
    normalized = _normalize_short_probe(text)

    if normalized in SHORT_STATUS_PATTERNS:
        logger.info("heuristic_parse: detected short status probe, parser_source=heuristic_parser, primary_intent=status_query")
        segments.append(SemanticSegment(
            text=text,
            kind="status_query",
            confidence=0.95,
        ))
        return ParsedIntentGraph(
            segments=segments,
            primary_intent="status_query",
            has_status_query=True,
            parser_source="heuristic_parser",
        )

    if normalized in SHORT_CORRECTION_PATTERNS:
        logger.info("heuristic_parse: detected short correction, parser_source=heuristic_parser, primary_intent=correction")
        segments.append(SemanticSegment(
            text=text,
            kind="correction",
            confidence=0.95,
        ))
        return ParsedIntentGraph(
            segments=segments,
            primary_intent="correction",
            has_correction=True,
            parser_source="heuristic_parser",
        )

    explicit_paths = _extract_explicit_paths(text)
    explicit_file_task = _extract_explicit_file_task(text, explicit_paths)
    if explicit_file_task is not None:
        logger.info(
            "heuristic_parse: detected explicit file task, parser_source=heuristic_parser, primary_intent=task_request, mode=%s, target=%s",
            explicit_file_task["request_mode"],
            explicit_file_task["target_ref"],
        )
        segment = SemanticSegment(
            text=text,
            kind="task_request",
            request_mode=explicit_file_task["request_mode"],
            target_ref=explicit_file_task["target_ref"],
            confidence=0.96,
        )
        graph = ParsedIntentGraph(
            segments=[segment],
            primary_intent="task_request",
            parser_source="heuristic_parser",
        )
        graph.actionable_targets.append(explicit_file_task["target_ref"])
        if explicit_file_task.get("format_hint"):
            graph.constraints.append(f"format:{explicit_file_task['format_hint']}")
        if explicit_file_task.get("topic_hint"):
            graph.acceptance_criteria.append(f"topic:{explicit_file_task['topic_hint']}")
        return graph

    # 检测路径（显式硬信号）- 支持 Unix 和 Windows 路径
    generic_path = text.startswith("/") and "." in text.split()[0]  # /path/to/file.ext 模式
    has_path = bool(explicit_paths) or generic_path
    # 文件路径检测
    if has_path:
        logger.info(f"heuristic_parse: detected path, parser_source=heuristic_parser, primary_intent=reference_material")
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

    # 显式命令（以 / 开头但不是路径）
    if text.startswith("/") and not any(x in text for x in ["/home/", "/mnt/", "/tmp/"]):
        logger.info(f"heuristic_parse: detected explicit command, parser_source=heuristic_parser, primary_intent=task_request")
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

    # 附件标记 → reference_material
    if "[用户发送了文件:" in text or "[附件:" in text:
        logger.info(f"heuristic_parse: detected attachment marker, parser_source=heuristic_parser, primary_intent=reference_material")
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

    # 默认：chat
    logger.info(f"heuristic_parse: no explicit signal, parser_source=chat_default, primary_intent=chat")
    return ParsedIntentGraph(
        primary_intent="chat",
        parser_source="chat_default",
    )


def _normalize_short_probe(text: str) -> str:
    normalized = re.sub(r"\s+", "", (text or "").strip().lower())
    return normalized.strip("?!？！。,.，")


def _extract_explicit_paths(text: str) -> List[str]:
    paths: List[str] = []
    for pattern in (WINDOWS_PATH_RE, UNIX_PATH_RE):
        for match in pattern.finditer(text or ""):
            candidate = match.group(0).strip().rstrip(".,!?，。！？")
            if candidate not in paths:
                paths.append(candidate)
    return paths


def _extract_explicit_file_task(text: str, paths: List[str]) -> Optional[Dict[str, str]]:
    if not text or not paths:
        return None

    lowered = text.lower()
    request_mode = None
    for verbs, nouns in EXPLICIT_FILE_TASK_PATTERNS:
        has_verb = any(verb in text or verb in lowered for verb in verbs)
        if not has_verb:
            continue
        if nouns and not any(noun in text or noun in lowered for noun in nouns):
            continue
        request_mode = "write" if any(
            marker in text or marker in lowered
            for marker in ("创建", "新建", "生成", "写", "制作", "html", "页面", "网页", "create", "generate", "write", "build", "page", "website")
        ) else "analyze" if any(
            marker in text or marker in lowered
            for marker in READ_ONLY_FILE_TASK_MARKERS
        ) else "execute"
        break

    if request_mode is None:
        return None

    target_ref = paths[0]
    format_hint = _infer_format_hint(text, target_ref)
    topic_hint = _infer_topic_hint(text)
    return {
        "target_ref": target_ref,
        "request_mode": request_mode,
        "format_hint": format_hint or "",
        "topic_hint": topic_hint or "",
    }


def _infer_format_hint(text: str, path: str) -> Optional[str]:
    lowered = (text or "").lower()
    if any(marker in lowered or marker in text for marker in ("html", "页面", "网页", "html网页", "html页面")):
        return "html"
    if path.lower().endswith((".html", ".htm")):
        return "html"
    if path.lower().endswith(".md") or "markdown" in lowered:
        return "markdown"
    return None


def _infer_topic_hint(text: str) -> Optional[str]:
    patterns = (
        r"介绍\s*([A-Za-z][A-Za-z0-9_-]*)",
        r"关于\s*([A-Za-z][A-Za-z0-9_-]*)",
        r"about\s+([A-Za-z][A-Za-z0-9_-]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            topic = match.group(1)
            return "EgoCore" if topic.lower() == "egocore" else topic
    if re.search(r"\begocore\b", text or "", flags=re.IGNORECASE):
        return "EgoCore"
    return None


# =============================================================================
# 主解析函数
# =============================================================================

class SemanticParseError(Exception):
    """语义解析错误"""
    pass


async def semantic_parse_message(
    text: str,
    recent_turns: List[Dict[str, Any]],
    runtime_snapshot: Dict[str, Any],
    llm_client: Any = None,
    timeout: float = 8.0,
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

    性能约束：
    - 超时：8 秒
    - LLM 调用次数：最多 1 次
    - 不重试 LLM
    """
    # 如果没有 LLM client，直接走 heuristic
    if llm_client is None:
        logger.info("semantic_parse: no LLM client, using heuristic_parse")
        return heuristic_parse(text)

    heuristic_graph = heuristic_parse(text)
    if heuristic_graph.parser_source == "heuristic_parser":
        logger.info(
            "semantic_parse: fast heuristic hit, parser_source=%s, primary_intent=%s",
            heuristic_graph.parser_source,
            heuristic_graph.primary_intent,
        )
        return heuristic_graph

    # 构建 prompt
    recent_turns_str = json.dumps(recent_turns[-6:], ensure_ascii=False, indent=2)
    runtime_snapshot_str = json.dumps(runtime_snapshot, ensure_ascii=False, indent=2)

    prompt = SEGMENTATION_PROMPT.format(
        text=text,
        recent_turns=recent_turns_str,
        runtime_snapshot=runtime_snapshot_str,
    )

    try:
        # 调用 LLM（带超时）
        result = await asyncio.wait_for(
            _call_llm(llm_client, prompt),
            timeout=timeout,
        )

        # 解析结果
        graph = _parse_llm_result(result, text)

        if graph.segments:
            # 明确设置：真正走 semantic_parse 且成功
            graph.parser_source = "semantic_parser"
            logger.info(f"semantic_parse: LLM success, parser_source=semantic_parser, primary_intent={graph.primary_intent}")
            return graph
        else:
            # LLM 返回空结果（如 invalid JSON 或 empty segments），回退 heuristic
            graph = heuristic_parse(text)
            # 确保 parser_source 反映实际路径：因 empty/invalid 回退 → heuristic_parser
            logger.info(f"semantic_parse: LLM empty/invalid result, fallback to parser_source={graph.parser_source}")
            return graph

    except asyncio.TimeoutError:
        logger.warning("semantic_parse: LLM timeout, fallback to heuristic")
        graph = heuristic_parse(text)
        logger.info(f"semantic_parse: timeout fallback parser_source={graph.parser_source}")
        return graph
    except Exception as e:
        logger.error(f"semantic_parse: LLM error: {e}")
        graph = heuristic_parse(text)
        logger.info(f"semantic_parse: error fallback parser_source={graph.parser_source}")
        return graph


async def _call_llm(llm_client: Any, prompt: str) -> Dict[str, Any]:
    """
    调用 LLM 并返回 JSON 结果。

    这里需要根据实际的 LLM client 适配。
    """
    result_str = None

    # 获取 LLM 响应的辅助函数
    def extract_content(response) -> Optional[str]:
        """从 LLM 响应中提取文本内容"""
        if response is None:
            return None
        # LLMResponse 对象有 content 属性
        if hasattr(response, "content"):
            return response.content
        # 字典格式
        if isinstance(response, dict):
            return response.get("content") or response.get("text")
        # 字符串
        if isinstance(response, str):
            return response
        return None

    try:
        # 尝试 LLMClient.generate (同步)
        if hasattr(llm_client, "generate"):
            import asyncio
            # 在线程池中运行同步方法
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: llm_client.generate(prompt)
            )
            result_str = extract_content(response)
    except Exception as e:
        logger.debug(f"_call_llm: generate failed: {e}")

    if result_str is None:
        try:
            # 尝试 openai 风格
            if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
                response = await llm_client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                result_str = response.choices[0].message.content
        except Exception as e:
            logger.debug(f"_call_llm: openai style failed: {e}")

    if result_str is None:
        try:
            # 尝试自定义 complete 方法
            if hasattr(llm_client, "complete"):
                result = await llm_client.complete(prompt)
                result_str = extract_content(result)
        except Exception as e:
            logger.debug(f"_call_llm: complete failed: {e}")

    if result_str is None:
        raise SemanticParseError("No valid LLM client interface found")

    # 日志：原始 LLM 输出
    logger.info(f"_call_llm: raw output length={len(result_str)}, first 200 chars: {result_str[:200]}")

    # 尝试解析 JSON
    try:
        # 清理可能的 markdown 代码块
        cleaned = result_str.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 移除第一行和最后一行
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            logger.info(f"_call_llm: cleaned markdown block, new length={len(cleaned)}")

        # 提取第一个完整 JSON 对象（处理 LLM 返回 JSON 后带额外内容的情况）
        cleaned = _extract_first_json(cleaned)
        logger.info(f"_call_llm: extracted JSON object, length={len(cleaned)}")

        parsed = json.loads(cleaned)
        logger.info(f"_call_llm: JSON parsed successfully, segments={len(parsed.get('segments', []))}")
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"_call_llm: JSON decode error: {e}, result[:500]: {result_str[:500]}")
        raise SemanticParseError(f"Invalid JSON response: {e}")


def _extract_first_json(text: str) -> str:
    """
    从文本中提取第一个完整的 JSON 对象。

    处理场景：
    - LLM 返回 JSON 后带有额外的 markdown 表格或说明文字
    - 找到第一个 { 到其匹配的 } 之间的内容

    示例输入：
    {"segments": [...]}
    | 字段 | 说明 |
    |------|------|

    返回：{"segments": [...]}
    """
    # 找到第一个非空白字符是 { 的位置
    start = -1
    for i, char in enumerate(text):
        if char in ' \t\n\r':
            continue
        if char == '{':
            start = i
            break
        else:
            # 第一个非空白字符不是 {，直接返回原字符串让后续解析报错
            return text

    if start == -1:
        return text

    # 使用栈匹配括号，找到 JSON 对象结束位置
    depth = 0
    in_string = False
    escape_next = False
    end = -1

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not in_string:
            in_string = True
            continue

        if char == '"' and in_string:
            in_string = False
            continue

        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break

    if end == -1:
        # 没找到匹配的 }，返回原字符串
        return text

    return text[start:end + 1]


def _parse_llm_result(result: Dict[str, Any], original_text: str) -> ParsedIntentGraph:
    """
    解析 LLM 返回的 JSON 结果。

    注意：此函数不设置 parser_source，由调用方根据调用结果明确设置。
    """
    graph = ParsedIntentGraph()
    # 明确清空 parser_source，强制调用方设置正确值
    graph.parser_source = ""

    segments_data = result.get("segments", [])
    if not segments_data:
        return graph

    for item in segments_data:
        kind = item.get("kind", "small_talk")
        if kind not in SEGMENT_KINDS:
            kind = "small_talk"

        request_mode = item.get("request_mode")
        if request_mode and request_mode not in REQUEST_MODES:
            request_mode = "unknown"

        seg = SemanticSegment(
            text=item.get("text", original_text),
            kind=kind,
            confidence=float(item.get("confidence", 0.5)),
            refers_to_previous=bool(item.get("refers_to_previous", False)),
            target_ref=item.get("target_ref"),
            request_mode=request_mode,
            priority=int(item.get("priority", 0)),
        )
        graph.segments.append(seg)

        # 更新 graph 标志
        if seg.kind == "status_query":
            graph.has_status_query = True
        elif seg.kind == "correction":
            graph.has_correction = True
        elif seg.kind == "clarification":
            graph.has_clarification = True
        elif seg.kind == "background":
            graph.has_background = True
        elif seg.kind == "constraint":
            graph.constraints.append(seg.text)
        elif seg.kind == "acceptance_criteria":
            graph.acceptance_criteria.append(seg.text)
        elif seg.kind == "task_request":
            graph.actionable_targets.append(seg.text)

    # 决定 primary_intent
    graph.primary_intent = _decide_primary_intent(graph)
    graph.secondary_intents = _decide_secondary_intents(graph)
    graph.requires_clarification = _needs_clarification(graph)

    return graph


def _decide_primary_intent(graph: ParsedIntentGraph) -> str:
    """决定主意图"""
    # 优先级：correction > task_request > status_query > clarification > background > small_talk

    if graph.has_correction:
        return "correction"

    for seg in graph.segments:
        if seg.kind == "task_request":
            return "task_request"

    if graph.has_status_query:
        return "status_query"

    if graph.has_clarification:
        return "clarification"

    if graph.has_background:
        return "background"

    # 默认
    if graph.segments:
        return graph.segments[0].kind

    return "chat"


def _decide_secondary_intents(graph: ParsedIntentGraph) -> List[str]:
    """决定次要意图"""
    secondary = []
    seen = {graph.primary_intent}

    for seg in graph.segments:
        if seg.kind not in seen:
            secondary.append(seg.kind)
            seen.add(seg.kind)

    return secondary


def _needs_clarification(graph: ParsedIntentGraph) -> bool:
    """判断是否需要澄清"""
    # 如果有 clarification 块，需要澄清
    if graph.has_clarification:
        return True

    # 如果有 reference_material 但没有明确的 task_request，需要澄清
    has_ref = any(seg.kind == "reference_material" for seg in graph.segments)
    has_task = any(seg.kind == "task_request" for seg in graph.segments)
    if has_ref and not has_task:
        return True

    return False


# =============================================================================
# 安全封装
# =============================================================================

async def safe_semantic_parse(
    text: str,
    recent_turns: List[Dict[str, Any]],
    state: Any,
    llm_client: Any = None,
) -> ParsedIntentGraph:
    """
    安全语义解析入口。

    退路顺序：
    1. semantic_parser
    2. heuristic_parser
    3. chat_default

    禁止：
    - 回退旧 TASK_KEYWORDS
    - 回退旧 regex 分类器
    - 回退短问句模式表作为主路由
    """
    context = build_parser_context(recent_turns, state)
    runtime_snapshot = context["runtime_snapshot"]

    # 日志：输入
    logger.info(f"safe_semantic_parse: input text[:100]={text[:100]}, has_llm={llm_client is not None}")

    try:
        graph = await semantic_parse_message(
            text=text,
            recent_turns=recent_turns,
            runtime_snapshot=runtime_snapshot,
            llm_client=llm_client,
        )

        if graph.segments:
            # 不覆写 parser_source，保持 semantic_parse_message 返回的正确值
            # semantic_parse_message 已经正确设置了 parser_source:
            #   - LLM 成功返回 → "semantic_parser"
            #   - LLM fallback → "heuristic_parser" 或 "chat_default"
            pass  # 统一审计日志在函数末尾
        else:
            # 空结果，回退 heuristic
            graph = heuristic_parse(text)
    except Exception as e:
        logger.error(f"safe_semantic_parse error: {e}")
        graph = heuristic_parse(text)

    # 统一审计日志（所有路径都经过这里）
    request_mode = None
    for seg in graph.segments:
        if seg.request_mode:
            request_mode = seg.request_mode
            break

    logger.info(
        "semantic_parse.audit parser_source=%s primary_intent=%s requires_clarification=%s segments=%d request_mode=%s",
        graph.parser_source,
        graph.primary_intent,
        graph.requires_clarification,
        len(graph.segments),
        request_mode,
    )

    # 验证 parser_source 合法性
    if graph.parser_source not in ("semantic_parser", "heuristic_parser", "chat_default"):
        logger.error(f"Invalid parser_source detected: {graph.parser_source}, resetting to chat_default")
        graph.parser_source = "chat_default"

    return graph


# =============================================================================
# Runtime 消费接口
# =============================================================================

def decide_runtime_action(graph: ParsedIntentGraph, state: Any) -> str:
    """
    Runtime 根据 graph + state 决定动作。

    优先级：
    1. 运行中状态查询
    2. 纠错/反驳
    3. 主任务请求
    4. 澄清
    5. 其他聊天
    """
    # 状态查询优先
    if graph.has_status_query:
        if hasattr(state, "is_busy") and state.is_busy():
            return "return_runtime_status"
        return "chat"

    # 纠错/反驳优先
    if graph.has_correction:
        return "repair_or_reframe"

    # 主任务请求
    if graph.primary_intent == "task_request":
        if graph.requires_clarification:
            return "waiting_input"
        return "execute_task"

    # 澄清
    if graph.has_clarification:
        return "clarify"

    # 参考材料（需要澄清）
    if graph.primary_intent == "reference_material":
        return "waiting_input"

    # 默认聊天
    return "chat"


def build_runtime_status_reply(state: Any) -> str:
    """
    构建状态查询回复。

    内容必须来自 runtime snapshot，不能由 LLM 自由生成。
    """
    # 没有运行中的任务
    if not (hasattr(state, "is_busy") and state.is_busy()):
        return "当前没有运行中的任务。"

    if hasattr(state, "pending_task_conflict") and getattr(state, "pending_task_conflict", None):
        conflict = getattr(state, "pending_task_conflict", None) or {}
        incoming_text = str(conflict.get("incoming_text") or "").strip()
        if incoming_text:
            return (
                "当前有一个待确认的新任务。\n\n"
                f"新任务：{incoming_text[:120]}\n\n"
                "回复“替换”会结束旧任务并开始新任务；回复“追加”会把它排到当前任务后面；回复“取消”会保持当前任务不变。"
            )
        return "当前有一个待确认的新任务。回复“替换 / 追加 / 取消”来决定如何处理。"

    if hasattr(state, "get_run_item_status_summary"):
        summary = state.get_run_item_status_summary()
        completed = list(summary.get("completed") or [])
        active = summary.get("active")
        pending = list(summary.get("pending") or [])
        blocked = list(summary.get("blocked") or [])
        parts = []
        if completed:
            parts.append(f"已完成：{'、'.join(completed[:3])}")
        if active:
            parts.append(f"当前正在处理：{active}")
        if pending:
            parts.append(f"后续还有：{'、'.join(pending[:3])}")
        if blocked:
            parts.append(f"当前卡住：{'、'.join(blocked[:3])}")
        if parts:
            return "\n".join(parts)

    # 有 current_step
    if hasattr(state, "current_step") and state.current_step:
        goal = getattr(state, "current_goal", "任务")
        return f"正在处理：{goal}，当前步骤：{state.current_step}"

    # 只有 current_goal
    if hasattr(state, "current_goal") and state.current_goal:
        return f"正在处理：{state.current_goal}"

    # 默认
    return "正在处理中。"
