"""
OpenEmotion Agent Runtime - Semantic Intent Router

Classifies user messages into semantic intents before processing.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import re

from app.risk_signal import is_high_risk_message

# Phase 2: 统一语义解析器集成
from app.runtime_v2.semantic_parser import ParsedIntentGraph


class SemanticIntent(str, Enum):
    """Semantic intent classification for user messages."""

    CHAT = "chat"                    # Greetings, small talk, status checks
    QUESTION = "question"            # General questions, explanations
    NEW_TASK = "new_task"            # Clear task requests
    CONTINUE_TASK = "continue_task"  # Continue/resume previous task
    COMMAND = "command"              # Explicit commands like /new, /run


@dataclass
class IntentResult:
    """Result of intent classification with diagnostic fields."""

    intent: SemanticIntent
    confidence: float
    original_message: str
    extracted_content: Optional[str] = None
    matched_patterns: List[str] = None
    # T2 Diagnostic fields for message tracing
    matched_task_id: Optional[str] = None
    source_of_context: Optional[str] = None  # 'new_task', 'continue_task', 'chat', 'question', 'command'

    def __post_init__(self):
        if self.matched_patterns is None:
            self.matched_patterns = []


class SemanticRouter:
    """
    Semantic intent router for message classification.

    Classifies messages into 5 categories:
    - chat: Greetings, small talk
    - question: General questions
    - new_task: Task requests
    - continue_task: Continue/resume requests
    - command: Explicit commands
    """

    # Chat patterns (greetings, small talk)
    CHAT_PATTERNS = [
        r"^(你好|您好|hi|hello|hey|嗨|早上好|晚上好|下午好)[？?]?$",  # Greetings with optional question mark
        r"^(在吗|在不在|你好吗|怎么样)[？?]?$",
        r"^(好的|ok|明白|收到|谢谢|感谢)$",
        r"^(你还在吗|怎么样了现在)[？?]?$",
        # v2.1: Capability confirmation patterns (能力确认句)
        r"^(你现在|现在|目前).*?(能|可以|会|是否).*?[？?]?$",
        r"^(你.*?能力|你能|你可以|你会|你能做)[？?]?$",
        r"(帮我写代码|帮我编程|帮我开发)[？?]?$",
        r"^(你是谁|你是什么|介绍一下你自己)[？?]?$",
        r"^(你能做什么|你的能力|你会什么)[？?]?$",
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r"^(为什么|为何|怎么回事|什么原因)",
        r"(是什么意思|是什么|怎么理解)",
        r"^(如何|怎么|怎样)",
        r"[？?]$",  # Ends with question mark (Chinese or ASCII)
        r"^(解释|说明|解释一下)",
    ]

    # New task patterns
    NEW_TASK_PATTERNS = [
        r"^(帮我|请帮我|帮我做|帮我完成|帮我检查|帮我分析)",
        r"^(读取|阅读|查看|检查|分析|整理|生成|创建|写|实现)",
        r"^(任务|task)",
        r"(并总结|并分析|并检查|并生成)",
        r"^(做一个|做一个分析|做一个检查)",
        r"^(查询|获取|列出|展示|显示)",
        r"^(告诉我|说明一下|介绍一下)",
        r"(什么问题|什么核心问题|有哪些问题)",
        r"(当前的|现在的|目前的).*(时间|状态|进度)",
    ]

    # Continue task patterns
    CONTINUE_PATTERNS = [
        r"^(继续|接着做|接着|继续做|继续执行)",
        r"^(还有呢|还有什么|接下来)",
        r"^(上个任务|上一个任务|刚才的任务|之前的任务)",
        r"(怎么样了|进展如何|完成了没)",
        r"^(恢复|resume)",
        r"^(做完它|完成它|继续完成)",
    ]

    # Command patterns
    COMMAND_PATTERN = r"^/[a-zA-Z_]+"

    def __init__(self):
        """Initialize semantic router."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._chat_re = [re.compile(p, re.IGNORECASE) for p in self.CHAT_PATTERNS]
        self._question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self._new_task_re = [re.compile(p, re.IGNORECASE) for p in self.NEW_TASK_PATTERNS]
        self._continue_re = [re.compile(p, re.IGNORECASE) for p in self.CONTINUE_PATTERNS]
        self._command_re = re.compile(self.COMMAND_PATTERN)

    def _is_short_question(self, message: str) -> bool:
        """
        检测是否为短问句（P1-C 新增）

        短问句应优先归类为 CHAT intent，避免进入 question 链路的过度解释模式。

        Args:
            message: 用户消息

        Returns:
            True 如果是短问句
        """
        message_clean = message.strip().rstrip("？?")

        # 长度 <=5 且包含疑问词
        if len(message_clean) <= 5:
            short_question_words = [
                "什么", "为啥", "为什么", "怎么", "啊", "嗯", "哦", "啥",
            ]
            if any(word in message_clean for word in short_question_words):
                return True

        # 特定短模式
        short_patterns = [
            r"^什么[？?]?$",
            r"^为啥[？?]?$",
            r"^为什么[？?]?$",
            r"^怎么[？?]?$",
            r"^啊[？?]?$",
            r"^嗯[？?]?$",
            r"^哦[？?]?$",
            r"^啥意思[？?]?$",
            r"^什么意思[？?]?$",
            r"^你说什么[？?]?$",
            r"^再说一遍[？?]?$",
        ]

        for pattern in short_patterns:
            if re.search(pattern, message_clean):
                return True

        return False

    def _check_meta_intent(self, message_lower: str) -> Optional[IntentResult]:
        """
        P4-C: Pre-classification guard for high-value meta messages.

        These 3 types should NOT go to task execution:
        1. Preference/reply style constraints
        2. Correction/refutation
        3. Clarification about current conversation

        Returns:
            IntentResult if matched, None otherwise
        """
        # 1. 偏好/回复方式约束 patterns
        preference_patterns = [
            "记住", "偏好", "喜欢", "给我回复", "之后给我", "回复时",
            "先给最小", "别铺太大", "尽量短", "短一点", "简洁",
            "我的偏好是", "我喜欢", "以后", "之后"
        ]

        # 2. 纠正/反驳 patterns
        correction_patterns = [
            "不对", "不是", "你理解", "我不是说", "我的意思是",
            "错了", "重新", "改为", "换", "改成", "不是这个",
            "不是说这个", "不是指", "不是问"
        ]

        # 3. 澄清/追问 patterns
        clarification_patterns = [
            "你说的是", "指的是", "哪部分", "哪个", "什么项目",
            "你的项目", "我的项目", "问的是", "我是说",
            "你的执行", "仓库是", "你指的是"
        ]

        # Check each category
        for pattern in preference_patterns:
            if pattern in message_lower:
                return IntentResult(
                    intent=SemanticIntent.CHAT,
                    confidence=0.95,
                    original_message=message_lower,
                    matched_patterns=["meta_preference"]
                )

        for pattern in correction_patterns:
            if pattern in message_lower:
                return IntentResult(
                    intent=SemanticIntent.CHAT,
                    confidence=0.95,
                    original_message=message_lower,
                    matched_patterns=["meta_correction"]
                )

        for pattern in clarification_patterns:
            if pattern in message_lower:
                return IntentResult(
                    intent=SemanticIntent.CHAT,
                    confidence=0.95,
                    original_message=message_lower,
                    matched_patterns=["meta_clarification"]
                )

        return None

    def classify(self, message: str) -> IntentResult:
        """
        Classify a message into semantic intent.

        Args:
            message: User message text

        Returns:
            IntentResult with classification details
        """
        message = message.strip()
        original_message = message
        message_lower = message.lower()

        # P4-C: Pre-classification guard for high-value meta messages
        # These should NOT go to task execution
        meta_result = self._check_meta_intent(message_lower)
        if meta_result:
            return meta_result

        # 1. Check for explicit commands first (highest priority)
        if self._command_re.match(message):
            return IntentResult(
                intent=SemanticIntent.COMMAND,
                confidence=1.0,
                original_message=original_message,
                extracted_content=message.split()[0],
                matched_patterns=["command"]
            )

        # 2. Check for chat patterns
        for pattern in self._chat_re:
            if pattern.search(message_lower):
                return IntentResult(
                    intent=SemanticIntent.CHAT,
                    confidence=0.9,
                    original_message=original_message,
                    matched_patterns=[pattern.pattern]
                )

        # 3. Check for continue patterns
        for pattern in self._continue_re:
            if pattern.search(message_lower):
                return IntentResult(
                    intent=SemanticIntent.CONTINUE_TASK,
                    confidence=0.9,
                    original_message=original_message,
                    matched_patterns=[pattern.pattern]
                )

        # 4. Check for new task patterns
        for pattern in self._new_task_re:
            if pattern.search(message_lower):
                return IntentResult(
                    intent=SemanticIntent.NEW_TASK,
                    confidence=0.85,
                    original_message=original_message,
                    extracted_content=original_message,
                    matched_patterns=[pattern.pattern]
                )

        # P1-C: 短问句优先归类为 CHAT，避免进入 question 链路的过度解释
        if self._is_short_question(message):
            return IntentResult(
                intent=SemanticIntent.CHAT,
                confidence=0.85,
                original_message=original_message,
                matched_patterns=["short_question"]
            )

        # 5. Check for question patterns
        for pattern in self._question_re:
            if pattern.search(message_lower):
                return IntentResult(
                    intent=SemanticIntent.QUESTION,
                    confidence=0.8,
                    original_message=original_message,
                    extracted_content=original_message,
                    matched_patterns=[pattern.pattern]
                )

        # 6. Default: treat short messages as chat, longer as potential task
        if len(message) < 10:
            return IntentResult(
                intent=SemanticIntent.CHAT,
                confidence=0.5,
                original_message=original_message,
                matched_patterns=["short_message_default"]
            )

        # Longer message without clear intent - could be a task request
        return IntentResult(
            intent=SemanticIntent.NEW_TASK,
            confidence=0.6,
            original_message=original_message,
            extracted_content=original_message,
            matched_patterns=["long_message_default"]
        )

    def is_high_risk(self, message: str) -> bool:
        """
        Check if message contains high-risk operations.

        Args:
            message: User message text

        Returns:
            True if message requires confirmation
        """
        return is_high_risk_message(message)

    def extract_task_content(self, message: str) -> Optional[str]:
        """
        Extract task content from a message.

        Args:
            message: User message text

        Returns:
            Extracted task content or None
        """
        result = self.classify(message)

        if result.intent == SemanticIntent.NEW_TASK:
            # Remove common prefixes
            content = message
            prefixes = ["帮我", "请帮我", "帮我做", "帮我完成", "帮我检查", "帮我分析", "请"]
            for prefix in prefixes:
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            return content if content else message

        return None


