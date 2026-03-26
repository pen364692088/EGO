from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional

from .progress_events import ProgressEvent, is_terminal_event
from .runtime_reply import RuntimeV2TurnResult
from .state import RuntimeV2State

# Phase 0 设计合同：统一语义解析器
from .semantic_parser import (
    ParsedIntentGraph,
    SemanticSegment,
    heuristic_parse,
    decide_runtime_action,
    build_runtime_status_reply,
    SEGMENT_KINDS,
    REQUEST_MODES,
)


# 文件类型推断模式（仅用于文件-only 场景的弱信号推断）
FILE_TYPE_PATTERNS = {
    "task": ["任务单", "todo", "task", "plan", "fix", "patch", "执行", ".txt"],
    "spec": ["SOUL", "AGENTS", "TOOLS", "BOOTSTRAP", "README", "POLICY", "规范", ".md"],
    "log": ["log", "trace", "error", "report", "日志", ".log"],
}


@dataclass
class IntentInference:
    """
    WS-3: 统一意图推断结果对象
    
    分层推断信号强度：
    1. 最近用户上下文 (最强)
    2. capsule / artifact type
    3. 文件名模式 (最弱)
    """
    inferred_action: Optional[str] = None  # execute/compare/analyze
    confidence: str = "low"  # high/medium/low
    primary_target: Optional[Dict[str, Any]] = None  # 主目标 artifact
    secondary_option: Optional[str] = None  # 备选动作
    reason: Optional[str] = None  # 推断理由


