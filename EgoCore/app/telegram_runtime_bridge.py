from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional

from app.memory.profile_memory import ProfileMemory, StandingRuleParseFailure, describe_standing_rule
from app.risk_signal import assess_message_risk_level
from app.telegram_runtime_result import TelegramTurnResult

from app.runtime_v2.progress_events import ProgressEvent, is_terminal_event
from app.runtime_v2.semantic_parser import ParsedIntentGraph, SemanticSegment, build_runtime_status_reply, decide_runtime_action, heuristic_parse
from app.runtime_v2.state import RuntimeV2State

logger = logging.getLogger(__name__)

FILE_TYPE_PATTERNS = {
    "task": ["任务单", "todo", "task", "plan", "fix", "patch", "执行", ".txt"],
    "spec": ["SOUL", "AGENTS", "TOOLS", "BOOTSTRAP", "README", "POLICY", "规范", ".md"],
    "log": ["log", "trace", "error", "report", "日志", ".log"],
}


@dataclass
class IntentInference:
    inferred_action: Optional[str] = None
    confidence: str = "low"
    primary_target: Optional[Dict[str, Any]] = None
    secondary_option: Optional[str] = None
    reason: Optional[str] = None


def extract_filename_from_text(text: str) -> Optional[str]:
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
    if re.search(r"(执行|运行|开始|做|处理|改|修|fix|run|execute)", text or "", flags=re.IGNORECASE):
        return IntentInference(
            inferred_action="execute",
            confidence="high",
            primary_target=state.last_uploaded_artifact,
            secondary_option="analyze",
            reason="用户明确提到动作",
        )

    result = IntentInference()
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
        if artifact_type == "spec":
            result.inferred_action = "analyze"
            result.confidence = "medium"
            result.primary_target = state.last_uploaded_artifact
            result.secondary_option = "constraint"
            result.reason = "检测到规范类文件"
            return result

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

    result.reason = "无法推断意图"
    return result


def build_suggestion_response_from_intent(intent: IntentInference, state: RuntimeV2State) -> str:
    action = intent.inferred_action
    confidence = intent.confidence
    target = intent.primary_target
    secondary = intent.secondary_option

    if state.pending_artifacts and len(state.pending_artifacts) >= 2:
        task_artifacts = state.get_task_artifacts()
        spec_artifacts = state.get_spec_artifacts()
        if task_artifacts and spec_artifacts:
            task_file = task_artifacts[-1].get("filename", "任务单")
            spec_count = len(spec_artifacts)
            if confidence == "high":
                return f"我可以先按「{task_file}」执行，并把 {spec_count} 份规范当作约束。要我这样走吗？"
            return f"我看有 {spec_count} 份规范和 1 份任务单「{task_file}」。要我按任务单执行，并把规范当约束？还是先对比规范？"
        if len(spec_artifacts) >= 2:
            if confidence == "high":
                return f"现在有 {len(spec_artifacts)} 份规范文件，我可以先做职责边界对比。要我现在开始吗？"
            return f"我看到 {len(spec_artifacts)} 份规范文件。你要我对比它们的职责边界，还是审查某一份？"

    if target:
        filename = target.get("filename", "文件")
        if action == "execute":
            if confidence == "high":
                return f"我先按「{filename}」执行。要我开始吗？"
            if confidence == "medium":
                return f"我看这更像一份任务单「{filename}」。我要先按「执行这份任务」走吗？"
            if secondary == "analyze":
                return f"收到「{filename}」。你要我执行它，还是先审查内容？"
            return f"收到「{filename}」。你要我做什么？"
        if action == "analyze":
            if confidence == "high":
                return f"我先审查「{filename}」。要我开始吗？"
            if confidence == "medium":
                if secondary == "constraint":
                    return f"这更像规范文件「{filename}」。你是要我审查它，还是把它当作后续执行约束？"
                return f"我看这是「{filename}」。你要我先审查它吗？"
            return f"收到「{filename}」。你要我审查它，还是把它当作执行约束？"
        if action == "compare":
            if confidence == "high":
                return "我开始对比。要我现在开始吗？"
            return "你想要对比哪些文件？"

    return "收到文件。请告诉我你想做什么（执行/审查/对比）？"