# Global router instance
_router: Optional[SemanticRouter] = None


def get_semantic_router() -> SemanticRouter:
    """Get or create global semantic router instance."""
    global _router
    if _router is None:
        _router = SemanticRouter()
    return _router


def classify_message(message: str) -> IntentResult:
    """
    Classify a message into semantic intent.

    Convenience function using global router.

    Args:
        message: User message text

    Returns:
        IntentResult with classification details
    """
    return get_semantic_router().classify(message)


# =============================================================================
# Phase 2: 统一语义解析器集成
# =============================================================================

async def classify_semantic(
    message: str,
    recent_turns: list = None,
    runtime_snapshot: dict = None,
    llm_client = None,
) -> IntentResult:
    """
    使用统一语义解析器分类消息。

    这是新的权威入口，取代旧的 regex 分类。

    Args:
        message: 用户消息
        recent_turns: 最近对话上下文
        runtime_snapshot: 运行时状态快照
        llm_client: LLM 调用器

    Returns:
        IntentResult with classification details
    """
    from app.runtime_v2.semantic_parser import (
        safe_semantic_parse,
        decide_runtime_action,
        ParsedIntentGraph,
    )

    # 调用统一语义解析器
    graph = await safe_semantic_parse(
        text=message,
        recent_turns=recent_turns or [],
        state=None,  # 需要 state 对象，这里用 None 会回退到 heuristic
        llm_client=llm_client,
    )

    # 将 ParsedIntentGraph 转换为 IntentResult
    return _graph_to_intent_result(graph, message)


