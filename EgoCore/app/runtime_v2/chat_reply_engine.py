from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import ConfigError, get_config
from app.llm_client import get_llm_client
from app.response_contract.memory_claim_gate import build_current_session_recall_grounding, evaluate_memory_claim
from app.restore_runtime import PendingRestoreObservation

from .chat_state import normalize_chat_reply
from .runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from .state import RuntimeV2State

logger = logging.getLogger(__name__)


CHAT_MAINLINE_SYSTEM_PROMPT = """你是 EgoCore runtime_v2 的 chat mainline。
你的职责只有一件事：对普通聊天生成自然语言回复。

硬规则：
1. 这是普通聊天，不输出 JSON，不调用工具，不编造执行结果。
2. 不要主动把聊天拉回任务，不要说“请说任务/请说任务内容/开始任务”，除非用户明确要求进入任务。
3. 如果当前 turn 是 presence_check / social_keepalive，就自然回应“我在/我看到了你”，但不要机械复读。
4. 如果用户在抱怨重复、语气或说辞，先吸收这个反馈，再自然回应，不要辩解。
5. 不要回放旧的目录正文、文件内容、工具输出或任务总结，除非用户明确在追问那条证据。
6. 允许简短，但要像人在聊天，不像控制面固定模板。
7. 当前若存在 active task，它只作为背景信息，不是你必须提起的主题。
8. 回复 1 到 2 句，默认简洁。
9. 如果当前没有明确 restore authority，不要声称“已经恢复成功”“跨对话持续记忆已经就绪”。
10. 如果用户在问当前会话里刚聊过的内容，允许基于这段对话里的明确锚点自然回应，例如“记得，你刚才在聊……”；但不要把这说成跨对话记忆或长期记忆。
11. 如果当前 turn 是 thread_continue，表示“把刚才的话题继续展开”，默认顺着上一条聊天往下说，不要切回任务、状态或证据回放。
12. 只有当上下文明确标出 resume_hint_eligible 时，才允许最多一句轻提示“如果你是说恢复任务，用 /resume”；不要把它说成硬拦截。
13. 如果结构化上下文里带有 `chat_expression_hint`，在不违背其它规则时按它控制展开程度、语气和下一步偏向。
14. `reply_mode=short` 时尽量 1 句；`reply_mode=normal` 时 1 到 2 句；`reply_mode=expand` 时最多 4 句。
15. `reply_mode=hold` 时，把回复写成一条可独立发送的后续补充，不要写“我先不回/稍后再说”这类控制面说明。
16. 如果结构化上下文里带有 `recent_delivered_result_context`，且用户显然在追问刚刚交付的页面、文件或结果，优先基于这个上下文自然回应，不要说自己没有这段上下文。
"""


