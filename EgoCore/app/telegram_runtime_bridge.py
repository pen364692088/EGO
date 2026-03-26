from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, Optional

from app.telegram_runtime_result import TelegramTurnResult

from app.runtime_v2.progress_events import ProgressEvent, is_terminal_event
from app.runtime_v2.semantic_parser import ParsedIntentGraph, decide_runtime_action, heuristic_parse
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.telegram_bridge import (
    TelegramDeliveryAction,
    TelegramIngressDecision,
    TelegramPreRuntimeAction,
    build_runtime_status_reply,
    build_suggestion_response_from_intent,
    infer_intent,
)

logger = logging.getLogger(__name__)


class TelegramRuntimeBridge:
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

    async def inspect_ingress_semantic(
        self,
        text: str,
        state: RuntimeV2State,
        llm_client: Any = None,
    ) -> TelegramIngressDecision:
        graph = self._normalize_ambiguous_probe(text, heuristic_parse(text), state)

        logger.info(
            "SEMANTIC_AUDIT: text[:50]=%r parser_source=%s primary_intent=%s requires_clarification=%s has_status_query=%s has_correction=%s segments=%s",
            text[:50],
            graph.parser_source,
            graph.primary_intent,
            graph.requires_clarification,
            graph.has_status_query,
            graph.has_correction,
            len(graph.segments),
        )

        requested_output = self._extract_requested_output(text)
        runtime_action = decide_runtime_action(graph, state)
        logger.info("SEMANTIC_AUDIT: runtime_action=%s", runtime_action)

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

        inferred_filename = None
        for seg in graph.segments:
            if seg.kind == "reference_material" and seg.target_ref:
                inferred_filename = seg.target_ref
                break

        is_confirm_execution = looks_like_task and bool(getattr(state, "pending_artifacts", []))

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
            inferred_filename=inferred_filename,
            is_confirm_execution=is_confirm_execution,
            ack_text=None,
            busy_notice_text=None,
            requested_output=requested_output,
            _parsed_intent_graph=graph,
            _runtime_action=runtime_action,
        )

    def inspect_ingress(self, text: str, state: RuntimeV2State) -> TelegramIngressDecision:
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

        is_confirm_execution = looks_like_task and bool(getattr(state, "pending_artifacts", []))

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
        runtime_action = getattr(decision, "_runtime_action", None)
        logger.info(
            "SEMANTIC_AUDIT: plan_pre_runtime runtime_action=%s looks_like_task=%s is_file_only=%s",
            runtime_action,
            decision.looks_like_task,
            decision.is_file_only,
        )

        if decision.is_file_only:
            intent = infer_intent(text="", state=state, has_attachment=True)
            suggestion_text = build_suggestion_response_from_intent(intent, state)
            if intent.inferred_action:
                state.last_inferred_action = intent.inferred_action
            if intent.primary_target:
                target_filename = intent.primary_target.get("filename")
                if target_filename:
                    state.last_inferred_target = target_filename
            return TelegramPreRuntimeAction(
                should_return_early=True,
                force_waiting_input=True,
                waiting_input_text=suggestion_text,
                ack_text=None,
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

    def plan_delivery(self, result: TelegramTurnResult, state: RuntimeV2State, is_challenge_turn: bool) -> TelegramDeliveryAction:
        reply_text = result.reply_text
        delivery_kind = result.delivery_kind or ("progress" if result.status == "waiting_input" else "chat")

        if result.reply:
            if result.reply.generation_id is not None and result.reply.generation_id != state.generation_id:
                return TelegramDeliveryAction(should_send=False, text="")
            if result.reply.turn_id and result.reply.turn_id != state.active_turn_id and state.active_turn_status == "terminal":
                return TelegramDeliveryAction(should_send=False, text="")

        terminal_statuses = {"completed_verified", "completed", "blocked", "failed"}
        if state.task_status in terminal_statuses:
            if reply_text:
                state.last_delivery_type = "final"
                state.pop_progress_events()
                return TelegramDeliveryAction(should_send=True, text=reply_text)
            return TelegramDeliveryAction(should_send=False, text="")

        if state.has_pending_progress_events():
            events = state.pop_progress_events()
            if events:
                last_event = events[-1]
                if isinstance(last_event, ProgressEvent):
                    state.last_delivery_type = last_event.event_type.value
                    if is_terminal_event(last_event.event_type):
                        return TelegramDeliveryAction(should_send=True, text=last_event.message)
                    return TelegramDeliveryAction(should_send=True, text=last_event.message)

        if delivery_kind == "progress" and state.should_drop_progress():
            return TelegramDeliveryAction(should_send=False, text="")

        if not reply_text:
            return TelegramDeliveryAction(should_send=False, text="")

        generic_busy_texts = {
            "我还在继续处理刚才那个任务。",
            "收到，正在处理这条请求。",
        }
        if delivery_kind == "progress" and reply_text in generic_busy_texts:
            return TelegramDeliveryAction(should_send=False, text="")

        state.last_delivery_type = delivery_kind
        return TelegramDeliveryAction(should_send=True, text=reply_text)


__all__ = [
    "TelegramRuntimeBridge",
    "TelegramDeliveryAction",
    "TelegramIngressDecision",
    "TelegramPreRuntimeAction",
]