def extract_filename_from_text(text: str) -> Optional[str]:
    """从文本中提取文件名"""
    patterns = [
        r"\[附件:\s*([^\]]+)\]",
        r"\[用户发送了文件:\s*([^\]]+)\]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def infer_intent_from_filename(filename: str) -> List[str]:
    """
    低成本推断：只用文件名（第三级信号 - 最弱）
    
    WS-3: 文件名只能当弱信号，不能当主判断
    """
    if not filename:
        return []
    candidates = []
    filename_lower = filename.lower()
    for file_type, patterns in FILE_TYPE_PATTERNS.items():
        if any(p.lower() in filename_lower for p in patterns):
            candidates.append(file_type)
    return candidates


def infer_intent(
    text: str,
    state: RuntimeV2State,
    has_attachment: bool = False,
) -> IntentInference:
    """
    基于 artifact 类型的意图推断（文件-only 场景）。

    注意：自然语言语义解析已由 semantic_parser 完成，
    此函数仅用于文件-only 场景的弱信号推断。

    关键约束：绝不允许触发 raw/chunk read
    """
    result = IntentInference()

    # 基于 artifact type 推断（来自 state._classify_artifact_type）
    if state.last_uploaded_artifact:
        filename = state.last_uploaded_artifact.get("filename")
        artifact_type = state._classify_artifact_type(filename)
        
        if artifact_type == "task":
            result.inferred_action = "execute"
            result.confidence = "medium"
            result.primary_target = state.last_uploaded_artifact
            result.secondary_option = "analyze"
            result.reason = "检测到任务单类文件"
            return result
        
        elif artifact_type == "spec":
            result.inferred_action = "analyze"
            result.confidence = "medium"
            result.primary_target = state.last_uploaded_artifact
            result.secondary_option = "constraint"
            result.reason = "检测到规范类文件"
            return result
    
    # 第三级信号：文件名模式 (最弱)
    if has_attachment:
        filename = extract_filename_from_text(text)
        if filename:
            file_types = infer_intent_from_filename(filename)
            if file_types:
                file_type = file_types[0]
                result.primary_target = {"filename": filename, "source": "attachment"}
                
                if file_type == "task":
                    result.inferred_action = "execute"
                    result.confidence = "low"
                    result.secondary_option = "analyze"
                    result.reason = "文件名暗示任务单"
                elif file_type == "spec":
                    result.inferred_action = "analyze"
                    result.confidence = "low"
                    result.secondary_option = "constraint"
                    result.reason = "文件名暗示规范文件"
                else:
                    result.inferred_action = "analyze"
                    result.confidence = "low"
                    result.reason = "文件类型未知"
                
                return result
    
    # 默认：低置信，需要用户澄清
    result.inferred_action = None
    result.confidence = "low"
    result.reason = "无法推断意图"
    return result


def build_suggestion_response_from_intent(intent: IntentInference, state: RuntimeV2State) -> str:
    """
    WS-3: 基于意图推断生成建议式确认
    
    回复规则：
    - 高置信：直接给主建议 + 备选
    - 中置信：给主建议，但语气更保守
    - 低置信：中性追问
    """
    action = intent.inferred_action
    confidence = intent.confidence
    target = intent.primary_target
    secondary = intent.secondary_option
    
    # 多文件 bundle 场景
    if state.pending_artifacts and len(state.pending_artifacts) >= 2:
        task_artifacts = state.get_task_artifacts()
        spec_artifacts = state.get_spec_artifacts()
        
        # 规范 + 任务单
        if task_artifacts and spec_artifacts:
            task_file = task_artifacts[-1].get("filename", "任务单")
            spec_count = len(spec_artifacts)
            if confidence == "high":
                return f"我可以先按「{task_file}」执行，并把 {spec_count} 份规范当作约束。要我这样走吗？"
            else:
                return f"我看有 {spec_count} 份规范和 1 份任务单「{task_file}」。要我按任务单执行，并把规范当约束？还是先对比规范？"
        
        # 多份规范
        if len(spec_artifacts) >= 2:
            if confidence == "high":
                return f"现在有 {len(spec_artifacts)} 份规范文件，我可以先做职责边界对比。要我现在开始吗？"
            else:
                return f"我看到 {len(spec_artifacts)} 份规范文件。你要我对比它们的职责边界，还是审查某一份？"
    
    # 单文件场景
    if target:
        filename = target.get("filename", "文件")
        
        if action == "execute":
            if confidence == "high":
                return f"我先按「{filename}」执行。要我开始吗？"
            elif confidence == "medium":
                return f"我看这更像一份任务单「{filename}」。我要先按「执行这份任务」走吗？"
            else:
                if secondary == "analyze":
                    return f"收到「{filename}」。你要我执行它，还是先审查内容？"
                return f"收到「{filename}」。你要我做什么？"
        
        elif action == "analyze":
            if confidence == "high":
                return f"我先审查「{filename}」。要我开始吗？"
            elif confidence == "medium":
                if secondary == "constraint":
                    return f"这更像规范文件「{filename}」。你是要我审查它，还是把它当作后续执行约束？"
                return f"我看这是「{filename}」。你要我先审查它吗？"
            else:
                return f"收到「{filename}」。你要我审查它，还是把它当作执行约束？"
        
        elif action == "compare":
            if confidence == "high":
                return f"我开始对比。要我现在开始吗？"
            else:
                return f"你想要对比哪些文件？"
    
    # fallback
    return "收到文件。请告诉我你想做什么（执行/审查/对比）？"


# 保留旧函数兼容性
def build_suggestion_response(filename: str, file_type: str, action: Optional[str] = None) -> str:
    """兼容旧接口"""
    intent = IntentInference(
        inferred_action=action,
        confidence="medium" if file_type != "unknown" else "low",
        primary_target={"filename": filename},
        secondary_option="analyze" if file_type == "task" else "constraint",
    )
    state = RuntimeV2State(session_id="compat")
    return build_suggestion_response_from_intent(intent, state)


@dataclass
class TelegramIngressDecision:
    looks_like_task: bool
    is_short_probe: bool
    is_challenge_turn: bool
    absorb_as_busy_notice: bool
    remember_challenge_turn: bool
    has_attachment: bool = False
    is_file_only: bool = False  # 只有文件，没有明确任务
    # 意图推断结果（闭环1）
    inferred_action: Optional[str] = None  # 猜用户要执行/对比/审查
    inferred_file_type: Optional[str] = None  # 猜文件类型 task/spec/log
    inferred_filename: Optional[str] = None  # 提取的文件名
    # 闭环2：对建议式确认的肯定回复
    is_confirm_execution: bool = False  # 对建议的肯定，不发 ack
    ack_text: Optional[str] = None
    busy_notice_text: Optional[str] = None
    requested_output: Optional[Dict[str, Any]] = None
    # Phase 0：统一语义解析结果
    _parsed_intent_graph: Optional[ParsedIntentGraph] = None
    _runtime_action: Optional[str] = None


@dataclass
class TelegramPreRuntimeAction:
    should_return_early: bool = False
    busy_notice_text: Optional[str] = None
    ack_text: Optional[str] = None
    remember_challenge_turn: bool = False
    force_waiting_input: bool = False  # 强制 waiting_input
    waiting_input_text: Optional[str] = None
    direct_reply_text: Optional[str] = None


@dataclass
class TelegramDeliveryAction:
    should_send: bool
    text: str = ""


class RuntimeV2TelegramBridge:
    AMBIGUOUS_PRESENCE_PROBES = {"在吗", "还在吗", "还在不", "在不在"}
    WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() -]+[\\/])*[A-Za-z0-9._() -]+")
    UNIX_PATH_RE = re.compile(r"(?:/mnt|/home|/tmp|/Users)(?:/[A-Za-z0-9._() -]+)+")

    def _extract_requested_output(self, text: str) -> Optional[Dict[str, Any]]:
        raw_path = self._extract_first_path(text)
        if not raw_path:
            return None

        lowered = (text or "").lower()
        has_task_signal = any(token in text or token in lowered for token in (
            "创建", "新建", "生成", "写", "制作", "做", "修改", "改", "更新", "重写", "修复", "优化", "换",
            "create", "generate", "write", "make", "build", "modify", "update", "edit", "rewrite", "fix",
        ))
        has_page_signal = any(token in text or token in lowered for token in (
            "页面", "网页", "html", "html网页", "html页面", "page", "webpage", "website",
        ))
        if not has_task_signal and not has_page_signal:
            return None

        output_format = self._infer_output_format(text, raw_path)
        is_directory = self._looks_like_directory(raw_path)
        topic = self._infer_topic(text)
        suggested_filename = None
        effective_path = raw_path
        if is_directory:
            suggested_filename = self._suggest_filename(topic, output_format or "html")
            effective_path = self._join_path(raw_path, suggested_filename)

        return {
            "kind": "html_page" if output_format == "html" else "file",
            "format": output_format,
            "target_path": raw_path,
            "target_is_directory": is_directory,
            "suggested_filename": suggested_filename,
            "effective_path": effective_path,
            "topic": topic,
            "sufficient": bool(effective_path and output_format),
        }

    def _extract_first_path(self, text: str) -> Optional[str]:
        for pattern in (self.WINDOWS_PATH_RE, self.UNIX_PATH_RE):
            match = pattern.search(text or "")
            if match:
                return match.group(0).rstrip(".,!?，。！？")
        return None

    def _infer_output_format(self, text: str, path: str) -> Optional[str]:
        lowered = (text or "").lower()
        if any(token in text or token in lowered for token in ("html", "页面", "网页", "html网页", "html页面")):
            return "html"
        if path.lower().endswith((".html", ".htm")):
            return "html"
        if path.lower().endswith(".md") or "markdown" in lowered:
            return "markdown"
        return None

    def _infer_topic(self, text: str) -> Optional[str]:
        for pattern in (r"介绍\s*([A-Za-z][A-Za-z0-9_-]*)", r"关于\s*([A-Za-z][A-Za-z0-9_-]*)", r"about\s+([A-Za-z][A-Za-z0-9_-]*)"):
            match = re.search(pattern, text or "", flags=re.IGNORECASE)
            if match:
                topic = match.group(1)
                return "EgoCore" if topic.lower() == "egocore" else topic
        if re.search(r"\begocore\b", text or "", flags=re.IGNORECASE):
            return "EgoCore"
        return None

    def _looks_like_directory(self, path: str) -> bool:
        lowered = path.lower()
        if lowered.endswith(("\\", "/")):
            return True
        return "." not in PureWindowsPath(path).name and "." not in PurePosixPath(path).name

    def _suggest_filename(self, topic: Optional[str], output_format: str) -> str:
        if topic and topic.lower() == "egocore":
            stem = "egocore_intro"
        elif topic:
            stem = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_") or "page"
        else:
            stem = "page"
        suffix = ".html" if output_format == "html" else ".md"
        return f"{stem}{suffix}"

    def _join_path(self, path: str, filename: str) -> str:
        if re.match(r"^[A-Za-z]:[\\/]", path or ""):
            return str(PureWindowsPath(path) / filename)
        return str(PurePosixPath(path) / filename)

    def _normalize_ambiguous_probe(
        self,
        text: str,
        graph: ParsedIntentGraph,
        state: RuntimeV2State,
    ) -> ParsedIntentGraph:
        normalized = re.sub(r"\s+", "", (text or "").strip().lower()).strip("?!？！。,.，")
        if normalized not in self.AMBIGUOUS_PRESENCE_PROBES:
            return graph
        if hasattr(state, "is_busy") and state.is_busy():
            return graph

        # 空闲态下，这类短句更接近存在性问候，不应硬判成 status_query。
        graph.has_status_query = False
        graph.primary_intent = "chat"
        graph.secondary_intents = []
        graph.requires_clarification = False
        if graph.segments:
            graph.segments[0].kind = "small_talk"
            graph.segments[0].request_mode = None
        graph.parser_source = "heuristic_parser"
        return graph

    def build_ingress_context(
        self,
        decision: TelegramIngressDecision,
        state: RuntimeV2State,
    ) -> Dict[str, Any]:
        graph = decision._parsed_intent_graph
        request_mode = None
        if graph is not None:
            for seg in graph.segments:
                if seg.request_mode:
                    request_mode = seg.request_mode
                    break
        target_action = request_mode or decision.inferred_action
        resolved_target = state.resolve_target(target_action) if target_action in {"execute", "compare", "analyze"} else None
        if resolved_target is None and decision.requested_output:
            resolved_target = {
                "path": decision.requested_output.get("effective_path"),
                "source": "explicit_output_request",
                "format": decision.requested_output.get("format"),
            }
        return {
            "parser_source": graph.parser_source if graph else "chat_default",
            "primary_intent": graph.primary_intent if graph else "chat",
            "secondary_intents": graph.secondary_intents if graph else [],
            "runtime_action": decision._runtime_action,
            "request_mode": request_mode,
            "requires_clarification": graph.requires_clarification if graph else False,
            "has_status_query": graph.has_status_query if graph else False,
            "has_correction": graph.has_correction if graph else False,
            "actionable_targets": graph.actionable_targets if graph else [],
            "constraints": graph.constraints if graph else [],
            "acceptance_criteria": graph.acceptance_criteria if graph else [],
            "pending_artifacts_count": len(state.pending_artifacts),
            "last_uploaded_artifact": state.last_uploaded_artifact,
            "resolved_target": resolved_target,
            "requested_output": decision.requested_output,
        }

    # =========================================================================
    # Phase 0 设计合同：统一语义解析器（新主链）
    # =========================================================================
    
    async def inspect_ingress_semantic(
        self,
        text: str,
        state: RuntimeV2State,
        llm_client: Any = None,
    ) -> "TelegramIngressDecision":
        """
        新版语义入口（async）：消费 ParsedIntentGraph。
        
        这是唯一权威语义判定入口。
        旧的关键词/regex 判定已被降级为 fallback。
        
        职责：
        - 调用统一语义解析器
        - 根据 graph 填充 TelegramIngressDecision
        - 不再使用关键词表作为主判定源
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 直接走程序化解析，避免前置 parser LLM 与主决策 LLM 串行。
        # 复杂语义留给主决策 LLM 一次性消费 ingress_context 处理。
        graph = self._normalize_ambiguous_probe(text, heuristic_parse(text), state)
        
        # ================================================================
        # 审计日志：打印关键决策信息
        # ================================================================
        logger.info(
            f"SEMANTIC_AUDIT: text[:50]={text[:50]!r} "
            f"parser_source={graph.parser_source} "
            f"primary_intent={graph.primary_intent} "
            f"requires_clarification={graph.requires_clarification} "
            f"has_status_query={graph.has_status_query} "
            f"has_correction={graph.has_correction} "
            f"segments={len(graph.segments)}"
        )

        requested_output = self._extract_requested_output(text)
        
        # 根据 graph 决定 runtime 动作
        runtime_action = decide_runtime_action(graph, state)
        
        logger.info(f"SEMANTIC_AUDIT: runtime_action={runtime_action}")
        
        # 转换为 TelegramIngressDecision
        looks_like_task = (
            graph.primary_intent == "task_request" or
            any(seg.kind == "task_request" for seg in graph.segments)
        )
        
        has_attachment = "[用户发送了文件:" in text or "[附件:" in text
        
        # 文件-only：有附件但没有明确任务请求
        is_file_only = has_attachment and not looks_like_task
        
        # 状态查询
        is_status_query = graph.has_status_query
        
        # 纠错/挑战
        is_challenge_turn = graph.has_correction
        
        # 从 graph 提取 inferred_action
        inferred_action = None
        for seg in graph.segments:
            if seg.kind == "task_request" and seg.request_mode:
                inferred_action = seg.request_mode
                break
        
        # 提取目标
        inferred_filename = None
        for seg in graph.segments:
            if seg.kind == "reference_material" and seg.target_ref:
                inferred_filename = seg.target_ref
                break
        
        # 确认执行：检查是否有 pending_artifacts + task_request
        is_confirm_execution = (
            looks_like_task and
            hasattr(state, "pending_artifacts") and
            len(state.pending_artifacts) > 0
        )
        
        return TelegramIngressDecision(
            looks_like_task=looks_like_task,
            is_short_probe=is_status_query,  # 状态查询视为短探针
            is_challenge_turn=is_challenge_turn,
            absorb_as_busy_notice=False,  # 不再发送 generic busy notice
            remember_challenge_turn=is_challenge_turn,
            has_attachment=has_attachment,
            is_file_only=is_file_only,
            inferred_action=inferred_action,
            inferred_file_type=None,  # TODO: 从 graph 提取
            inferred_filename=inferred_filename,
            is_confirm_execution=is_confirm_execution,
            ack_text=None,  # 不再发送 generic ACK
            busy_notice_text=None,
            requested_output=requested_output,
            _parsed_intent_graph=graph,  # 附加 graph 供后续使用
            _runtime_action=runtime_action,
        )

    # =========================================================================
    # 旧版同步方法（兼容层，将逐步废弃）
    # =========================================================================
    
    def inspect_ingress(self, text: str, state: RuntimeV2State) -> "TelegramIngressDecision":
        """
        旧版同步入口（兼容层）。
        
        警告：此方法保留是为了兼容现有调用链。
        新代码应使用 inspect_ingress_semantic()。
        
        此方法不再使用关键词表作为主判定源。
        当无法使用语义解析器时，会回退到 heuristic parser。
        """
        graph = self._normalize_ambiguous_probe(text, heuristic_parse(text), state)
        requested_output = self._extract_requested_output(text)
        runtime_action = decide_runtime_action(graph, state)

        looks_like_task = (
            graph.primary_intent == "task_request" or
            any(seg.kind == "task_request" for seg in graph.segments)
        )

        has_attachment = "[用户发送了文件:" in text or "[附件:" in text
        is_file_only = has_attachment and not looks_like_task
        is_status_query = graph.has_status_query
        is_challenge_turn = graph.has_correction

        inferred_action = None
        for seg in graph.segments:
            if seg.kind == "task_request" and seg.request_mode:
                inferred_action = seg.request_mode
                break

        is_confirm_execution = (
            looks_like_task and
            hasattr(state, "pending_artifacts") and
            len(state.pending_artifacts) > 0
        )

        return TelegramIngressDecision(
            looks_like_task=looks_like_task,
            is_short_probe=is_status_query,
            is_challenge_turn=is_challenge_turn,
            absorb_as_busy_notice=False,
            remember_challenge_turn=is_challenge_turn,
            has_attachment=has_attachment,
            is_file_only=is_file_only,
            inferred_action=inferred_action,
            inferred_file_type=None,
            inferred_filename=None,
            is_confirm_execution=is_confirm_execution,
            ack_text=None,
            busy_notice_text=None,
            requested_output=requested_output,
            _parsed_intent_graph=graph,
            _runtime_action=runtime_action,
        )

    def plan_pre_runtime(self, decision: TelegramIngressDecision, state: RuntimeV2State) -> TelegramPreRuntimeAction:
        import logging
        logger = logging.getLogger(__name__)
        
        # 审计日志
        runtime_action = getattr(decision, "_runtime_action", None)
        logger.info(
            f"SEMANTIC_AUDIT: plan_pre_runtime "
            f"runtime_action={runtime_action} "
            f"looks_like_task={decision.looks_like_task} "
            f"is_file_only={decision.is_file_only}"
        )
        
        # 文件-only：强制 waiting_input，不进入 runtime 决策
        if decision.is_file_only:
            # WS-3: 使用分层意图推断
            intent = infer_intent(
                text="",  # 文件-only 场景，用户文本中没有动作
                state=state,
                has_attachment=True,
            )
            
            # WS-3: 基于意图推断生成建议式确认
            suggestion_text = build_suggestion_response_from_intent(intent, state)
            
            # 写入状态
            if intent.inferred_action:
                state.last_inferred_action = intent.inferred_action
            if intent.primary_target:
                target_filename = intent.primary_target.get("filename")
                if target_filename:
                    state.last_inferred_target = target_filename
            
            # 只发一条建议式确认，不双发
            return TelegramPreRuntimeAction(
                should_return_early=True,
                force_waiting_input=True,
                waiting_input_text=suggestion_text,
                ack_text=None,  # 不再单独发 ack
            )

        if runtime_action == "return_runtime_status":
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text=build_runtime_status_reply(state),
                remember_challenge_turn=decision.remember_challenge_turn,
            )
        
        return TelegramPreRuntimeAction(
            should_return_early=decision.absorb_as_busy_notice,
            busy_notice_text=decision.busy_notice_text,
            ack_text=decision.ack_text,
            remember_challenge_turn=decision.remember_challenge_turn,
        )

    def plan_delivery(self, result: RuntimeV2TurnResult, state: RuntimeV2State, is_challenge_turn: bool) -> TelegramDeliveryAction:
        reply_text = result.reply_text
        delivery_kind = result.delivery_kind or ("progress" if result.status == "waiting_input" else "chat")
        
        # WS-1: Stale check - 如果 generation 或 turn 不匹配，drop
        if result.reply:
            if result.reply.generation_id is not None and result.reply.generation_id != state.generation_id:
                # generation 不匹配 → drop
                return TelegramDeliveryAction(should_send=False, text="")
            if result.reply.turn_id and result.reply.turn_id != state.active_turn_id and state.active_turn_status == "terminal":
                # turn 已 terminal 且不是当前 turn → drop
                return TelegramDeliveryAction(should_send=False, text="")
        
        # WS-4: 如果任务已完成/阻塞，优先发 final result
        terminal_statuses = {"completed_verified", "completed", "blocked", "failed"}
        if state.task_status in terminal_statuses:
            if reply_text:
                state.last_delivery_type = "final"
                # 清空 pending_progress_events，避免残留
                state.pop_progress_events()
                return TelegramDeliveryAction(should_send=True, text=reply_text)
            return TelegramDeliveryAction(should_send=False, text="")
        
        # WS-4: 检查是否有进度事件
        if state.has_pending_progress_events():
            events = state.pop_progress_events()
            # 取最后一个事件（最有信息量）
            if events:
                last_event = events[-1]
                if isinstance(last_event, ProgressEvent):
                    state.last_delivery_type = last_event.event_type.value
                    
                    # terminal 事件后不发更多消息，直接返回事件文本
                    if is_terminal_event(last_event.event_type):
                        return TelegramDeliveryAction(should_send=True, text=last_event.message)
                    
                    # 非 terminal 事件，返回事件文本
                    return TelegramDeliveryAction(should_send=True, text=last_event.message)
        
        # WS-1: 如果 final_sent 后的 busy/progress，drop
        if delivery_kind == "progress" and state.should_drop_progress():
            return TelegramDeliveryAction(should_send=False, text="")
        
        if not reply_text:
            return TelegramDeliveryAction(should_send=False, text="")
        
        # WS-4: 只过滤确切的 generic busy 文案
        # 不再使用宽泛的关键词匹配
        GENERIC_BUSY_TEXTS = {
            "我还在继续处理刚才那个任务。",
            "收到，正在处理这条请求。",
        }
        if delivery_kind == "progress" and reply_text in GENERIC_BUSY_TEXTS:
            return TelegramDeliveryAction(should_send=False, text="")
        
        # 正常发送 reply
        state.last_delivery_type = delivery_kind
        return TelegramDeliveryAction(should_send=True, text=reply_text)
