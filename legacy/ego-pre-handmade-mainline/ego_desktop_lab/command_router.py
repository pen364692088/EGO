from __future__ import annotations

import json
import platform
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.capability_registry import capability_summary, get_capability
from ego_desktop_lab.decision_view import DecisionView
from ego_desktop_lab.relational_companion import CompanionSurfacePlan, build_companion_surface_plan
from ego_desktop_lab.semantic_provider import route_text_to_safety_scenario_id
from ego_desktop_lab.subjective_loop_contract import classify_feedback_signal


CLAIM_CEILING = "lab-only conversation command layer proof"


@dataclass(frozen=True)
class DialogueState:
    last_user_event: str | None = None
    last_command_type: str | None = None
    last_missing_info: tuple[str, ...] = ()
    last_reply_was_pending: bool = False
    last_feedback_signal: str | None = None
    last_feedback_summary: str | None = None
    preferred_reply_style: str | None = None
    last_answer_topic: str | None = None
    last_answer_summary: str | None = None
    last_answer_command_type: str | None = None
    last_answer_source: str | None = None


@dataclass(frozen=True)
class CommandDecision:
    command_type: str
    source: str
    confidence: float
    rationale: str
    user_event: str
    response_text: str
    missing_info: tuple[str, ...] = ()
    capability_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    safety_relevant: bool = False
    resolved_topic: str | None = None
    context_summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def route_conversation_command(
    text: str,
    *,
    dialogue_state: DialogueState | None = None,
    now: datetime | None = None,
) -> CommandDecision | None:
    stripped = text.strip()
    if not stripped:
        return None
    if route_text_to_safety_scenario_id(stripped) is not None:
        return None
    normalized = " ".join(stripped.lower().split())
    state = dialogue_state or DialogueState()
    feedback_signal = classify_feedback_signal(stripped)

    if feedback_signal is not None:
        return _decision(
            "respond_to_feedback",
            stripped,
            _feedback_response(feedback_signal),
            "user gave affective or corrective feedback; create session-local feedback outcome before continuing",
        )
    if _is_time_query(normalized):
        current = now or datetime.now().astimezone()
        return _decision(
            "answer_local_time",
            stripped,
            f"现在是 {current.strftime('%Y-%m-%d %H:%M:%S %Z%z')}。这是 Python runtime 看到的本地时间，不是通过系统命令读取的。",
            "user asked for current time; local runtime can answer read-only",
        )
    if _is_system_info_query(normalized):
        system_info = _platform_summary()
        return _decision(
            "answer_local_system_info",
            stripped,
            f"我能看到的运行环境是：{system_info}。这是 Python runtime 可见的平台信息；我没有执行系统命令，也没有读取你的文件。",
            "user asked for computer/system information; local runtime can answer read-only",
        )
    math_answer = _basic_math_answer(stripped)
    if math_answer is not None:
        return _decision(
            "basic_math_answer",
            stripped,
            math_answer,
            "user asked a basic arithmetic question; answer deterministically without tools",
        )
    if _is_style_preference_feedback(normalized):
        return _decision(
            "style_preference_feedback",
            stripped,
            "收到。当前会话内我会优先直接回答问题；如果涉及实时数据、文件、命令或权限边界，我仍会明确说明不能直接执行或不能编造。",
            "user requested answer-only style; store session-local surface preference",
        )
    if _is_fresh_external_info_query(normalized):
        return _decision(
            "fresh_external_info_request",
            stripped,
            "当前 lab shell 没有接入实时天气、新闻、行情或网页查询工具，所以我不能编造最新结果。需要实时数据时，后续只能通过 permissioned tool sandbox 或人工提供来源。",
            "user asked for fresh external information; no live tool route is attached",
            resolved_topic=_extract_answer_topic(stripped) or stripped,
        )
    if _is_contextual_followup_query(normalized) and _extract_answer_topic(stripped) is None:
        if state.last_answer_topic:
            if state.last_answer_command_type == "fresh_external_info_request":
                return _decision(
                    "fresh_external_info_request",
                    stripped,
                    (
                        f"上一轮话题是“{state.last_answer_topic}”，但它需要实时外部数据。"
                        "当前 lab shell 没有接入天气、新闻、行情或网页查询工具，所以我不能据此判断或编造最新结论。"
                    ),
                    "short follow-up resolved to previous fresh-data topic, but no live tool route is attached",
                    resolved_topic=state.last_answer_topic,
                    context_summary=state.last_answer_summary,
                )
            return _decision(
                "llm_contextual_followup_answer",
                stripped,
                (
                    f"这句短追问指向上一轮话题“{state.last_answer_topic}”。"
                    "回答可以由 LLM answer draft 生成，但 canonical decision、gate、memory 和 state 不变。"
                ),
                "short follow-up resolved from session-local last answer topic; LLM may answer only as an admitted draft",
                resolved_topic=state.last_answer_topic,
                context_summary=state.last_answer_summary,
            )
    if _is_capability_query(normalized):
        return _decision(
            "answer_capability_question",
            stripped,
            capability_summary(),
            "user asked what the shell can or cannot do",
        )
    if _is_what_info_needed_query(normalized):
        missing = state.last_missing_info or (
            "具体目标",
            "你期望的结果",
            "限制条件或权限边界",
        )
        if state.last_feedback_signal in {"misunderstood", "negative"}:
            prefix = "上一轮你指出我可能误解了；这次我需要先确认"
        else:
            prefix = "上一轮缺的信息是" if state.last_reply_was_pending else "如果要继续判断，我需要"
        return _decision(
            "ask_clarification",
            stripped,
            f"{prefix}：{'、'.join(missing)}。你可以直接补一句目标和限制，我再给下一步建议。",
            "user asked what information is needed; answer from dialogue state",
            missing_info=missing,
        )
    if _is_evidence_boundary_query(normalized):
        return _decision(
            "explain_evidence_boundary",
            stripped,
            "不能把单元测试、模拟通过或局部验证直接说成 live / production 生效。需要真实入口证据、执行 trace、结果记录和可回放 evidence 才能提升结论。",
            "starter-pack style evidence boundary prompt",
        )
    if _is_failed_tool_recovery_query(normalized):
        return _decision(
            "recover_from_failed_tool",
            stripped,
            "如果工具调用失败，就不能假装已经完成。正确做法是报告失败、保留 unknown、检查路径或最小重试条件，再决定是否继续。",
            "starter-pack style failed tool recovery prompt",
        )
    if _is_memory_boundary_query(normalized):
        return _decision(
            "explain_memory_boundary",
            stripped,
            "如果偏好或记忆没有出现在当前上下文或稳定记忆中，就不能当事实使用。应说明来源不可用，并请用户确认或重新提供。",
            "starter-pack style memory boundary prompt",
        )
    if _is_llm_open_question_query(normalized):
        return _decision(
            "llm_open_question_answer",
            stripped,
            "这个问题适合由 LLM 生成 answer draft；当前回答必须经过 admission validator，且不能声称执行工具、读取文件或获取实时数据。",
            "open-ended question admitted only as LLM answer draft; canonical decision and gate remain host-owned",
            resolved_topic=_extract_answer_topic(stripped),
        )
    if _is_outcome_repair_feedback(normalized):
        return None
    companion_plan = build_companion_surface_plan(stripped)
    if companion_plan.intent_family != "unknown_open_chat":
        return _relational_decision(stripped, companion_plan)
    return None