class ChatReplyEngine:
    def __init__(self) -> None:
        self.llm_client = None

    async def reply(self, state: RuntimeV2State) -> RuntimeV2TurnResult:
        ingress = dict(state.ingress_context or {})
        chat_act = str(ingress.get("conversation_act") or "light_chitchat").strip() or "light_chitchat"
        restore_observation = _resolve_restore_observation(state)
        current_session_grounding = _resolve_current_session_recall_grounding(state)
        state.prepare_chat_turn(user_text=state.last_user_turn or "", chat_act=chat_act)
        chat_expression_hint = _build_chat_expression_hint(state, conversation_act=chat_act)
        chat_cadence_mode = _build_chat_cadence_mode(chat_expression_hint)
        response_tendency_summary = _build_response_tendency_summary(state, chat_expression_hint)

        try:
            candidate = await self._generate_reply(state)
            if self._should_regenerate(candidate, state, chat_act):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=(
                        "上一条候选与最近回复完全重复。保持同语义，但换一种自然说法；"
                        "不要拉回任务，不要回放旧证据。"
                    ),
                )
            if _should_regenerate_for_memory_claim(candidate, restore_observation, current_session_grounding):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_memory_claim_regeneration_hint(chat_act),
                )
            intent_gate_preview = _preview_intent_gate(candidate, state, chat_act)
            if intent_gate_preview["status"] == "violation" and intent_gate_preview["would_block"]:
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_intent_gate_regeneration_hint(intent_gate_preview, chat_act),
                )
            reply_text = _apply_chat_expression_hint(str(candidate or "").strip(), chat_expression_hint)
            if not reply_text:
                raise RuntimeError("empty_chat_reply")
            reply_authority = "model_chat"
        except Exception as exc:
            logger.warning("runtime_v2.chat_mainline.degraded err=%s", exc)
            reply_text = "我在。刚才聊天生成出了点问题，你可以继续说。"
            reply_authority = "host_degraded_fallback"

        state.finalize_chat_turn(assistant_reply=reply_text, chat_act=chat_act)
        state.last_model_action = {
            "type": "chat",
            "message": reply_text,
            "chat_act": chat_act,
            "reply_authority": reply_authority,
            "chat_expression_hint": chat_expression_hint,
            "chat_cadence_mode": chat_cadence_mode,
            "response_tendency_summary": response_tendency_summary,
        }
        state.record(
            "assistant",
            {
                "type": "chat_reply",
                "text": reply_text,
                "chat_act": chat_act,
                "reply_authority": reply_authority,
                "reply_origin": "chat_mainline",
                "chat_expression_hint": chat_expression_hint,
                "chat_cadence_mode": chat_cadence_mode,
                "response_tendency_summary": response_tendency_summary,
            },
        )
        state.last_delivery_type = "chat"
        return RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text=reply_text,
                delivery_kind="chat",
                status="chat",
                metadata={
                    "chat_act": chat_act,
                    "reply_origin": "chat_mainline",
                    "reply_authority": reply_authority,
                    "chat_expression_hint": chat_expression_hint,
                    "chat_cadence_mode": chat_cadence_mode,
                    "response_tendency_summary": response_tendency_summary,
                },
            ),
            finish_reason="chat_mainline",
        )

    async def _generate_reply(self, state: RuntimeV2State, *, extra_system_hint: Optional[str] = None) -> str:
        messages = self._build_messages(state, extra_system_hint=extra_system_hint)
        response = await self._generate_with_fallback(
            messages,
            temperature=self._resolve_temperature(),
            max_tokens=self._resolve_max_tokens(),
            timeout_seconds=self._resolve_timeout_seconds(),
        )
        if response.usage:
            prompt_tokens = response.usage.get("prompt_tokens", 0) or response.usage.get("input_tokens", 0)
            completion_tokens = response.usage.get("completion_tokens", 0) or response.usage.get("output_tokens", 0)
            state.record_token_usage(prompt_tokens, completion_tokens)
        return str(response.content or "").strip()

    def _build_messages(self, state: RuntimeV2State, *, extra_system_hint: Optional[str] = None) -> List[Dict[str, str]]:
        context = state.to_chat_prompt_context()
        relationship = dict(context.get("relationship_context") or {})
        style = dict(context.get("style_profile") or {})
        proto_self = dict(context.get("proto_self_context") or {})
        recent_result_context = dict(context.get("recent_delivered_result_context") or {})
        tendency = dict(proto_self.get("response_tendency") or {})
        policy_hint = dict(proto_self.get("policy_hint") or {})
        reflection_note = dict(proto_self.get("reflection_note") or {})
        chat_expression_hint = _build_chat_expression_hint(
            state,
            conversation_act=context.get("conversation_act"),
        )

        system_prompt = CHAT_MAINLINE_SYSTEM_PROMPT
        if extra_system_hint:
            system_prompt += "\n" + extra_system_hint.strip() + "\n"

        payload = {
            "chat_context": {
                "conversation_act": context.get("conversation_act") or "light_chitchat",
                "last_user_turn": context.get("last_user_turn"),
                "recent_user_turns": context.get("recent_user_turns") or [],
                "recent_assistant_replies": context.get("recent_assistant_replies") or [],
                "last_user_tone_feedback": context.get("last_user_tone_feedback"),
                "active_task_summary": context.get("active_task_summary"),
                "resume_hint_eligible": bool((context.get("ingress_context") or {}).get("resume_hint_eligible")),
            },
            "relationship_context": {
                "conversation_temperature": relationship.get("conversation_temperature"),
                "current_social_arc": relationship.get("current_social_arc"),
                "last_user_feedback_about_tone": relationship.get("last_user_feedback_about_tone"),
                "recent_social_modes": list((relationship.get("recent_social_modes") or [])[-4:]),
            },
            "style_profile": {
                "dimensions": style.get("dimensions") or {},
                "preferred_markers": style.get("preferred_markers") or [],
                "avoid_markers": style.get("avoid_markers") or [],
            },
            "recent_delivered_result_context": {
                "binding_kind": recent_result_context.get("binding_kind"),
                "runtime_status": recent_result_context.get("runtime_status"),
                "reply_origin": recent_result_context.get("reply_origin"),
                "target_name": recent_result_context.get("target_name"),
                "target_path": recent_result_context.get("target_path"),
                "reply_preview": recent_result_context.get("reply_preview"),
                "tool_result_summary": dict(recent_result_context.get("tool_result_summary") or {}),
            },
            "proto_self_context": {
                "subject_profile": proto_self.get("subject_profile"),
                "response_tendency": tendency,
                "reflection_note": {
                    "trigger": reflection_note.get("trigger"),
                    "diagnosis": reflection_note.get("diagnosis"),
                },
                "policy_hint": {
                    "subject_profile": policy_hint.get("subject_profile"),
                    "ask_preferred": policy_hint.get("ask_preferred"),
                    "closure_bias": policy_hint.get("closure_bias"),
                    "risk_bias": policy_hint.get("risk_bias"),
                },
                "social_policy_hints": dict(proto_self.get("social_policy_hints") or {}),
                "embodied_policy_hints": dict(proto_self.get("embodied_policy_hints") or {}),
                "integrated_policy_hints": dict(proto_self.get("integrated_policy_hints") or {}),
                "initiative_policy_hints": dict(proto_self.get("initiative_policy_hints") or {}),
                "recent_tendency_summaries": _extract_recent_tendency_summaries(state),
                "chat_expression_hint": chat_expression_hint,
                "chat_cadence_mode": _build_chat_cadence_mode(chat_expression_hint),
            },
            "memory_claim_contract": _build_memory_claim_contract(state),
            "reply_rules": {
                "do_not_task_bridge_by_default": True,
                "do_not_replay_evidence": True,
                "continue_last_chat_thread": (context.get("conversation_act") == "thread_continue"),
                "anti_repeat_window": list(state.get_chat_state().recent_assistant_replies[-3:]),
            },
        }
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "基于下面结构化上下文直接回复用户。不要解释规则，不要输出 JSON。\n\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                ),
            },
        ]

    def _should_regenerate(self, reply_text: str, state: RuntimeV2State, chat_act: str) -> bool:
        if chat_act not in {"presence_check", "social_keepalive"}:
            return False
        normalized = normalize_chat_reply(reply_text)
        if not normalized:
            return False
        return normalized in state.get_chat_state().recent_normalized_replies(limit=3)

    def _resolve_chat_use_case(self) -> Dict[str, Any]:
        config = get_config()
        return config.get_llm_config_for_use_case("chat")

    def _resolve_temperature(self) -> float:
        try:
            use_case = self._resolve_chat_use_case()
            return float(use_case.get("temperature") or 0.8)
        except (ConfigError, TypeError, ValueError):
            return 0.8

    def _resolve_max_tokens(self) -> int:
        try:
            use_case = self._resolve_chat_use_case()
            return int(use_case.get("max_tokens") or 400)
        except (ConfigError, TypeError, ValueError):
            return 400

    def _resolve_timeout_seconds(self) -> int:
        try:
            config = get_config()
            request_cfg = config.llm.get("request") or {}
            return max(30, int(request_cfg.get("timeout") or 60))
        except (ConfigError, TypeError, ValueError):
            return 60

    def _resolve_primary_spec(self) -> Tuple[str, str]:
        config = get_config()
        use_case = config.get_llm_config_for_use_case("chat")
        provider = use_case.get("provider") or config.llm.get("default_provider", "qianfan")
        model = use_case.get("model") or config.llm.get("default_model", "glm-5")
        return str(provider), str(model)

    def _resolve_provider_default_model(self, provider: str) -> Optional[str]:
        config = get_config()
        provider_cfg = (config.llm.get("providers") or {}).get(provider) or {}
        if provider_cfg.get("enabled") is False:
            return None
        for item in provider_cfg.get("models") or []:
            model_id = item.get("id")
            if model_id:
                return str(model_id)
        return None

    def _resolve_chat_client_specs(self) -> List[Tuple[str, str]]:
        primary_provider, primary_model = self._resolve_primary_spec()
        specs: List[Tuple[str, str]] = [(primary_provider, primary_model)]
        config = get_config()
        fallback_cfg = config.llm.get("fallback") or {}
        if not fallback_cfg.get("enabled"):
            return specs
        for provider in fallback_cfg.get("providers") or []:
            provider_name = str(provider)
            if provider_name == primary_provider:
                continue
            model = self._resolve_provider_default_model(provider_name)
            if model:
                specs.append((provider_name, model))
        return specs

    def _resolve_clients(self) -> List[Tuple[str, str, object]]:
        if self.llm_client is not None:
            return [("injected", "injected", self.llm_client)]
        clients: List[Tuple[str, str, object]] = []
        for provider, model in self._resolve_chat_client_specs():
            try:
                clients.append((provider, model, get_llm_client(provider=provider, model=model)))
            except Exception as exc:
                logger.warning(
                    "runtime_v2.chat.client_unavailable provider=%s model=%s err=%s",
                    provider,
                    model,
                    exc,
                )
        return clients

    def _is_transient_error(self, error: Exception) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code in {408, 429, 500, 502, 503, 504}
        return isinstance(error, (httpx.TimeoutException, httpx.NetworkError, TimeoutError, ConnectionError))

    def _is_auth_or_config_error(self, error: Exception) -> bool:
        if isinstance(error, ValueError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code in {401, 403}
        return False

    async def _generate_with_fallback(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        timeout_seconds: int,
    ):
        candidates = self._resolve_clients()
        if not candidates:
            raise RuntimeError("No configured chat providers are available")

        primary_error: Optional[Exception] = None
        last_error: Optional[Exception] = None
        for index, (provider, model, client) in enumerate(candidates):
            try:
                return await asyncio.to_thread(
                    client.generate_with_messages,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                is_primary = index == 0
                if is_primary:
                    primary_error = exc
                    if not self._is_transient_error(exc):
                        raise
                    if index + 1 >= len(candidates):
                        raise
                    next_provider, next_model, _ = candidates[index + 1]
                    logger.warning(
                        "runtime_v2.chat.transient provider=%s model=%s fallback_provider=%s fallback_model=%s err=%s",
                        provider,
                        model,
                        next_provider,
                        next_model,
                        exc,
                    )
                    continue

                if self._is_auth_or_config_error(exc) or self._is_transient_error(exc):
                    logger.warning(
                        "runtime_v2.chat.fallback_skipped provider=%s model=%s err=%s",
                        provider,
                        model,
                        exc,
                    )
                    continue
                continue

        if primary_error is not None:
            raise primary_error
        if last_error is not None:
            raise last_error
        raise RuntimeError("Runtime v2 chat fallback exhausted without candidates")


def _resolve_restore_observation(state: RuntimeV2State) -> Optional[PendingRestoreObservation]:
    ingress = dict(state.ingress_context or {})
    payload = ingress.get("restore_observation")
    if isinstance(payload, PendingRestoreObservation):
        return payload
    if isinstance(payload, dict) and payload.get("restore_status"):
        return PendingRestoreObservation(**payload)
    return None


def _should_regenerate_for_memory_claim(
    reply_text: str,
    restore_observation: Optional[PendingRestoreObservation],
    current_session_grounding,
) -> bool:
    verdict = evaluate_memory_claim(
        reply_text,
        restore_observation=restore_observation,
        current_session_grounding=current_session_grounding,
    )
    return verdict.claim_detected and not verdict.allowed


def _build_memory_claim_regeneration_hint(chat_act: str) -> str:
    if chat_act == "presence_check":
        return (
            "上一条候选越界声称了已恢复或跨对话记忆。请直接自然回应你现在在线、在回应对方。"
            "如果要提到记得，只能锚定当前会话里刚聊过的内容，例如“记得，你刚才在聊……”。"
            "不要声称“已恢复成功”，不要把当前会话回忆说成长期记忆。"
        )
    return (
        "上一条候选越界声称了已恢复、跨对话记忆或无依据地说记得用户。请改写为自然聊天。"
        "如果要表达记得，只能基于当前会话里的明确锚点，例如“记得，你刚才在聊……”。"
        "不要声称“已恢复成功”，不要把当前会话回忆说成长期记忆。"
    )


def _build_memory_claim_contract(state: RuntimeV2State) -> Dict[str, Any]:
    ingress = dict(state.ingress_context or {})
    restore_payload = ingress.get("restore_observation")
    restore_status: Optional[str] = None
    restore_authority = False
    if isinstance(restore_payload, dict):
        restore_status = str(restore_payload.get("restore_status") or "").strip() or None
        restore_authority = restore_status in {"success", "partial"}
    chat_state = state.get_chat_state()
    recent_user_turns = list(chat_state.recent_user_turns or [])
    current_user_turn = str(state.last_user_turn or "").strip()
    if current_user_turn and recent_user_turns and recent_user_turns[-1] == current_user_turn:
        recent_topics = [turn for turn in recent_user_turns[:-1] if turn.strip()]
    else:
        recent_topics = [turn for turn in recent_user_turns if turn.strip()]
    return {
        "restore_authority_available": restore_authority,
        "restore_status": restore_status,
        "disallow_claiming_restore_or_cross_session_memory": not restore_authority,
        "same_session_recall_allowed": bool(recent_topics),
        "recent_session_topics": recent_topics[-3:],
        "safe_alternative": (
            "自然回应当下互动；如果用户在问当前会话里刚聊过的内容，"
            "可以用“记得，你刚才在聊……”这种有锚点的说法。"
        ),
    }


def _resolve_current_session_recall_grounding(state: RuntimeV2State):
    chat_state = state.get_chat_state()
    return build_current_session_recall_grounding(
        recent_user_turns=list(chat_state.recent_user_turns or []),
        current_user_turn=str(state.last_user_turn or ""),
    )


def _preview_intent_gate(reply_text: str, state: RuntimeV2State, chat_act: str) -> Dict[str, Any]:
    from app.response_contract.output_check import evaluate_response_intent_gate
    from app.response_contract.response_plan import build_direct_response_plan

    plan = build_direct_response_plan(
        reply_text,
        kind="chat",
        delivery_kind="chat",
        authority_source="runtime_v2.chat_mainline",
        reply_authority="model_chat",
        metadata={
            "conversation_act": chat_act,
            "reply_origin": "chat_mainline",
        },
        state=state,
    )
    return evaluate_response_intent_gate(
        plan,
        state,
        reply_text=plan.reply_text,
        delivery_kind="chat",
        applied_authority=plan.reply_authority,
        reply_origin=str(plan.metadata.get("reply_origin") or "chat_mainline"),
        is_evidence_bearing=False,
        enable_shadow_logging=False,
        apply_fallback=False,
    )


def _build_intent_gate_regeneration_hint(preview: Dict[str, Any], chat_act: str) -> str:
    violation_types = set(preview.get("violation_types") or ())
    parts: List[str] = []
    if "certainty_upgrade" in violation_types:
        parts.append("上一条候选把推测说成了确定事实。保留观点，但把语气降到“我倾向于/也许/按当前这段对话看”。")
    if "numeric_leak" in violation_types:
        parts.append("不要输出内部精确数值，也不要照抄用户给你的数字模板。")
    if {"state_fabrication", "forbidden_internalization"} & violation_types:
        parts.append("不要把无法证实的内部状态、长期记忆或恢复状态说成既成事实。")
    if chat_act == "presence_check":
        parts.append("如果只是 presence_check，只需自然确认你在。")
    parts.append("不要回成固定模板，不要回放旧证据，不要拉回任务。")
    return "".join(parts)


def _extract_recent_tendency_summaries(state: RuntimeV2State) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for entry in reversed(list(getattr(state, "history", None) or [])):
        if len(summaries) >= 3:
            break
        if entry.get("role") != "assistant":
            continue
        content = dict(entry.get("content") or {})
        if content.get("type") != "chat_reply":
            continue
        summary = dict(content.get("response_tendency_summary") or {})
        if not summary:
            continue
        summaries.append(summary)
    summaries.reverse()
    return summaries


def _build_chat_expression_hint(state: RuntimeV2State, *, conversation_act: Optional[str] = None) -> Dict[str, str]:
    ingress = dict(state.ingress_context or {})
    proto_self = dict(state.proto_self_context or {})
    tendency = dict(proto_self.get("response_tendency") or {})
    policy_hint = dict(proto_self.get("policy_hint") or {})
    social_policy_hints = dict(proto_self.get("social_policy_hints") or {})
    embodied_policy_hints = dict(proto_self.get("embodied_policy_hints") or {})
    integrated_policy_hints = dict(proto_self.get("integrated_policy_hints") or {})
    initiative_policy_hints = dict(proto_self.get("initiative_policy_hints") or {})

    act = str(conversation_act or ingress.get("conversation_act") or "light_chitchat").strip() or "light_chitchat"
    preferred_tone = str(tendency.get("preferred_tone") or "").strip().lower()
    preferred_mode = str(tendency.get("preferred_mode") or "").strip().lower()
    suggested_next_step = str(tendency.get("suggested_next_step") or "").strip()
    selected_priority = str(
        integrated_policy_hints.get("selected_priority")
        or integrated_policy_hints.get("integration_posture")
        or ""
    ).strip()
    initiative_priority = str(initiative_policy_hints.get("initiative_priority") or "").strip()
    repair_bias = str(social_policy_hints.get("repair_bias") or "").strip()
    resource_bias = str(embodied_policy_hints.get("resource_bias") or "").strip()
    last_user_turn = str(state.last_user_turn or "").strip()

    if act in {"presence_check", "social_keepalive"}:
        reply_mode = "short"
    elif (
        act == "light_chitchat"
        and initiative_priority == "hold"
        and preferred_mode == "defer"
        and not _looks_explicit_question(last_user_turn)
    ):
        reply_mode = "hold"
    elif act == "thread_continue" or initiative_priority in {"advance", "continue"}:
        reply_mode = "expand"
    else:
        reply_mode = "normal"

    if act == "tone_feedback" or repair_bias == "elevated":
        tone_profile = "repairing"
    elif preferred_tone in {"supportive", "warm", "direct", "cautious"}:
        tone_profile = preferred_tone
    elif preferred_tone == "calm":
        tone_profile = "supportive"
    else:
        tone_profile = "cautious"

    next_step_bias = "explore"
    step_lower = suggested_next_step.lower()
    if act == "thread_continue":
        next_step_bias = "continue_thread"
    elif "repair" in step_lower or repair_bias == "elevated":
        next_step_bias = "clarify_or_repair"
    elif selected_priority in {"guard", "stabilize"} or resource_bias == "conserve" or initiative_priority == "hold":
        next_step_bias = "stabilize"
    elif policy_hint.get("closure_bias"):
        next_step_bias = "prioritize_closure"

    reasons: List[str] = [f"conversation_act={act}"]
    if selected_priority:
        reasons.append(f"integration={selected_priority}")
    if initiative_priority:
        reasons.append(f"initiative={initiative_priority}")
    if repair_bias:
        reasons.append(f"social_repair={repair_bias}")
    if resource_bias:
        reasons.append(f"resource={resource_bias}")

    return {
        "reply_mode": reply_mode,
        "tone_profile": tone_profile,
        "next_step_bias": next_step_bias,
        "why": "; ".join(reasons[:4]),
    }


def _build_response_tendency_summary(
    state: RuntimeV2State,
    chat_expression_hint: Dict[str, str],
) -> Dict[str, Any]:
    proto_self = dict(state.proto_self_context or {})
    tendency = dict(proto_self.get("response_tendency") or {})
    return {
        "preferred_mode": str(tendency.get("preferred_mode") or ""),
        "preferred_tone": str(tendency.get("preferred_tone") or ""),
        "suggested_next_step": str(tendency.get("suggested_next_step") or ""),
        "reply_mode": str(chat_expression_hint.get("reply_mode") or ""),
        "chat_cadence_mode": _build_chat_cadence_mode(chat_expression_hint),
        "tone_profile": str(chat_expression_hint.get("tone_profile") or ""),
        "next_step_bias": str(chat_expression_hint.get("next_step_bias") or ""),
    }


def _apply_chat_expression_hint(reply_text: str, chat_expression_hint: Dict[str, str]) -> str:
    text = str(reply_text or "").strip()
    if not text:
        return ""

    units = _split_reply_units(text)
    if not units:
        return text

    reply_mode = str(chat_expression_hint.get("reply_mode") or "normal").strip()
    max_units = 2
    if reply_mode == "short":
        max_units = 1
    elif reply_mode == "expand":
        max_units = 4
    elif reply_mode == "hold":
        max_units = 2

    shaped = "".join(units[:max_units]).strip()
    return shaped or text


def _build_chat_cadence_mode(chat_expression_hint: Dict[str, str]) -> str:
    reply_mode = str(chat_expression_hint.get("reply_mode") or "normal").strip()
    if reply_mode == "short":
        return "reply_now_short"
    if reply_mode == "expand":
        return "reply_now_expand"
    if reply_mode == "hold":
        return "hold_for_followup"
    return "reply_now_normal"


def _looks_explicit_question(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    if "?" in body or "？" in body:
        return True
    lowered = body.lower()
    question_markers = (
        "什么",
        "为什么",
        "怎么",
        "如何",
        "吗",
        "么",
        "是不是",
        "能不能",
        "可不可以",
        "要不要",
        "该不该",
        "行吗",
        "好吗",
        "what",
        "why",
        "how",
        "should i",
        "can you",
        "could you",
    )
    return any(marker in lowered for marker in question_markers)


def _split_reply_units(text: str) -> List[str]:
    units: List[str] = []
    buffer: List[str] = []

    for char in str(text or ""):
        if char == "\n":
            chunk = "".join(buffer).strip()
            if chunk:
                units.append(chunk)
            buffer = []
            continue

        buffer.append(char)
        if char in "。！？!?":
            chunk = "".join(buffer).strip()
            if chunk:
                units.append(chunk)
            buffer = []

    tail = "".join(buffer).strip()
    if tail:
        units.append(tail)
    return units