def build_suggestion_response(filename: str, file_type: str, action: Optional[str] = None) -> str:
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
    is_file_only: bool = False
    inferred_action: Optional[str] = None
    inferred_file_type: Optional[str] = None
    inferred_filename: Optional[str] = None
    is_confirm_execution: bool = False
    ack_text: Optional[str] = None
    busy_notice_text: Optional[str] = None
    requested_output: Optional[Dict[str, Any]] = None
    source_text: str = ""
    profile_scope: Optional[str] = None
    active_profile_rules: List[Dict[str, Any]] = field(default_factory=list)
    matched_profile_rules: List[Dict[str, Any]] = field(default_factory=list)
    rule_enforcement: Optional[Dict[str, Any]] = None
    registered_profile_rule: Optional[Dict[str, Any]] = None
    profile_rule_parse_error: Optional[Dict[str, Any]] = None
    _parsed_intent_graph: Optional[ParsedIntentGraph] = None
    _runtime_action: Optional[str] = None


@dataclass
class TelegramPreRuntimeAction:
    should_return_early: bool = False
    busy_notice_text: Optional[str] = None
    ack_text: Optional[str] = None
    remember_challenge_turn: bool = False
    force_waiting_input: bool = False
    waiting_input_text: Optional[str] = None
    direct_reply_text: Optional[str] = None
    rule_enforcement: Optional[Dict[str, Any]] = None
    response_plan_metadata: Optional[Dict[str, Any]] = None


@dataclass
class TelegramDeliveryAction:
    should_send: bool
    text: str = ""