def build_command_decision_view(
    decision: CommandDecision,
    *,
    evidence_log_path: Path,
) -> DecisionView:
    capability = get_capability(decision.command_type)
    action_surface = capability.action_surface if capability else "suggestion_card"
    selected = {
        "id": f"command:{decision.command_type}",
        "goal": decision.command_type,
        "reason": decision.rationale,
        "source_tension": "conversation_command",
        "priority": 1.0,
        "risk": 0.0,
        "cost": 0.0,
        "proposed_action": action_surface,
        "goal_id": None,
        "goal_description": None,
    }
    canonical = {
        "before_selected_intention": None,
        "after_selected_intention": selected,
        "semantic_policy_overlay_applied": False,
        "accepted_failure_type": decision.command_type,
        "selected_goal_id": None,
        "selection_change_reason": decision.rationale,
        "decision_source": "conversation_command_layer",
    }
    gate = {
        "status": "allow",
        "reason": "Read-only local shell command; no external action is executed.",
        "allowed_as": action_surface,
    }
    return DecisionView(
        user_event=decision.user_event,
        semantic_understanding={
            "command_type": decision.command_type,
            "command_source": decision.source,
            "confidence": decision.confidence,
            "rationale": decision.rationale,
            "capability": asdict(capability) if capability else None,
            "resolved_topic": decision.resolved_topic,
            "context_summary": decision.context_summary,
        },
        goal_binding={
            "binding_status": "not_required_for_local_command",
            "related_goal_id": None,
            "selected_goal_id": None,
            "pending_goal_binding": False,
        },
        goal_operation_proposal=None,
        semantic_policy_overlay=None,
        pressure_shift={"before": {}, "after": {}, "delta": {}},
        canonical_decision=canonical,
        gate_decision=gate,
        suggestion=decision.response_text,
        rendered_suggestion=decision.response_text,
        suggestion_source="conversation_command_layer",
        no_action_executed=True,
        evidence_log_path=str(evidence_log_path),
        claim_ceiling=CLAIM_CEILING,
        debug_refs={"command_decision": decision.to_dict()},
    )