def _graph_to_intent_result(graph: ParsedIntentGraph, message: str) -> IntentResult:
    """将 ParsedIntentGraph 转换为 IntentResult（兼容旧接口）。"""

    # 映射 primary_intent 到 SemanticIntent
    intent_mapping = {
        "task_request": SemanticIntent.NEW_TASK,
        "status_query": SemanticIntent.QUESTION,
        "chat": SemanticIntent.CHAT,
        "small_talk": SemanticIntent.CHAT,
        "reference_material": SemanticIntent.NEW_TASK,
        "correction": SemanticIntent.CHAT,
        "clarification": SemanticIntent.QUESTION,
        "background": SemanticIntent.CHAT,
    }

    primary = graph.primary_intent
    semantic_intent = intent_mapping.get(primary, SemanticIntent.CHAT)

    # 如果有 correction，优先作为 CHAT
    if graph.has_correction:
        semantic_intent = SemanticIntent.CHAT

    # 提取任务内容
    extracted_content = None
    if graph.actionable_targets:
        extracted_content = graph.actionable_targets[0]
    elif graph.segments:
        for seg in graph.segments:
            if seg.kind == "task_request":
                extracted_content = seg.text
                break

    return IntentResult(
        intent=semantic_intent,
        confidence=max([s.confidence for s in graph.segments]) if graph.segments else 0.5,
        original_message=message,
        extracted_content=extracted_content,
        matched_patterns=[f"parser:{graph.parser_source}"],
        source_of_context=primary,
    )


def classify_message_sync(message: str) -> IntentResult:
    """
    同步版本的语义分类（使用 heuristic parser）。

    用于无法使用 async 的场景。
    """
    from app.runtime_v2.semantic_parser import heuristic_parse

    graph = heuristic_parse(message)
    return _graph_to_intent_result(graph, message)