class TelegramRuntimeBridge:
    AMBIGUOUS_PRESENCE_PROBES = {"在吗", "还在吗", "还在不", "在不在"}
    CONFIRM_EXECUTION_PATTERNS = {
        "执行",
        "执行吧",
        "继续",
        "继续执行",
        "接着",
        "接着做",
        "开始执行",
        "开始",
        "开始吧",
        "按这个执行",
        "按这个做",
        "就按这个做",
        "按这个走",
        "就按这个走",
    }
    WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() -]+[\\/])*[A-Za-z0-9._() -]+")
    UNIX_PATH_RE = re.compile(r"(?:/mnt|/home|/tmp|/Users)(?:/[A-Za-z0-9._() -]+)+")

    def __init__(self, profile_memory_factory: Optional[Any] = None) -> None:
        self._profile_memory_factory = profile_memory_factory or (lambda scope: ProfileMemory(scope))

    def _resolve_profile_scope(self, state: RuntimeV2State) -> str:
        session_id = str(getattr(state, "session_id", "") or "").strip()
        if session_id.startswith("telegram:dm:"):
            return session_id.rsplit(":", 1)[-1]
        return session_id or "anonymous"

    def _get_profile_memory(self, state: RuntimeV2State, profile_scope: Optional[str] = None) -> Optional[ProfileMemory]:
        try:
            return self._profile_memory_factory(profile_scope or self._resolve_profile_scope(state))
        except Exception as exc:
            logger.warning("profile_memory.unavailable scope=%s err=%s", profile_scope or self._resolve_profile_scope(state), exc)
            return None

    def _looks_like_explicit_default_rule_request(self, text: str) -> bool:
        normalized = (text or "").strip()
        return any(token in normalized for token in ("默认走", "默认规则", "以后凡是", "以后涉及", "请记住", "记住这条规则"))

    def _looks_like_explicit_path(self, target_ref: Optional[str]) -> bool:
        if not target_ref:
            return False
        return bool(self.WINDOWS_PATH_RE.fullmatch(target_ref) or self.UNIX_PATH_RE.fullmatch(target_ref))

    def _build_explicit_path_target(self, target_ref: str) -> Dict[str, Any]:
        if re.match(r"^[A-Za-z]:[\\/]", target_ref or ""):
            filename = PureWindowsPath(target_ref).name
        else:
            filename = PurePosixPath(target_ref).name
        return {
            "path": target_ref,
            "filename": filename or target_ref,
            "source": "explicit_path",
        }

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

    def _looks_like_execution_confirmation(self, text: str, state: RuntimeV2State) -> bool:
        normalized = re.sub(r"\s+", "", (text or "").strip().lower()).strip("?!？！。,.，\"'“”‘’")
        if normalized not in self.CONFIRM_EXECUTION_PATTERNS:
            return False
        if getattr(state, "task_contract", None) and getattr(state, "contract_phase", None) in {"step_selected", "planning_stalled", "re_lock_needed", "executing"}:
            return True
        if getattr(state, "waiting_for_user_input", False):
            return True
        if not getattr(state, "pending_artifacts", []):
            return False
        if getattr(state, "last_inferred_action", None) == "execute":
            return True
        return False

    def _promote_execution_confirmation(
        self,
        text: str,
        graph: ParsedIntentGraph,
        state: RuntimeV2State,
    ) -> ParsedIntentGraph:
        if not self._looks_like_execution_confirmation(text, state):
            return graph

        target = state.resolve_target("execute")
        target_ref = None
        if target:
            target_ref = target.get("artifact_id") or target.get("artifact_ref") or target.get("filename")

        segment = SemanticSegment(
            text=text,
            kind="task_request",
            confidence=0.98,
            refers_to_previous=True,
            target_ref=target_ref,
            request_mode="execute",
            priority=0,
        )
        promoted = ParsedIntentGraph(
            segments=[segment],
            primary_intent="task_request",
            secondary_intents=[],
            parser_source="heuristic_parser",
            graph_version=graph.graph_version,
        )
        if target_ref:
            promoted.actionable_targets.append(target_ref)
        return promoted

    def _resolve_request_mode(self, decision: TelegramIngressDecision) -> Optional[str]:
        graph = decision._parsed_intent_graph
        if graph is not None:
            for seg in graph.segments:
                if seg.request_mode:
                    return seg.request_mode
        if decision.is_confirm_execution:
            return "execute"
        return None

    def _resolve_explicit_target_ref(self, decision: TelegramIngressDecision) -> Optional[str]:
        graph = decision._parsed_intent_graph
        if graph is not None:
            for seg in graph.segments:
                if self._looks_like_explicit_path(seg.target_ref):
                    return seg.target_ref
        requested_output = decision.requested_output or {}
        for key in ("effective_path", "target_path"):
            if self._looks_like_explicit_path(requested_output.get(key)):
                return requested_output.get(key)
        return None

    def _resolve_target_for_decision(
        self,
        decision: TelegramIngressDecision,
        state: RuntimeV2State,
        request_mode: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        explicit_target_ref = self._resolve_explicit_target_ref(decision)
        target_action = request_mode or decision.inferred_action
        if explicit_target_ref and target_action in {"execute", "compare", "analyze", "write"}:
            state.last_explicit_target = explicit_target_ref
            return self._build_explicit_path_target(explicit_target_ref)

        resolved_target = state.resolve_target(target_action) if target_action in {"execute", "compare", "analyze"} else None
        if resolved_target is not None:
            explicit_ref = resolved_target.get("path") or resolved_target.get("artifact_id") or resolved_target.get("filename")
            if resolved_target.get("source") == "explicit_target" and self._looks_like_explicit_path(explicit_ref):
                return self._build_explicit_path_target(str(explicit_ref))
            return resolved_target

        if decision.requested_output:
            return {
                "path": decision.requested_output.get("effective_path"),
                "source": "explicit_output_request",
                "format": decision.requested_output.get("format"),
            }
        return None

    def _build_rule_context(self, rule: Any, *, matched: bool, risk_level: Optional[str] = None) -> Dict[str, Any]:
        summary = describe_standing_rule(rule) if hasattr(rule, "predicate") else rule.get("summary")
        if hasattr(rule, "to_dict"):
            payload = rule.to_dict()
        else:
            payload = dict(rule or {})
        context = {
            "rule_id": payload.get("rule_id"),
            "predicate": payload.get("predicate") or {},
            "phase": payload.get("phase"),
            "effect": payload.get("effect") or {},
            "priority": payload.get("priority"),
            "enabled": payload.get("enabled", True),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "authority_source": "profile_memory",
            "summary": summary,
            "matched": matched,
        }
        if risk_level is not None:
            context["matched_risk_level"] = risk_level
        return context

    def _build_rule_enforcement(
        self,
        matched_rules: List[Dict[str, Any]],
        *,
        resolved_target: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not matched_rules:
            return None

        winner = matched_rules[0]
        effect = winner.get("effect") or {}
        effect_type = effect.get("type")
        matched_rule_ids = [item.get("rule_id") for item in matched_rules if item.get("rule_id")]

        if effect_type == "reply_only_once":
            return {
                "kind": "reply_only_once",
                "selected_rule_id": winner.get("rule_id"),
                "matched_rule_ids": matched_rule_ids,
                "authority_source": "profile_memory",
                "reply_text": effect.get("phrase") or "",
                "summary": winner.get("summary"),
            }

        nested_effects = effect.get("effects") if effect_type == "composite" else [effect]
        effect_types = {item.get("type") for item in nested_effects if isinstance(item, dict)}
        if {
            "read_only_first",
            "require_minimal_verification_before_mutation",
            "forbid_direct_mutation_before_confirmation",
        }.intersection(effect_types):
            return {
                "kind": "read_only_preflight",
                "selected_rule_id": winner.get("rule_id"),
                "matched_rule_ids": matched_rule_ids,
                "authority_source": "profile_memory",
                "blocked_mutation": True,
                "requires_confirmation": True,
                "summary": winner.get("summary"),
                "target_path": (resolved_target or {}).get("path"),
            }

        return None

    def _attach_profile_rule_context(
        self,
        decision: TelegramIngressDecision,
        state: RuntimeV2State,
        *,
        resolved_target: Optional[Dict[str, Any]] = None,
        request_mode: Optional[str] = None,
    ) -> None:
        profile_scope = decision.profile_scope or self._resolve_profile_scope(state)
        decision.profile_scope = profile_scope
        profile_memory = self._get_profile_memory(state, profile_scope)
        if profile_memory is None:
            decision.active_profile_rules = []
            decision.matched_profile_rules = []
            decision.rule_enforcement = None
            return
        decision.active_profile_rules = profile_memory.get_active_rule_contexts()

        if decision.registered_profile_rule or decision.profile_rule_parse_error:
            decision.matched_profile_rules = []
            return

        request_mode = request_mode or self._resolve_request_mode(decision)
        resolved_target = resolved_target if resolved_target is not None else self._resolve_target_for_decision(decision, state, request_mode)
        risk_level = assess_message_risk_level(decision.source_text)
        matched_rules = profile_memory.match_standing_rules(
            target_path=(resolved_target or {}).get("path"),
            request_mode=request_mode,
            risk_level=risk_level,
        )
        decision.matched_profile_rules = [
            self._build_rule_context(rule, matched=True, risk_level=risk_level)
            for rule in matched_rules
        ]
        decision.rule_enforcement = self._build_rule_enforcement(
            decision.matched_profile_rules,
            resolved_target=resolved_target,
        )

    def build_ingress_context(
        self,
        decision: TelegramIngressDecision,
        state: RuntimeV2State,
    ) -> Dict[str, Any]:
        graph = decision._parsed_intent_graph
        request_mode = self._resolve_request_mode(decision)
        resolved_target = self._resolve_target_for_decision(decision, state, request_mode)
        self._attach_profile_rule_context(
            decision,
            state,
            resolved_target=resolved_target,
            request_mode=request_mode,
        )
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
            "profile_scope": decision.profile_scope,
            "active_profile_rules": decision.active_profile_rules,
            "matched_profile_rules": decision.matched_profile_rules,
            "rule_enforcement": decision.rule_enforcement,
            "profile_rule_authority": "profile_memory",
            "restore_observation": None,
        }

    async def inspect_ingress_semantic(
        self,
        text: str,
        state: RuntimeV2State,
        llm_client: Any = None,
    ) -> TelegramIngressDecision:
        graph = self._normalize_ambiguous_probe(text, heuristic_parse(text), state)
        graph = self._promote_execution_confirmation(text, graph, state)

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

        is_confirm_execution = self._looks_like_execution_confirmation(text, state)
        decision = TelegramIngressDecision(
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
            source_text=text,
            profile_scope=self._resolve_profile_scope(state),
            _parsed_intent_graph=graph,
            _runtime_action=runtime_action,
        )
        profile_memory = self._get_profile_memory(state, decision.profile_scope)
        if profile_memory is not None:
            registration = profile_memory.register_standing_rule_from_text(
                text,
                created_from={
                    "source": "telegram_runtime_bridge",
                    "session_id": state.session_id,
                    "text": text[:500],
                },
            )
            if registration is not None:
                if isinstance(registration, StandingRuleParseFailure):
                    decision.profile_rule_parse_error = {
                        "reason": registration.reason,
                        "acknowledgement_text": registration.acknowledgement_text,
                        "authority_source": "profile_memory",
                    }
                else:
                    decision.registered_profile_rule = {
                        **self._build_rule_context(registration.rule, matched=False),
                        "created": registration.created,
                        "confirmation_text": registration.confirmation_text,
                    }
        self._attach_profile_rule_context(decision, state)
        return decision

    def inspect_ingress(self, text: str, state: RuntimeV2State) -> TelegramIngressDecision:
        graph = self._normalize_ambiguous_probe(text, heuristic_parse(text), state)
        graph = self._promote_execution_confirmation(text, graph, state)
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

        is_confirm_execution = self._looks_like_execution_confirmation(text, state)
        decision = TelegramIngressDecision(
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
            source_text=text,
            profile_scope=self._resolve_profile_scope(state),
            _parsed_intent_graph=graph,
            _runtime_action=runtime_action,
        )
        profile_memory = self._get_profile_memory(state, decision.profile_scope)
        if profile_memory is not None:
            registration = profile_memory.register_standing_rule_from_text(
                text,
                created_from={
                    "source": "telegram_runtime_bridge",
                    "session_id": state.session_id,
                    "text": text[:500],
                },
            )
            if registration is not None:
                if isinstance(registration, StandingRuleParseFailure):
                    decision.profile_rule_parse_error = {
                        "reason": registration.reason,
                        "acknowledgement_text": registration.acknowledgement_text,
                        "authority_source": "profile_memory",
                    }
                else:
                    decision.registered_profile_rule = {
                        **self._build_rule_context(registration.rule, matched=False),
                        "created": registration.created,
                        "confirmation_text": registration.confirmation_text,
                    }
        self._attach_profile_rule_context(decision, state)
        return decision

    def plan_pre_runtime(self, decision: TelegramIngressDecision, state: RuntimeV2State) -> TelegramPreRuntimeAction:
        self._attach_profile_rule_context(decision, state)
        runtime_action = getattr(decision, "_runtime_action", None)
        logger.info(
            "SEMANTIC_AUDIT: plan_pre_runtime runtime_action=%s looks_like_task=%s is_file_only=%s",
            runtime_action,
            decision.looks_like_task,
            decision.is_file_only,
        )

        if decision.profile_rule_parse_error:
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text=decision.profile_rule_parse_error.get("acknowledgement_text"),
                rule_enforcement={
                    "kind": "profile_rule_unsupported",
                    "authority_source": "profile_memory",
                    "reason": decision.profile_rule_parse_error.get("reason"),
                },
                response_plan_metadata={
                    "status": "profile_rule_unsupported",
                    "delivery_kind": "final",
                    "authority_source": "profile_memory",
                },
            )

        if decision.registered_profile_rule:
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text=decision.registered_profile_rule.get("confirmation_text"),
                rule_enforcement={
                    "kind": "profile_rule_registered",
                    "authority_source": "profile_memory",
                    "selected_rule_id": decision.registered_profile_rule.get("rule_id"),
                },
                response_plan_metadata={
                    "status": "profile_rule_registered",
                    "delivery_kind": "final",
                    "authority_source": "profile_memory",
                    "matched_rule_ids": [decision.registered_profile_rule.get("rule_id")],
                },
            )

        if decision.rule_enforcement and decision.rule_enforcement.get("kind") == "reply_only_once":
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text=decision.rule_enforcement.get("reply_text"),
                rule_enforcement=decision.rule_enforcement,
                response_plan_metadata={
                    "status": "profile_rule_enforced",
                    "delivery_kind": "final",
                    "authority_source": "profile_memory",
                    "matched_rule_ids": decision.rule_enforcement.get("matched_rule_ids") or [],
                    "enforcement": decision.rule_enforcement,
                },
            )

        if decision.rule_enforcement and decision.rule_enforcement.get("kind") == "read_only_preflight":
            return TelegramPreRuntimeAction(
                should_return_early=True,
                force_waiting_input=True,
                rule_enforcement=decision.rule_enforcement,
                response_plan_metadata={
                    "status": "profile_rule_enforced",
                    "delivery_kind": "waiting_input",
                    "authority_source": "profile_memory",
                    "matched_rule_ids": decision.rule_enforcement.get("matched_rule_ids") or [],
                    "enforcement": decision.rule_enforcement,
                },
            )

        if decision.is_file_only:
            intent = infer_intent(text="", state=state, has_attachment=True)
            if intent.inferred_action:
                state.last_inferred_action = intent.inferred_action
            if intent.primary_target:
                target_filename = intent.primary_target.get("filename")
                if target_filename:
                    state.last_inferred_target = target_filename
            if intent.inferred_action == "execute":
                decision._runtime_action = "execute_task"
                if state.ingress_context is not None:
                    state.ingress_context["runtime_action"] = "execute_task"
                    state.ingress_context["request_mode"] = "execute"
                    state.ingress_context["resolved_target"] = state.resolve_target("execute")
                return TelegramPreRuntimeAction(
                    should_return_early=False,
                    ack_text="收到任务单，开始执行。",
                )
            suggestion_text = build_suggestion_response_from_intent(intent, state)
            return TelegramPreRuntimeAction(
                should_return_early=True,
                force_waiting_input=True,
                waiting_input_text=suggestion_text,
                ack_text=None,
                response_plan_metadata={
                    "status": "waiting_input",
                    "delivery_kind": "waiting_input",
                    "authority_source": "host_pre_runtime",
                },
            )

        if runtime_action == "return_runtime_status":
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text=build_runtime_status_reply(state),
                remember_challenge_turn=decision.remember_challenge_turn,
                response_plan_metadata={
                    "status": "return_runtime_status",
                    "delivery_kind": "final",
                    "authority_source": "host_pre_runtime",
                },
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
    "FILE_TYPE_PATTERNS",
    "IntentInference",
    "extract_filename_from_text",
    "infer_intent_from_filename",
    "infer_intent",
    "build_suggestion_response_from_intent",
    "build_suggestion_response",
    "TelegramRuntimeBridge",
    "TelegramDeliveryAction",
    "TelegramIngressDecision",
    "TelegramPreRuntimeAction",
]