def append_command_evidence(path: Path, decision: CommandDecision, view: DecisionView) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event_id": f"event:conversation_command:{decision.command_type}",
        "command_decision": decision.to_dict(),
        "canonical_decision": view.canonical_decision,
        "gate_decision": view.gate_decision,
        "suggestion": view.rendered_suggestion,
        "no_action_executed": view.no_action_executed,
        "claim_ceiling": view.claim_ceiling,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def dialogue_state_from_view(
    view: DecisionView,
    *,
    previous_state: DialogueState | None = None,
    admitted_answer_text: str | None = None,
) -> DialogueState:
    semantic = view.semantic_understanding
    command_type = str(
        semantic.get("command_type")
        or view.canonical_decision.get("accepted_failure_type")
        or "unknown"
    )
    goal_binding = view.goal_binding or {}
    pending = (
        command_type in {"ambiguous_concern", "ask_clarification", "unsupported_or_out_of_scope"}
        or bool(goal_binding.get("pending_goal_binding"))
        or goal_binding.get("binding_status") == "pending_goal_binding"
    )
    missing = ("具体目标", "期望结果", "限制条件或权限边界") if pending else ()
    feedback_signal = classify_feedback_signal(view.user_event or "")
    feedback_summary = None
    if feedback_signal in {"misunderstood", "negative"}:
        feedback_summary = "user reported misunderstanding or low usefulness; next turn should reduce assumptions"
    elif feedback_signal == "helpful":
        feedback_summary = "user reported usefulness; preserve session strategy cautiously"
    preferred = "answer_only" if command_type == "style_preference_feedback" else None
    previous = previous_state or DialogueState()
    last_answer_topic = previous.last_answer_topic
    last_answer_summary = previous.last_answer_summary
    last_answer_command_type = previous.last_answer_command_type
    last_answer_source = previous.last_answer_source
    if command_type in {
        "basic_math_answer",
        "llm_open_question_answer",
        "llm_contextual_followup_answer",
        "fresh_external_info_request",
    }:
        last_answer_topic = (
            _clean_topic(str(semantic.get("resolved_topic") or ""))
            or _extract_answer_topic(view.user_event or "")
            or (view.user_event or "").strip()
            or command_type
        )
        answer_text = admitted_answer_text or view.rendered_suggestion or view.suggestion or ""
        last_answer_summary = _summarize_answer(answer_text)
        last_answer_command_type = command_type
        last_answer_source = "llm_answer_admission" if admitted_answer_text else "conversation_command_layer"
    return DialogueState(
        last_user_event=view.user_event,
        last_command_type=command_type,
        last_missing_info=missing,
        last_reply_was_pending=pending,
        last_feedback_signal=feedback_signal,
        last_feedback_summary=feedback_summary,
        preferred_reply_style=preferred or previous.preferred_reply_style,
        last_answer_topic=last_answer_topic,
        last_answer_summary=last_answer_summary,
        last_answer_command_type=last_answer_command_type,
        last_answer_source=last_answer_source,
    )


def _decision(
    command_type: str,
    user_event: str,
    response_text: str,
    rationale: str,
    *,
    missing_info: tuple[str, ...] = (),
    resolved_topic: str | None = None,
    context_summary: str | None = None,
) -> CommandDecision:
    return CommandDecision(
        command_type=command_type,
        source="deterministic_command_router",
        confidence=0.95,
        rationale=rationale,
        user_event=user_event,
        response_text=response_text,
        missing_info=missing_info,
        capability_id=command_type,
        evidence_refs=(f"command:{command_type}",),
        resolved_topic=resolved_topic,
        context_summary=context_summary,
    )


def _relational_decision(user_event: str, plan: CompanionSurfacePlan) -> CommandDecision:
    return CommandDecision(
        command_type="relational_companion_surface",
        source="deterministic_relational_companion_layer",
        confidence=0.90,
        rationale=(
            f"lab-only relational companion intent={plan.intent_family}; "
            f"strategy={plan.response_strategy}; gate={plan.gate_status}"
        ),
        user_event=user_event,
        response_text=plan.response_text,
        missing_info=("具体指代",) if plan.should_ask_clarification else (),
        capability_id="relational_companion_surface",
        evidence_refs=(f"relational:intent:{plan.intent_family}",),
        safety_relevant=plan.sensitive_request,
    )


def _is_time_query(text: str) -> bool:
    return any(item in text for item in ("几点", "时间", "现在几点", "what time", "current time"))


def _is_system_info_query(text: str) -> bool:
    return any(item in text for item in ("什么系统", "操作系统", "计算机是什么系统", "电脑是什么系统", "system", "os"))


def _is_capability_query(text: str) -> bool:
    return any(item in text for item in ("你能做什么", "能做哪些", "可以做什么", "支持什么", "什么能力", "capabilities", "what can you do"))


def _basic_math_answer(text: str) -> str | None:
    compact = text.replace("？", "?").replace("，", ",").strip()
    match = re.fullmatch(r"\s*(-?\d+)\s*\+\s*(-?\d+)\s*(?:=|等于)?\s*(?:几|多少)?\s*\??\s*", compact)
    if not match:
        return None
    left = int(match.group(1))
    right = int(match.group(2))
    return f"{left}+{right}={left + right}"


def _is_style_preference_feedback(text: str) -> bool:
    return any(
        item in text
        for item in (
            "回答问题即可",
            "直接回答问题",
            "只回答问题",
            "别解释过程",
            "不用展开",
            "answer only",
            "just answer",
        )
    )


def _is_fresh_external_info_query(text: str) -> bool:
    return any(
        item in text
        for item in (
            "天气",
            "气温",
            "下雨",
            "新闻",
            "最新",
            "实时",
            "当前价格",
            "现在价格",
            "行情",
            "weather",
            "forecast",
            "latest",
            "realtime",
            "current price",
        )
    )


def _is_llm_open_question_query(text: str) -> bool:
    if any(item in text for item in ("ego", "stage", "阶段", "项目", "验收", "测试", "下一步")):
        return False
    return any(
        item in text
        for item in (
            "怎么看待",
            "你怎么看",
            "你认为",
            "评价一下",
            "解释一下",
            "介绍一下",
            "你知道",
            "你了解",
            "听说过",
            "为什么",
            "what do you think",
            "do you know",
            "explain",
        )
    )


def _is_contextual_followup_query(text: str) -> bool:
    return any(
        item in text
        for item in (
            "你觉得怎么样",
            "你觉得呢",
            "你怎么看",
            "怎么评价",
            "它怎么样",
            "这个怎么样",
            "那怎么样",
            "继续说",
            "展开讲讲",
            "多说点",
            "为什么这么评价",
            "为什么这么说",
            "适合出门",
            "what about it",
            "tell me more",
            "why so",
        )
    )


def _extract_answer_topic(text: str) -> str | None:
    stripped = _clean_topic(text)
    if not stripped:
        return None
    patterns = (
        r"^(?:你)?(?:听说过|知道|了解)(.+?)(?:吗)?$",
        r"^(?:你)?怎么看待(.+?)$",
        r"^(?:你)?怎么看(.+?)$",
        r"^(?:你)?认为(.+?)$",
        r"^评价一下(.+?)$",
        r"^解释一下(.+?)$",
        r"^介绍一下(.+?)$",
        r"^do you know (.+?)$",
        r"^what do you think(?: about| of)? (.+?)$",
        r"^explain (.+?)$",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        topic = _clean_topic(match.group(1))
        if topic:
            return topic
    if _is_fresh_external_info_query(stripped.lower()):
        return stripped
    return None


def _clean_topic(text: str) -> str:
    topic = " ".join(text.strip().split())
    topic = topic.strip(" \t\r\n，。！？?!.:：；;“”\"'《》")
    if topic.endswith("的") and len(topic) > 1:
        topic = topic[:-1].strip(" ，。！？?!.:：；;“”\"'《》")
    for prefix in ("关于", "对", "一下", "这个", "那个"):
        if topic.startswith(prefix) and len(topic) > len(prefix):
            topic = topic[len(prefix):].strip(" ，。！？?!.:：；;“”\"'《》")
    return topic


def _summarize_answer(text: str, *, limit: int = 160) -> str:
    summary = " ".join(text.strip().split())
    return summary if len(summary) <= limit else f"{summary[:limit - 1]}…"


def _is_what_info_needed_query(text: str) -> bool:
    return any(item in text for item in ("还需要什么信息", "需要什么信息", "缺什么信息", "what info", "what information"))


def _is_evidence_boundary_query(text: str) -> bool:
    return (
        "unit test passed" in text
        or "simulation passed" in text
        or "claim the feature is live" in text
        or "production" in text
        or "证据边界" in text
    )


def _is_failed_tool_recovery_query(text: str) -> bool:
    return (
        "file_not_found" in text
        or "failed tool" in text
        or "tool failed" in text
        or "工具调用失败" in text
        or "读取失败" in text
    )


def _is_memory_boundary_query(text: str) -> bool:
    return (
        "memory boundary" in text
        or "not in the current context" in text
        or "mentioned a preference last week" in text
        or "没有在当前上下文" in text
    )


def _is_outcome_repair_feedback(text: str) -> bool:
    failure_marker = any(
        item in text
        for item in (
            "结果没有改善",
            "没有改善",
            "没改善",
            "没有带来改善",
            "没有帮助",
            "failed",
            "did not help",
            "no improvement",
        )
    )
    repair_marker = any(
        item in text
        for item in (
            "重新规划",
            "重规划",
            "修复",
            "replan",
            "repair",
        )
    )
    return failure_marker and repair_marker


def _feedback_response(feedback_signal: str) -> str:
    if feedback_signal == "helpful":
        return "收到，我会把这次反馈当成当前会话内的正向信号，但不会写入长期记忆。下一步我会尽量沿用这类更有帮助的回答方式。"
    if feedback_signal == "misunderstood":
        return "我先不辩解；这说明上一轮理解可能偏了。请告诉我具体错在目标、事实、权限边界还是表达方式，我会按这个重新判断。"
    return "我先承认这次回复可能没有对齐你的期望，不继续硬推原判断。请指出最关键的不对之处：目标、事实、限制条件，还是表达方式。"


def _platform_summary() -> str:
    system = platform.system() or sys.platform
    release = platform.release()
    machine = platform.machine()
    lower_release = release.lower()
    if system == "Linux" and "microsoft" in lower_release:
        system = "Linux / WSL"
    return f"{system} {release} ({machine})".strip()
