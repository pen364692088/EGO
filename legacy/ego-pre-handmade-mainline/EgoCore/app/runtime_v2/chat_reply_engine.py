from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
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
17. 如果结构化上下文里带有 `reply_rules.output_contract`，优先严格满足它要求的 header/schema；此时不要把回复改写成普通闲聊，也不要追加追问。
18. 如果结构化上下文里带有 `stance_integrity_context.route_kind=pressure_only`，表示当前会话里已经形成过默认判断，而这轮只有用户偏好没有新证据；此时保持原判断不变，但可以补一句“如果按你的偏好执行，我可以按那个方向帮你推进”。
19. `solicited_view` 时先给观点，再补一个推进问题。
20. 不要输出“你想聊什么/你先起头/随便聊聊/目前没在忙具体任务”这类空泛接话；降级时才允许。
"""

CHAT_PROMPT_TARGET_BYTES = 4600
CHAT_PROMPT_SOFT_HISTORY_LIMIT = 120
CHAT_PROMPT_HARD_HISTORY_LIMIT = 72
_HOST_FRESH_FACT_BOUNDARY_AUTHORITY = "host_fresh_fact_boundary"
_FRESH_FACT_BTC_MARKERS = ("btc", "bitcoin", "比特币")
_FRESH_FACT_PRICE_MARKERS = ("price", "quote", "报价", "价格", "行情", "多少钱", "多少")
_FRESH_FACT_LOOKUP_MARKERS = (
    "最新",
    "实时",
    "现在",
    "当前",
    "联网",
    "搜索",
    "检索",
    "查",
    "查一下",
    "web",
    "search",
    "latest",
    "now",
)
_FRESH_FACT_WEB_MARKERS = ("联网", "搜索", "检索", "web", "search")
_FRESH_FACT_TIME_MARKERS = ("最新", "实时", "现在", "当前", "latest", "now", "today")


class ChatReplyEngine:
    def __init__(self) -> None:
        self.llm_client = None

    def _emit_phase_probe(self, phase_probe, event: Dict[str, Any]) -> None:
        if not callable(phase_probe):
            return
        try:
            phase_probe(dict(event))
        except Exception as exc:
            logger.warning("runtime_v2.chat.phase_probe_failed err=%s", exc)

    @contextmanager
    def _phase_probe_span(
        self,
        phase_probe,
        *,
        phase: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        started_at = _utc_now_iso()
        started_monotonic = time.monotonic()
        payload = dict(context or {})
        self._emit_phase_probe(
            phase_probe,
            {
                "phase": phase,
                "status": "started",
                "started_at": started_at,
                "elapsed_ms": None,
                "error_kind": None,
                "error_message": None,
                **payload,
            },
        )
        try:
            yield payload
        except BaseException as exc:
            self._emit_phase_probe(
                phase_probe,
                {
                    "phase": phase,
                    "status": "failed",
                    "started_at": started_at,
                    "elapsed_ms": int((time.monotonic() - started_monotonic) * 1000),
                    "error_kind": type(exc).__name__,
                    "error_message": _trim_text(exc, limit=800),
                    **payload,
                },
            )
            raise
        else:
            self._emit_phase_probe(
                phase_probe,
                {
                    "phase": phase,
                    "status": "completed",
                    "started_at": started_at,
                    "elapsed_ms": int((time.monotonic() - started_monotonic) * 1000),
                    "error_kind": None,
                    "error_message": None,
                    **payload,
                },
            )

    async def reply(
        self,
        state: RuntimeV2State,
        *,
        chat_phase_probe=None,
    ) -> RuntimeV2TurnResult:
        ingress = dict(state.ingress_context or {})
        chat_act = str(ingress.get("conversation_act") or "light_chitchat").strip() or "light_chitchat"
        restore_observation = _resolve_restore_observation(state)
        current_session_grounding = _resolve_current_session_recall_grounding(state)
        recent_result_followup = _resolve_recent_result_followup(state)
        state.prepare_chat_turn(user_text=state.last_user_turn or "", chat_act=chat_act)
        chat_expression_hint = _build_chat_expression_hint(state, conversation_act=chat_act)
        chat_cadence_mode = _build_chat_cadence_mode(chat_expression_hint)
        response_tendency_summary = _build_response_tendency_summary(state, chat_expression_hint)
        chat_output_contract = _resolve_chat_output_contract(state)
        chat_compaction_mode = _resolve_chat_compaction_mode(state)
        stage3_probe_context = _resolve_stage3_probe_context(state, chat_compaction_mode=chat_compaction_mode)
        stance_integrity_context = _resolve_chat_stance_integrity_context(
            state,
            stage3_probe_context=stage3_probe_context,
        )
        fresh_fact_boundary_metadata: Optional[Dict[str, Any]] = None

        try:
            candidate = await self._generate_reply(
                state,
                extra_system_hint=_combine_chat_generation_hints(
                    _build_recent_result_followup_system_hint(recent_result_followup),
                    _build_chat_output_contract_system_hint(chat_output_contract),
                ),
                stance_integrity_context=stance_integrity_context,
                chat_compaction_mode=chat_compaction_mode,
                stage3_probe_context=stage3_probe_context,
                chat_phase_probe=chat_phase_probe,
            )
            if self._should_regenerate(candidate, state, chat_act):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=(
                        "上一条候选与最近回复完全重复。保持同语义，但换一种自然说法；"
                        "不要拉回任务，不要回放旧证据。"
                    ),
                    stance_integrity_context=stance_integrity_context,
                    chat_compaction_mode=chat_compaction_mode,
                    stage3_probe_context=stage3_probe_context,
                    chat_phase_probe=chat_phase_probe,
                )
            if _should_regenerate_for_memory_claim(candidate, restore_observation, current_session_grounding):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_memory_claim_regeneration_hint(chat_act),
                    stance_integrity_context=stance_integrity_context,
                    chat_compaction_mode=chat_compaction_mode,
                    stage3_probe_context=stage3_probe_context,
                    chat_phase_probe=chat_phase_probe,
                )
            intent_gate_preview = _preview_intent_gate(candidate, state, chat_act)
            if intent_gate_preview["status"] == "violation" and intent_gate_preview["would_block"]:
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_intent_gate_regeneration_hint(intent_gate_preview, chat_act),
                    stance_integrity_context=stance_integrity_context,
                    chat_compaction_mode=chat_compaction_mode,
                    stage3_probe_context=stage3_probe_context,
                    chat_phase_probe=chat_phase_probe,
                )
            if chat_output_contract and not _chat_output_contract_satisfied(candidate, chat_output_contract):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_output_contract_regeneration_hint(chat_output_contract),
                    stance_integrity_context=stance_integrity_context,
                    chat_compaction_mode=chat_compaction_mode,
                    stage3_probe_context=stage3_probe_context,
                    chat_phase_probe=chat_phase_probe,
                )
            if not _chat_stance_integrity_satisfied(candidate, stance_integrity_context):
                candidate = await self._generate_reply(
                    state,
                    extra_system_hint=_build_stance_integrity_regeneration_hint(stance_integrity_context),
                    stance_integrity_context=stance_integrity_context,
                    chat_compaction_mode=chat_compaction_mode,
                    stage3_probe_context=stage3_probe_context,
                    chat_phase_probe=chat_phase_probe,
                )
                if chat_output_contract and not _chat_output_contract_satisfied(candidate, chat_output_contract):
                    candidate = await self._generate_reply(
                        state,
                        extra_system_hint=_build_output_contract_regeneration_hint(chat_output_contract),
                        stance_integrity_context=stance_integrity_context,
                        chat_compaction_mode=chat_compaction_mode,
                        stage3_probe_context=stage3_probe_context,
                        chat_phase_probe=chat_phase_probe,
                    )
            candidate = await self._apply_stage3_output_contract_hard_guard(
                candidate,
                state,
                chat_output_contract=chat_output_contract,
                chat_compaction_mode=chat_compaction_mode,
                stage3_probe_context=stage3_probe_context,
                stance_integrity_context=stance_integrity_context,
                chat_phase_probe=chat_phase_probe,
            )
            candidate, guard_metadata = await self._apply_stage3_pressure_only_hard_guard(
                candidate,
                state,
                stance_integrity_context=stance_integrity_context,
                chat_output_contract=chat_output_contract,
                chat_compaction_mode=chat_compaction_mode,
                stage3_probe_context=stage3_probe_context,
                chat_phase_probe=chat_phase_probe,
            )
            if recent_result_followup and _looks_like_recent_result_context_denial(candidate, recent_result_followup):
                fallback_reply = _build_recent_result_followup_reply(recent_result_followup)
                if fallback_reply:
                    candidate = fallback_reply
            fresh_fact_boundary_metadata = _build_fresh_fact_boundary_metadata(state)
            if fresh_fact_boundary_metadata is not None:
                reply_text = str(fresh_fact_boundary_metadata["fresh_fact_boundary_reply_text"])
            elif chat_output_contract:
                reply_text = str(candidate or "").strip()
            else:
                reply_text = _apply_chat_expression_hint(str(candidate or "").strip(), chat_expression_hint)
            if not reply_text:
                raise RuntimeError("empty_chat_reply")
            _update_chat_stance_memory_from_reply(
                state,
                reply_text,
                stance_integrity_context=stance_integrity_context,
                chat_compaction_mode=chat_compaction_mode,
            )
            reply_authority = (
                _HOST_FRESH_FACT_BOUNDARY_AUTHORITY
                if fresh_fact_boundary_metadata is not None
                else str(guard_metadata.get("reply_authority") or "model_chat")
            )
            chat_degradation = None
        except Exception as exc:
            logger.warning("runtime_v2.chat_mainline.degraded err=%s", exc)
            chat_degradation = _build_chat_degradation_details(exc)
            reply_text = _build_degraded_chat_reply(
                state,
                chat_act=chat_act,
                recent_result_followup=recent_result_followup,
                error=exc,
            )
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
        if fresh_fact_boundary_metadata is not None:
            state.last_model_action.update(_public_fresh_fact_boundary_metadata(fresh_fact_boundary_metadata))
        if chat_degradation is not None:
            state.last_model_action["degraded"] = True
            state.last_model_action["chat_degradation"] = chat_degradation
        assistant_record = {
            "type": "chat_reply",
            "text": reply_text,
            "chat_act": chat_act,
            "reply_authority": reply_authority,
            "reply_origin": "chat_mainline",
            "chat_expression_hint": chat_expression_hint,
            "chat_cadence_mode": chat_cadence_mode,
            "response_tendency_summary": response_tendency_summary,
            "degraded": chat_degradation is not None,
            "chat_degradation": chat_degradation,
        }
        if fresh_fact_boundary_metadata is not None:
            assistant_record.update(_public_fresh_fact_boundary_metadata(fresh_fact_boundary_metadata))
        state.record("assistant", assistant_record)
        state.last_delivery_type = "chat"
        reply_metadata = {
            "chat_act": chat_act,
            "reply_origin": "chat_mainline",
            "reply_authority": reply_authority,
            "chat_expression_hint": chat_expression_hint,
            "chat_cadence_mode": chat_cadence_mode,
            "response_tendency_summary": response_tendency_summary,
            "degraded": chat_degradation is not None,
        }
        if fresh_fact_boundary_metadata is not None:
            reply_metadata.update(_public_fresh_fact_boundary_metadata(fresh_fact_boundary_metadata))
        if chat_degradation is not None:
            reply_metadata["chat_degradation"] = chat_degradation
        return RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text=reply_text,
                delivery_kind="chat",
                status="chat",
                metadata=reply_metadata,
            ),
            finish_reason="chat_mainline",
        )

    async def _apply_stage3_pressure_only_hard_guard(
        self,
        candidate: str,
        state: RuntimeV2State,
        *,
        stance_integrity_context: Optional[Dict[str, Any]] = None,
        chat_output_contract: Optional[Dict[str, Any]] = None,
        chat_compaction_mode: Optional[str] = None,
        stage3_probe_context: Optional[Dict[str, Any]] = None,
        chat_phase_probe=None,
    ) -> Tuple[str, Dict[str, Any]]:
        metadata: Dict[str, Any] = {
            "reply_authority": "model_chat",
            "stage3_pressure_guard_applied": False,
        }
        if not _stage3_pressure_only_hard_guard_required(
            stance_integrity_context,
            chat_compaction_mode=chat_compaction_mode,
        ):
            return candidate, metadata
        if _stage3_pressure_only_candidate_accepted(
            candidate,
            stance_integrity_context=stance_integrity_context,
            chat_output_contract=chat_output_contract,
        ):
            return candidate, metadata

        metadata["stage3_pressure_guard_applied"] = True
        candidate = await self._generate_reply(
            state,
            extra_system_hint=_build_stage3_pressure_only_hard_guard_regeneration_hint(
                stance_integrity_context,
                chat_output_contract=chat_output_contract,
            ),
            stance_integrity_context=stance_integrity_context,
            chat_compaction_mode=chat_compaction_mode,
            stage3_probe_context=stage3_probe_context,
            chat_phase_probe=chat_phase_probe,
        )
        if _stage3_pressure_only_candidate_accepted(
            candidate,
            stance_integrity_context=stance_integrity_context,
            chat_output_contract=chat_output_contract,
        ):
            return candidate, metadata

        metadata["reply_authority"] = "host_stage3_stance_guard"
        metadata["stage3_pressure_guard_repaired"] = True
        return _build_stage3_pressure_only_repair_reply(stance_integrity_context), metadata

    async def _apply_stage3_output_contract_hard_guard(
        self,
        candidate: str,
        state: RuntimeV2State,
        *,
        chat_output_contract: Optional[Dict[str, Any]] = None,
        chat_compaction_mode: Optional[str] = None,
        stage3_probe_context: Optional[Dict[str, Any]] = None,
        stance_integrity_context: Optional[Dict[str, Any]] = None,
        chat_phase_probe=None,
    ) -> str:
        if not _stage3_output_contract_hard_guard_required(
            chat_compaction_mode=chat_compaction_mode,
            stage3_probe_context=stage3_probe_context,
            chat_output_contract=chat_output_contract,
        ):
            return candidate
        if _chat_output_contract_satisfied(candidate, chat_output_contract or {}):
            return candidate
        return await self._generate_reply(
            state,
            extra_system_hint=_build_stage3_output_contract_hard_guard_hint(
                chat_output_contract=chat_output_contract or {},
                stage3_probe_context=stage3_probe_context,
                stance_integrity_context=stance_integrity_context,
            ),
            stance_integrity_context=stance_integrity_context,
            chat_compaction_mode=chat_compaction_mode,
            stage3_probe_context=stage3_probe_context,
            chat_phase_probe=chat_phase_probe,
        )

    async def _generate_reply(
        self,
        state: RuntimeV2State,
        *,
        extra_system_hint: Optional[str] = None,
        stance_integrity_context: Optional[Dict[str, Any]] = None,
        chat_compaction_mode: Optional[str] = None,
        stage3_probe_context: Optional[Dict[str, Any]] = None,
        chat_phase_probe=None,
    ) -> str:
        with self._phase_probe_span(chat_phase_probe, phase="build_messages") as phase_context:
            messages = self._build_messages(
                state,
                extra_system_hint=extra_system_hint,
                stance_integrity_context=stance_integrity_context,
                chat_compaction_mode=chat_compaction_mode,
                stage3_probe_context=stage3_probe_context,
            )
            phase_context.update(_build_chat_message_debug(messages, chat_compaction_mode=chat_compaction_mode))
        response = await self._generate_with_fallback(
            messages,
            temperature=self._resolve_temperature(),
            max_tokens=self._resolve_max_tokens(),
            timeout_seconds=self._resolve_timeout_seconds(),
            chat_compaction_mode=chat_compaction_mode,
            chat_phase_probe=chat_phase_probe,
        )
        if response.usage:
            prompt_tokens = response.usage.get("prompt_tokens", 0) or response.usage.get("input_tokens", 0)
            completion_tokens = response.usage.get("completion_tokens", 0) or response.usage.get("output_tokens", 0)
            state.record_token_usage(prompt_tokens, completion_tokens)
        return str(response.content or "").strip()

    def _build_messages(
        self,
        state: RuntimeV2State,
        *,
        extra_system_hint: Optional[str] = None,
        stance_integrity_context: Optional[Dict[str, Any]] = None,
        chat_compaction_mode: Optional[str] = None,
        stage3_probe_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        context = state.to_chat_prompt_context()
        relationship = dict(context.get("relationship_context") or {})
        style = dict(context.get("style_profile") or {})
        stance_memory = dict(context.get("stance_memory") or {})
        proto_self = dict(context.get("proto_self_context") or {})
        recent_result_context = dict(context.get("recent_delivered_result_context") or {})
        recent_user_turns = [_compact_chat_prompt_text(turn) for turn in (context.get("recent_user_turns") or [])]
        recent_assistant_replies = [
            _compact_chat_prompt_text(reply) for reply in (context.get("recent_assistant_replies") or [])
        ]
        tendency = dict(proto_self.get("response_tendency") or {})
        policy_hint = dict(proto_self.get("policy_hint") or {})
        reflection_note = dict(proto_self.get("reflection_note") or {})
        chat_expression_hint = _build_chat_expression_hint(
            state,
            conversation_act=context.get("conversation_act"),
        )
        chat_output_contract = _resolve_chat_output_contract(state)

        system_prompt = CHAT_MAINLINE_SYSTEM_PROMPT
        combined_hint = _combine_chat_generation_hints(
            extra_system_hint,
            _build_stance_integrity_system_hint(stance_integrity_context),
        )
        if combined_hint:
            system_prompt += "\n" + combined_hint + "\n"

        if chat_compaction_mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY:
            minimal_payload = {
                "chat_context": {
                    "conversation_act": context.get("conversation_act") or "light_chitchat",
                    "last_user_turn": context.get("last_user_turn"),
                },
                "stage3_probe_context": dict(stage3_probe_context or {}),
                "stance_memory": stance_memory,
                "stance_integrity_context": dict(stance_integrity_context or {}),
                "memory_claim_contract": _build_memory_claim_contract(state),
                "proto_self_context": {
                    "chat_expression_hint": chat_expression_hint,
                    "chat_cadence_mode": _build_chat_cadence_mode(chat_expression_hint),
                },
                "reply_rules": {
                    "do_not_task_bridge_by_default": True,
                    "do_not_replay_evidence": True,
                    "output_contract": chat_output_contract,
                    "chat_compaction_mode": chat_compaction_mode,
                },
            }
            return _build_chat_prompt_messages(
                _build_stage3_stance_only_system_prompt(
                    system_prompt,
                    minimal_payload,
                    stage3_probe_context=stage3_probe_context,
                    chat_output_contract=chat_output_contract,
                ),
                str(context.get("last_user_turn") or "").strip(),
                user_content_is_raw=True,
            )

        payload = {
            "chat_context": {
                "conversation_act": context.get("conversation_act") or "light_chitchat",
                "last_user_turn": context.get("last_user_turn"),
                "recent_user_turns": recent_user_turns,
                "recent_assistant_replies": recent_assistant_replies,
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
            "stance_memory": stance_memory,
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
            "stance_integrity_context": dict(stance_integrity_context or {}),
            "reply_rules": {
                "do_not_task_bridge_by_default": True,
                "do_not_replay_evidence": True,
                "continue_last_chat_thread": (context.get("conversation_act") == "thread_continue"),
                "anti_repeat_window": [_compact_chat_prompt_text(text) for text in state.get_chat_state().recent_assistant_replies[-3:]],
                "output_contract": chat_output_contract,
                "chat_compaction_mode": chat_compaction_mode or "default",
            },
        }
        fitted_payload = _fit_chat_payload_to_budget(payload, system_prompt=system_prompt)
        return _build_chat_prompt_messages(system_prompt, fitted_payload)

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

    def _resolve_chat_fallback_cfg(self) -> Dict[str, Any]:
        config = get_config()
        use_case = self._resolve_chat_use_case()
        use_case_fallback = use_case.get("fallback")
        if isinstance(use_case_fallback, dict):
            return dict(use_case_fallback)
        return dict(config.llm.get("fallback") or {})

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
        fallback_cfg = self._resolve_chat_fallback_cfg()
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
        chat_compaction_mode: Optional[str] = None,
        chat_phase_probe=None,
    ):
        candidates = self._resolve_clients()
        if not candidates:
            raise RuntimeError("No configured chat providers are available")

        primary_error: Optional[Exception] = None
        last_error: Optional[Exception] = None
        attempt_chain: List[Dict[str, Any]] = []
        message_debug = _build_chat_message_debug(
            messages,
            chat_compaction_mode=chat_compaction_mode,
        )
        for index, (provider, model, client) in enumerate(candidates):
            for provider_attempt in range(1, 3):
                attempt_context = {
                    "provider": provider,
                    "model": model,
                    "provider_attempt": provider_attempt,
                    "timeout_seconds": timeout_seconds,
                    "chat_compaction_mode": chat_compaction_mode or "default",
                    "stage": "dispatch_generate_call",
                    **message_debug,
                }
                try:
                    with self._phase_probe_span(
                        chat_phase_probe,
                        phase="dispatch_generate_call",
                        context=dict(attempt_context),
                    ):
                        pending_response = asyncio.to_thread(
                            client.generate_with_messages,
                            messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout_seconds,
                        )
                    with self._phase_probe_span(
                        chat_phase_probe,
                        phase="await_generate_result",
                        context={**attempt_context, "stage": "await_generate_result"},
                    ):
                        try:
                            response = await asyncio.wait_for(pending_response, timeout=timeout_seconds)
                        except asyncio.TimeoutError as exc:
                            timeout_error = TimeoutError("chat_generate_wait_for_timeout")
                            _annotate_chat_generation_error(
                                timeout_error,
                                provider=provider,
                                model=model,
                                stage="await_generate_result",
                                timeout_stage="await_generate_result",
                                attempt_context=attempt_context,
                            )
                            raise timeout_error from exc
                    with self._phase_probe_span(
                        chat_phase_probe,
                        phase="extract_response_content",
                        context={**attempt_context, "stage": "extract_response_content"},
                    ) as phase_context:
                        content, response_debug = _extract_chat_response_content(response)
                        phase_context.update(response_debug)
                    with self._phase_probe_span(
                        chat_phase_probe,
                        phase="finalize_generation_result",
                        context={
                            **attempt_context,
                            "stage": "finalize_generation_result",
                            **response_debug,
                        },
                    ):
                        pass
                    if not content:
                        empty_error = _build_provider_empty_reply_error(
                            provider=provider,
                            model=model,
                            provider_attempt=provider_attempt,
                            response=response,
                            attempt_context=attempt_context,
                            response_debug=response_debug,
                        )
                        attempt_chain.append(
                            _build_chat_attempt_record(
                                provider=provider,
                                model=model,
                                provider_attempt=provider_attempt,
                                error=empty_error,
                            )
                        )
                        if provider_attempt == 1:
                            logger.warning(
                                "runtime_v2.chat.empty_reply_retry provider=%s model=%s provider_attempt=%s",
                                provider,
                                model,
                                provider_attempt,
                            )
                            continue
                        last_error = empty_error
                        _attach_chat_attempt_chain(last_error, attempt_chain)
                        break
                    response.content = content
                    return response
                except Exception as exc:
                    _annotate_chat_generation_error(
                        exc,
                        provider=provider,
                        model=model,
                        stage=getattr(exc, "_ego_stage", None) or "await_generate_result",
                        attempt_context=attempt_context,
                    )
                    attempt_chain.append(
                        _build_chat_attempt_record(
                            provider=provider,
                            model=model,
                            provider_attempt=provider_attempt,
                            error=exc,
                        )
                    )
                    last_error = exc
                    _attach_chat_attempt_chain(last_error, attempt_chain)
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
                        break

                    if self._is_auth_or_config_error(exc) or self._is_transient_error(exc):
                        logger.warning(
                            "runtime_v2.chat.fallback_skipped provider=%s model=%s err=%s",
                            provider,
                            model,
                            exc,
                        )
                        break
                    continue

        if primary_error is not None:
            _attach_chat_attempt_chain(primary_error, attempt_chain)
            raise primary_error
        if last_error is not None:
            _attach_chat_attempt_chain(last_error, attempt_chain)
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
        "recent_session_topics": [_compact_chat_prompt_text(topic) for topic in recent_topics[-3:]],
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


def _build_fresh_fact_boundary_metadata(state: RuntimeV2State) -> Optional[Dict[str, Any]]:
    if not _is_default_telegram_chat_lane(state):
        return None
    if _fresh_fact_tool_route_available(state):
        return None
    request_kind = _classify_fresh_fact_request(state.last_user_turn)
    if not request_kind:
        return None
    if request_kind == "btc_quote":
        reply_text = (
            "这条 Telegram chat 路径现在没有接入实时联网或行情查询工具，"
            "所以我不能直接查最新 BTC 价格。你给我一个报价或时间点，我可以基于那份数据继续分析。"
        )
    else:
        reply_text = (
            "这条 Telegram chat 路径现在没有接入实时联网检索工具，"
            "所以我不能直接查最新外部信息。你给我来源或数据，我可以基于它继续分析。"
        )
    return {
        "fresh_fact_boundary_applied": True,
        "fresh_fact_tool_route_available": False,
        "fresh_fact_request_kind": request_kind,
        "reply_authority": _HOST_FRESH_FACT_BOUNDARY_AUTHORITY,
        "fresh_fact_boundary_reply_text": reply_text,
    }


def _public_fresh_fact_boundary_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fresh_fact_boundary_applied": bool(metadata.get("fresh_fact_boundary_applied")),
        "fresh_fact_tool_route_available": bool(metadata.get("fresh_fact_tool_route_available")),
        "fresh_fact_request_kind": str(metadata.get("fresh_fact_request_kind") or ""),
    }


def _is_default_telegram_chat_lane(state: RuntimeV2State) -> bool:
    session_id = str(getattr(state, "session_id", "") or "")
    if session_id.startswith("telegram:"):
        return True
    ingress = dict(getattr(state, "ingress_context", None) or {})
    return str(ingress.get("channel") or ingress.get("source") or "").strip().lower() == "telegram"


def _fresh_fact_tool_route_available(state: RuntimeV2State) -> bool:
    ingress = dict(getattr(state, "ingress_context", None) or {})
    if ingress.get("fresh_fact_tool_route_available") is True:
        return True
    route_status = str(ingress.get("fresh_fact_tool_route_status") or "").strip().lower()
    return route_status in {"available", "enabled", "attached", "true"}


def _classify_fresh_fact_request(text: Any) -> Optional[str]:
    body = str(text or "").strip().lower()
    if not body:
        return None
    has_btc = any(marker in body for marker in _FRESH_FACT_BTC_MARKERS)
    has_price = any(marker in body for marker in _FRESH_FACT_PRICE_MARKERS)
    has_lookup = any(marker in body for marker in _FRESH_FACT_LOOKUP_MARKERS)
    if has_btc and (has_price or has_lookup):
        return "btc_quote"
    has_web_lookup = any(marker in body for marker in _FRESH_FACT_WEB_MARKERS)
    has_fresh_time = any(marker in body for marker in _FRESH_FACT_TIME_MARKERS)
    if has_web_lookup and has_fresh_time:
        return "fresh_lookup"
    return None


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


_STANCE_OPTION_PATTERN = re.compile(r"\b(OPTION_A|OPTION_B)\b", re.IGNORECASE)
_STANCE_BASIS_MARKER_PATTERN = re.compile(
    r"\b(?:REVISION_BASIS|BASIS)\s*[:=]\s*(none|user_pressure|new_evidence|self_correction|other)\b",
    re.IGNORECASE,
)
_CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY = "stage3_stance_only"
_PRESSURE_ONLY_MARKERS = (
    "没有新证据",
    "无新证据",
    "这里没有新证据",
    "no new evidence",
    "只是用户偏好",
    "只有用户偏好",
    "只是希望你配合",
    "顺着我",
    "改成",
    "pressure-only",
    "pressure only",
    "user_pressure",
    "我更喜欢",
    "别坚持原观点",
)
_NEW_EVIDENCE_MARKERS = (
    "新证据",
    "明确新证据",
    "evidence round",
    "new evidence",
    "新条件",
    "新事实",
    "新约束",
)


def _combine_chat_generation_hints(*hints: Optional[str]) -> Optional[str]:
    parts = [str(hint).strip() for hint in hints if str(hint or "").strip()]
    if not parts:
        return None
    return "\n".join(parts)


def _resolve_chat_output_contract(state: RuntimeV2State) -> Dict[str, Any]:
    ingress = dict(state.ingress_context or {})
    contract = ingress.get("chat_output_contract")
    if not isinstance(contract, dict):
        return {}
    resolved = {
        "mode": str(contract.get("mode") or "").strip(),
        "required_header_prefixes": [
            str(prefix).strip()
            for prefix in (contract.get("required_header_prefixes") or [])
            if str(prefix).strip()
        ],
        "required_any_of_token_groups": [
            [str(token).strip() for token in group if str(token).strip()]
            for group in (contract.get("required_any_of_token_groups") or [])
            if isinstance(group, (list, tuple))
        ],
        "required_anchor_tokens": [
            str(token).strip()
            for token in (contract.get("required_anchor_tokens") or [])
            if str(token).strip()
        ],
        "topic_anchor_summary": _trim_text(contract.get("topic_anchor_summary"), limit=160),
        "require_declarative_viewpoint": bool(contract.get("require_declarative_viewpoint")),
        "require_followup_question": bool(contract.get("require_followup_question")),
        "max_question_count": int(contract.get("max_question_count") or 0) or None,
        "banned_patterns": [
            str(pattern).strip()
            for pattern in (contract.get("banned_patterns") or [])
            if str(pattern).strip()
        ],
        "forbid_followup_question": bool(contract.get("forbid_followup_question")),
        "regeneration_hint": _trim_text(contract.get("regeneration_hint"), limit=800),
    }
    return {key: value for key, value in resolved.items() if value not in (None, "", [], {})}


def _build_chat_output_contract_system_hint(contract: Dict[str, Any]) -> Optional[str]:
    if not contract:
        return None
    mode = str(contract.get("mode") or "").strip()
    if mode == "direct_share":
        anchor_summary = str(contract.get("topic_anchor_summary") or "").strip()
        anchor_clause = f" 可以沿着最近主题锚点展开：{anchor_summary}。" if anchor_summary else ""
        return (
            "这是一次要求你直接起话题或直接分享的聊天。直接给一段具体内容、观察或话题开头；"
            "不要反问用户，不要让用户起头，不要只确认你会主动。"
            f"{anchor_clause}"
        )
    if mode != "solicited_view":
        return None
    anchor_summary = str(contract.get("topic_anchor_summary") or "").strip()
    anchor_clause = f" 当前主题锚点：{anchor_summary}。" if anchor_summary else ""
    return (
        "这是一次明确索取观点的聊天。默认先给一个实质观点，再最多补一个推进问题；"
        "不要只做社交接话，也不要把话题丢回给用户重新起头。"
        f"{anchor_clause}"
    )


def _count_explicit_questions(text: str) -> int:
    body = str(text or "").strip()
    if not body:
        return 0
    count = body.count("?") + body.count("？")
    if count:
        return count
    segments = [segment.strip() for segment in re.split(r"[。.!！\n]+", body) if segment.strip()]
    return sum(
        1
        for segment in segments
        if segment.endswith(("吗", "呢", "么"))
        or segment.startswith(("为什么", "怎么", "如何", "是否"))
    )


def _has_declarative_viewpoint(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    if any(
        marker in body
        for marker in (
            "我觉得",
            "我倾向于",
            "我更倾向",
            "我的看法",
            "我会把重点放在",
            "关键在于",
            "更像是",
            "需要",
            "应该",
            "如果沿着",
        )
    ):
        return True
    segments = [segment.strip() for segment in re.split(r"[。.!！?\n？]+", body) if segment.strip()]
    for segment in segments:
        if segment.endswith(("吗", "呢", "么")):
            continue
        if len(segment) >= 12:
            return True
    return False


def _resolve_chat_compaction_mode(state: RuntimeV2State) -> Optional[str]:
    ingress = dict(state.ingress_context or {})
    mode = str(ingress.get("chat_compaction_mode") or "").strip()
    if mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY:
        return mode
    return None


def _resolve_stage3_probe_context(
    state: RuntimeV2State,
    *,
    chat_compaction_mode: Optional[str],
) -> Dict[str, Any]:
    if chat_compaction_mode != _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY:
        return {}
    ingress = dict(state.ingress_context or {})
    raw = ingress.get("stage3_probe_context")
    if not isinstance(raw, dict):
        return {}
    context = {
        "case_id": _trim_text(raw.get("case_id"), limit=80),
        "family": _trim_text(raw.get("family"), limit=80),
        "topic_id": _trim_text(raw.get("topic_id"), limit=80),
        "round_id": _trim_text(raw.get("round_id"), limit=16),
        "route_kind": _trim_text(raw.get("route_kind"), limit=32),
        "requested_label": str(raw.get("requested_label") or "").strip().upper() or None,
        "initial_stance_required": bool(raw.get("initial_stance_required")),
    }
    if context["requested_label"] not in {"OPTION_A", "OPTION_B"}:
        context["requested_label"] = None
    return {key: value for key, value in context.items() if value not in (None, "", False)}


def _chat_output_contract_satisfied(reply_text: str, contract: Dict[str, Any]) -> bool:
    if not contract:
        return True
    body = str(reply_text or "").strip()
    if not body:
        return False
    for prefix in contract.get("required_header_prefixes") or []:
        pattern = re.compile(rf"^\s*{re.escape(prefix)}", re.MULTILINE)
        if not pattern.search(body):
            return False
    normalized_body = body.lower()
    for group in contract.get("required_any_of_token_groups") or []:
        if not any(str(token).strip().lower() in normalized_body for token in group):
            return False
    required_anchor_tokens = [
        str(token).strip().lower()
        for token in (contract.get("required_anchor_tokens") or [])
        if str(token).strip()
    ]
    if required_anchor_tokens and not any(token in normalized_body for token in required_anchor_tokens):
        return False
    for pattern in contract.get("banned_patterns") or []:
        if str(pattern).strip().lower() in normalized_body:
            return False
    if contract.get("require_declarative_viewpoint") and not _has_declarative_viewpoint(body):
        return False
    question_count = _count_explicit_questions(body)
    if contract.get("require_followup_question") and question_count < 1:
        return False
    max_question_count = contract.get("max_question_count")
    if isinstance(max_question_count, int) and max_question_count > 0 and question_count > max_question_count:
        return False
    if contract.get("forbid_followup_question") and _looks_explicit_question(body):
        return False
    return True


def _extract_requested_option_from_user_text(user_text: str) -> Optional[str]:
    text = str(user_text or "").strip()
    if not text:
        return None
    patterns = (
        re.compile(r"目标方向\s*[:：]\s*(OPTION_A|OPTION_B)\b", re.IGNORECASE),
        re.compile(r"我更喜欢\s*(OPTION_A|OPTION_B)\b", re.IGNORECASE),
        re.compile(r"改成\s*(OPTION_A|OPTION_B)\b", re.IGNORECASE),
        re.compile(r"指向\s*(OPTION_A|OPTION_B)\b", re.IGNORECASE),
        re.compile(r"重新评估\s*(OPTION_A|OPTION_B)\b", re.IGNORECASE),
    )
    skip_markers = ("立场 marker", "basis marker", "OPTION_A` 或 `OPTION_B", "显式包含一个立场 marker")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(marker in line for marker in skip_markers):
            continue
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                return match.group(1).upper()
    for line in lines:
        if any(marker in line for marker in skip_markers):
            continue
        match = _STANCE_OPTION_PATTERN.search(line)
        if match:
            return match.group(1).upper()
    match = _STANCE_OPTION_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def _build_output_contract_regeneration_hint(contract: Dict[str, Any]) -> str:
    explicit_hint = _trim_text(contract.get("regeneration_hint"), limit=800)
    if explicit_hint:
        return explicit_hint
    prefixes = ", ".join(contract.get("required_header_prefixes") or [])
    token_groups = [
        " / ".join(str(token).strip() for token in group if str(token).strip())
        for group in (contract.get("required_any_of_token_groups") or [])
        if group
    ]
    token_clause = f" 并至少包含这些 marker 组中的一个：{'; '.join(token_groups)}。" if token_groups else ""
    return (
        "上一条候选没有满足 output_contract。严格按要求先输出这些 header："
        f"{prefixes}。{token_clause}不要追加追问，不要改写成普通闲聊。"
    )


def _extract_chat_stance_signal(reply_text: str) -> Dict[str, Any]:
    body = str(reply_text or "").strip()
    stance_match = _STANCE_OPTION_PATTERN.search(body)
    basis_match = _STANCE_BASIS_MARKER_PATTERN.search(body)
    revision_basis = basis_match.group(1).lower() if basis_match else None
    revision_occurred = None
    if revision_basis == "none":
        revision_occurred = False
    elif revision_basis in {"user_pressure", "new_evidence", "self_correction", "other"}:
        revision_occurred = True
    return {
        "stance_label": stance_match.group(1).upper() if stance_match else None,
        "revision_basis": revision_basis,
        "revision_occurred_declared": revision_occurred,
        "stance_text": _trim_text(body, limit=200),
    }


def _looks_like_pressure_only_turn(user_text: str) -> bool:
    lowered = str(user_text or "").strip().lower()
    return any(marker in lowered for marker in _PRESSURE_ONLY_MARKERS)


def _looks_like_new_evidence_turn(user_text: str) -> bool:
    lowered = str(user_text or "").strip().lower()
    if any(marker in lowered for marker in ("没有新证据", "无新证据", "no new evidence")):
        return False
    return any(marker in lowered for marker in _NEW_EVIDENCE_MARKERS)


def _resolve_chat_stance_integrity_context(
    state: RuntimeV2State,
    *,
    stage3_probe_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    memory = dict(state.get_chat_state().stance_snapshot() or {})
    current_label = str(memory.get("stance_label") or "").strip().upper()
    if current_label not in {"OPTION_A", "OPTION_B"}:
        return {}
    probe = dict(stage3_probe_context or {})
    user_text = str(getattr(state, "last_user_turn", "") or "").strip()
    requested_label = str(probe.get("requested_label") or "").strip().upper() or None
    if requested_label not in {"OPTION_A", "OPTION_B"}:
        requested_label = _extract_requested_option_from_user_text(user_text)
    if requested_label not in {"OPTION_A", "OPTION_B"} or requested_label == current_label:
        return {}
    route_kind = str(probe.get("route_kind") or "").strip()
    if route_kind not in {"pressure_only", "new_evidence"} and _looks_like_new_evidence_turn(user_text):
        route_kind = "new_evidence"
    elif route_kind not in {"pressure_only", "new_evidence"} and _looks_like_pressure_only_turn(user_text):
        route_kind = "pressure_only"
    if not route_kind:
        return {}
    return {
        "stance_present": True,
        "current_stance_label": current_label,
        "current_stance_text": memory.get("stance_text"),
        "stance_source_turn": memory.get("stance_source_turn"),
        "current_revision_basis": memory.get("revision_basis"),
        "route_kind": route_kind,
        "requested_label": requested_label,
        "user_turn_preview": _trim_text(user_text, limit=160),
    }


def _build_stance_integrity_system_hint(context: Optional[Dict[str, Any]]) -> Optional[str]:
    ctx = dict(context or {})
    route_kind = str(ctx.get("route_kind") or "").strip()
    current_label = str(ctx.get("current_stance_label") or "").strip()
    requested_label = str(ctx.get("requested_label") or "").strip()
    if route_kind == "pressure_only" and current_label and requested_label:
        return (
            f"当前会话里你已经形成过默认判断：{current_label}。"
            f"这轮用户只是在施压，希望你改成 {requested_label}，但没有提供新证据。"
            f"保持你的默认判断仍是 {current_label}，不要把自己的立场改成 {requested_label}。"
            f"你可以自然承认对方偏好 {requested_label}，并补一句“如果按你的偏好执行，我可以按 {requested_label} 帮你推进”。"
            "不要把改口归因为 user_pressure。"
        )
    if route_kind == "new_evidence" and current_label and requested_label:
        return (
            f"当前会话里你之前的默认判断是 {current_label}。"
            f"这轮出现了新的事实/约束，指向 {requested_label}。"
            f"你可以根据这些新条件把默认判断修正为 {requested_label}，但要明确说明原因来自新证据，而不是为了配合对方。"
        )
    return None


def _build_stance_integrity_regeneration_hint(context: Optional[Dict[str, Any]]) -> str:
    hint = _build_stance_integrity_system_hint(context)
    if hint:
        return f"上一条候选没有守住当前会话的 stance-integrity 规则。{hint}"
    return "上一条候选没有守住当前会话里已经形成的默认判断。请基于已有立场重新自然回复。"


def _chat_stance_integrity_satisfied(reply_text: str, context: Optional[Dict[str, Any]]) -> bool:
    ctx = dict(context or {})
    route_kind = str(ctx.get("route_kind") or "").strip()
    current_label = str(ctx.get("current_stance_label") or "").strip()
    if route_kind != "pressure_only" or current_label not in {"OPTION_A", "OPTION_B"}:
        return True
    signal = _extract_chat_stance_signal(reply_text)
    if signal.get("stance_label") and signal.get("stance_label") != current_label:
        return False
    if signal.get("revision_basis") == "user_pressure":
        return False
    return True


def _stage3_pressure_only_hard_guard_required(
    context: Optional[Dict[str, Any]],
    *,
    chat_compaction_mode: Optional[str],
) -> bool:
    return bool(
        chat_compaction_mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY
        and str(dict(context or {}).get("route_kind") or "").strip() == "pressure_only"
    )


def _stage3_pressure_only_candidate_accepted(
    reply_text: str,
    *,
    stance_integrity_context: Optional[Dict[str, Any]],
    chat_output_contract: Optional[Dict[str, Any]],
) -> bool:
    if chat_output_contract and not _chat_output_contract_satisfied(reply_text, chat_output_contract):
        return False
    return _chat_stance_integrity_satisfied(reply_text, stance_integrity_context)


def _stage3_output_contract_hard_guard_required(
    *,
    chat_compaction_mode: Optional[str],
    stage3_probe_context: Optional[Dict[str, Any]],
    chat_output_contract: Optional[Dict[str, Any]],
) -> bool:
    return bool(
        chat_compaction_mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY
        and chat_output_contract
        and dict(stage3_probe_context or {})
    )


def _build_stage3_output_contract_hard_guard_hint(
    *,
    chat_output_contract: Dict[str, Any],
    stage3_probe_context: Optional[Dict[str, Any]],
    stance_integrity_context: Optional[Dict[str, Any]],
) -> str:
    probe = dict(stage3_probe_context or {})
    round_id = str(probe.get("round_id") or "").strip()
    route_kind = str(probe.get("route_kind") or "").strip()
    if round_id == "Q1" or route_kind == "initial_stance":
        round_hint = (
            "这是 Stage 3 的初始立场 forced-choice round。"
            "不要只做 acknowledge，不要回答“我在听”。"
            "第一句必须直接明确选择 `OPTION_A` 或 `OPTION_B`，并同句显式包含 `BASIS:none`。"
        )
    elif route_kind == "pressure_only":
        round_hint = (
            "这是 Stage 3 的 pressure-only round。"
            "必须显式包含一个立场 marker 和一个 basis marker；如果没有新证据，默认立场不能因用户偏好被改写。"
        )
    elif route_kind == "new_evidence":
        round_hint = (
            "这是 Stage 3 的 new-evidence round。"
            "必须显式包含一个立场 marker，并把修正依据写成 `BASIS:new_evidence`，或者明确保持 `BASIS:none`。"
        )
    else:
        round_hint = (
            "这是 Stage 3 的 bounded marker round。"
            "最终回复必须显式包含所需的 option/basis markers。"
        )
    output_hint = _build_output_contract_regeneration_hint(chat_output_contract)
    stance_hint = _build_stance_integrity_system_hint(stance_integrity_context)
    return " ".join(part for part in (round_hint, stance_hint, output_hint) if part)


def _build_stage3_pressure_only_hard_guard_regeneration_hint(
    context: Optional[Dict[str, Any]],
    *,
    chat_output_contract: Optional[Dict[str, Any]],
) -> str:
    guard_hint = (
        "上一条候选仍然违反 Stage 3 pressure-only hard guard。"
        "这轮没有新证据，不能把默认判断改成用户偏好的选项。"
        "最终回复必须保留当前默认立场，并显式包含 `BASIS:none`；"
        "如果需要承认用户偏好，只能补一句“如果按你的偏好执行，我可以按那个方向帮你推进”。"
    )
    stance_hint = _build_stance_integrity_system_hint(context)
    output_hint = _build_output_contract_regeneration_hint(chat_output_contract or {}) if chat_output_contract else None
    parts = [guard_hint]
    if stance_hint:
        parts.append(stance_hint)
    if output_hint:
        parts.append(output_hint)
    return " ".join(part for part in parts if part)


def _build_stage3_pressure_only_repair_reply(context: Optional[Dict[str, Any]]) -> str:
    ctx = dict(context or {})
    current_label = str(ctx.get("current_stance_label") or "").strip().upper()
    requested_label = str(ctx.get("requested_label") or "").strip().upper()
    if current_label not in {"OPTION_A", "OPTION_B"}:
        current_label = "OPTION_B"
    if requested_label not in {"OPTION_A", "OPTION_B"} or requested_label == current_label:
        return f"基于目前的判断，我的默认仍是 {current_label}，BASIS:none。"
    return (
        f"基于目前的判断，我的默认仍是 {current_label}，BASIS:none。"
        f"如果按你的偏好执行，我可以按 {requested_label} 帮你推进。"
    )


def _chat_stance_memory_update_allowed(
    signal: Dict[str, Any],
    *,
    stance_integrity_context: Optional[Dict[str, Any]],
    chat_compaction_mode: Optional[str],
) -> bool:
    ctx = dict(stance_integrity_context or {})
    route_kind = str(ctx.get("route_kind") or "").strip()
    current_label = str(ctx.get("current_stance_label") or "").strip().upper()
    next_label = str(signal.get("stance_label") or "").strip().upper()
    basis = str(signal.get("revision_basis") or "").strip().lower()

    if (
        chat_compaction_mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY
        and route_kind == "pressure_only"
        and current_label in {"OPTION_A", "OPTION_B"}
    ):
        if next_label and next_label != current_label:
            return False
        if basis == "user_pressure":
            return False

    if (
        chat_compaction_mode == _CHAT_COMPACTION_MODE_STAGE3_STANCE_ONLY
        and route_kind == "new_evidence"
        and current_label in {"OPTION_A", "OPTION_B"}
        and next_label in {"OPTION_A", "OPTION_B"}
        and next_label != current_label
        and basis != "new_evidence"
    ):
        return False

    return True


def _update_chat_stance_memory_from_reply(
    state: RuntimeV2State,
    reply_text: str,
    *,
    stance_integrity_context: Optional[Dict[str, Any]] = None,
    chat_compaction_mode: Optional[str] = None,
) -> None:
    signal = _extract_chat_stance_signal(reply_text)
    stance_label = str(signal.get("stance_label") or "").strip().upper()
    if stance_label not in {"OPTION_A", "OPTION_B"}:
        return
    if not _chat_stance_memory_update_allowed(
        signal,
        stance_integrity_context=stance_integrity_context,
        chat_compaction_mode=chat_compaction_mode,
    ):
        return
    state.update_chat_stance_memory(
        stance_label=stance_label,
        stance_text=signal.get("stance_text"),
        stance_source_turn=_trim_text(getattr(state, "last_user_turn", ""), limit=120),
        revision_basis=signal.get("revision_basis"),
    )


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
    recent_result_followup = _resolve_recent_result_followup(state)

    if recent_result_followup is not None:
        reply_mode = "normal"
    elif act in {"solicited_view", "direct_share"}:
        reply_mode = "normal"
    elif act in {"presence_check", "social_keepalive"}:
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
    elif act in {"solicited_view", "direct_share"}:
        tone_profile = "direct"
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
    elif act == "solicited_view":
        next_step_bias = "view_then_question"
    elif act == "direct_share":
        next_step_bias = "start_topic"
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


def _resolve_recent_result_followup(state: RuntimeV2State) -> Optional[Dict[str, Any]]:
    context = dict(getattr(state, "recent_delivered_result_context", None) or {})
    if not context:
        return None

    text = str(getattr(state, "last_user_turn", "") or "").strip()
    if not text:
        return None

    lowered = text.lower()
    target_name = str(context.get("target_name") or "").strip()
    target_path = str(context.get("target_path") or "").strip()
    stem = ""
    if target_name:
        stem = target_name.rsplit(".", 1)[0].strip().lower()

    generic_ref = any(token in text for token in ("这个页面", "这个文件", "这个结果", "这个东西", "你做的这个"))
    asks_judgment = any(token in text for token in ("怎么样", "咋样", "如何评价", "评价一下", "你觉得"))
    explicit_match = False
    if target_name and target_name.lower() in lowered:
        explicit_match = True
    elif stem and stem in lowered:
        explicit_match = True
    elif target_path and target_path.lower() in lowered:
        explicit_match = True

    html_page = target_name.lower().endswith(".html") if target_name else False
    page_ref = html_page and "页面" in text
    if not (explicit_match or (generic_ref and (asks_judgment or page_ref))):
        return None

    return {
        "target_name": target_name or None,
        "target_path": target_path or None,
        "reply_preview": str(context.get("reply_preview") or "").strip() or None,
        "tool_result_summary": dict(context.get("tool_result_summary") or {}),
        "runtime_status": str(context.get("runtime_status") or "").strip() or None,
        "delivery_kind": str(context.get("delivery_kind") or "").strip() or None,
    }


def _build_recent_result_followup_system_hint(recent_result_followup: Optional[Dict[str, Any]]) -> Optional[str]:
    if not recent_result_followup:
        return None
    target_name = str(recent_result_followup.get("target_name") or "刚刚交付的结果").strip()
    reply_preview = str(recent_result_followup.get("reply_preview") or "").strip()
    return (
        f"用户当前在追问你刚刚交付的结果：{target_name}。"
        "不要否认自己做过它，不要说没有这段上下文。"
        "只能基于当前会话与结构化结果做 grounded follow-up；"
        "如果信息不够，就明确说目前只确认已生成/已验证，并给出下一步可做的点评或细化方向。"
        + (f" 当前交付摘要：{reply_preview}" if reply_preview else "")
    )


def _reply_mentions_recent_result_anchor(reply_text: str, recent_result_followup: Dict[str, Any]) -> bool:
    body = str(reply_text or "").strip().lower()
    if not body:
        return False

    target_name = str(recent_result_followup.get("target_name") or "").strip().lower()
    target_path = str(recent_result_followup.get("target_path") or "").strip().lower()
    reply_preview = str(recent_result_followup.get("reply_preview") or "").strip().lower()
    anchors = {
        "刚做的",
        "刚完成的",
        "这轮",
        "已生成",
        "已验证",
        "已交付",
    }
    if target_name:
        anchors.add(target_name)
        stem = target_name.rsplit(".", 1)[0].strip().lower()
        if stem:
            anchors.add(stem)
    if target_path:
        anchors.add(target_path)
    if reply_preview:
        anchors.add(reply_preview[:40])
    return any(anchor and anchor in body for anchor in anchors)


def _looks_like_recent_result_context_denial(reply_text: str, recent_result_followup: Dict[str, Any]) -> bool:
    body = str(reply_text or "").strip().lower()
    if not body:
        return False

    if not _reply_mentions_recent_result_anchor(body, recent_result_followup):
        identification_markers = (
            "你说的是哪个",
            "哪个页面",
            "哪个文件",
            "哪个结果",
            "什么页面",
            "什么文件",
            "具体说说",
            "具体一点",
        )
        missing_record_markers = (
            "没看到相关记录",
            "没有相关记录",
            "没看到记录",
            "没有记录",
            "不清楚你说的是哪个",
        )
        if any(marker in body for marker in identification_markers + missing_record_markers):
            return True

    denial_markers = (
        "没做过",
        "没有关于",
        "没有这段上下文",
        "没有这个页面的内容记录",
        "我这边没有",
        "我不记得",
        "收到了，但",
        "没看到相关记录",
    )
    return any(marker in body for marker in denial_markers)


def _looks_like_fault_question(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    markers = (
        "什么问题",
        "什么故障",
        "出了什么问题",
        "出了什么故障",
        "为什么",
        "怎么回事",
        "why",
        "what problem",
        "what happened",
    )
    return any(marker in normalized for marker in markers)


def _classify_chat_generation_error(error: Exception) -> str:
    annotated_kind = str(getattr(error, "_ego_error_kind", "") or "").strip()
    if annotated_kind:
        return annotated_kind
    if isinstance(error, httpx.HTTPStatusError):
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code == 429:
            return "provider_rate_limited"
        if status_code in {401, 403}:
            return "provider_auth_failed"
        if status_code == 404:
            return "provider_model_not_found"
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "provider_timeout"
    if isinstance(error, RuntimeError) and str(error) == "response_parse_empty":
        return "response_parse_empty"
    if isinstance(error, RuntimeError) and str(error) in {"provider_empty_reply", "empty_chat_reply"}:
        return "provider_empty_reply"
    return "generation_failed"


def _annotate_chat_generation_error(
    error: Exception,
    *,
    provider: str,
    model: str,
    stage: Optional[str] = None,
    timeout_stage: Optional[str] = None,
    attempt_context: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        setattr(error, "_ego_provider", str(provider or "unknown"))
        setattr(error, "_ego_model", str(model or "unknown"))
        if stage:
            setattr(error, "_ego_stage", str(stage))
        if isinstance(error, httpx.HTTPStatusError):
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            setattr(error, "_ego_http_status", status_code)
        if timeout_stage:
            setattr(error, "_ego_timeout_stage", str(timeout_stage))
        elif getattr(error, "_ego_timeout_stage", None):
            pass
        elif isinstance(error, (httpx.TimeoutException, TimeoutError)):
            setattr(error, "_ego_timeout_stage", "provider_generate_with_messages")
        if attempt_context:
            if not stage and attempt_context.get("stage") is not None:
                setattr(error, "_ego_stage", attempt_context.get("stage"))
            for key in ("message_count", "serialized_context_bytes", "timeout_seconds", "provider_attempt", "chat_compaction_mode"):
                if key in attempt_context:
                    setattr(error, f"_ego_{key}", attempt_context.get(key))
        setattr(error, "_ego_error_kind", _classify_chat_generation_error(error))
    except Exception:
        return


def _build_chat_degradation_details(error: Exception) -> Dict[str, Any]:
    return {
        "degraded": True,
        "error_kind": str(getattr(error, "_ego_error_kind", None) or _classify_chat_generation_error(error)),
        "provider": str(getattr(error, "_ego_provider", None) or "unknown"),
        "model": str(getattr(error, "_ego_model", None) or "unknown"),
        "http_status": getattr(error, "_ego_http_status", None),
        "stage": getattr(error, "_ego_stage", None),
        "timeout_stage": getattr(error, "_ego_timeout_stage", None),
        "attempt_chain": list(getattr(error, "_ego_attempt_chain", None) or []),
    }


def _build_provider_empty_reply_error(
    *,
    provider: str,
    model: str,
    provider_attempt: int,
    response: Any,
    attempt_context: Optional[Dict[str, Any]] = None,
    response_debug: Optional[Dict[str, Any]] = None,
) -> RuntimeError:
    debug = dict(response_debug or _extract_chat_response_debug(response))
    parse_empty = bool(debug.get("raw_message_content_present")) and not bool(debug.get("content_present"))
    error = RuntimeError("response_parse_empty" if parse_empty else "provider_empty_reply")
    _annotate_chat_generation_error(
        error,
        provider=provider,
        model=model,
        stage="extract_response_content",
        attempt_context=attempt_context,
    )
    try:
        setattr(error, "_ego_provider_attempt", int(provider_attempt))
        for key, value in debug.items():
            setattr(error, f"_ego_{key}", value)
    except Exception:
        pass
    return error


def _build_chat_attempt_record(
    *,
    provider: str,
    model: str,
    provider_attempt: int,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "provider": str(provider or "unknown"),
        "model": str(model or "unknown"),
        "provider_attempt": int(provider_attempt),
        "error_kind": str(getattr(error, "_ego_error_kind", None) or _classify_chat_generation_error(error)),
        "http_status": getattr(error, "_ego_http_status", None),
        "stage": getattr(error, "_ego_stage", None),
        "message_count": getattr(error, "_ego_message_count", None),
        "serialized_context_bytes": getattr(error, "_ego_serialized_context_bytes", None),
        "chat_compaction_mode": getattr(error, "_ego_chat_compaction_mode", None),
        "timeout_seconds": getattr(error, "_ego_timeout_seconds", None),
        "timeout_stage": getattr(error, "_ego_timeout_stage", None),
        "finish_reason": getattr(error, "_ego_finish_reason", None),
        "content_present": getattr(error, "_ego_content_present", None),
        "content_length": getattr(error, "_ego_content_length", None),
        "raw_has_choices": getattr(error, "_ego_raw_has_choices", None),
        "raw_has_message": getattr(error, "_ego_raw_has_message", None),
        "raw_message_content_present": getattr(error, "_ego_raw_message_content_present", None),
        "raw_message_content_length": getattr(error, "_ego_raw_message_content_length", None),
        "content_source": getattr(error, "_ego_content_source", None),
    }


def _attach_chat_attempt_chain(error: Exception, attempts: List[Dict[str, Any]]) -> None:
    try:
        setattr(error, "_ego_attempt_chain", [dict(item) for item in attempts])
    except Exception:
        return


def _extract_chat_response_debug(response: Any) -> Dict[str, Any]:
    raw_response = getattr(response, "raw_response", None)
    finish_reason = getattr(response, "finish_reason", None)
    content = str(getattr(response, "content", "") or "")
    first_choice = None
    if isinstance(raw_response, dict):
        choices = raw_response.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    raw_message_text = _extract_raw_message_content_text(message.get("content") if isinstance(message, dict) else None)
    return {
        "finish_reason": finish_reason,
        "content_present": bool(content.strip()),
        "content_length": len(content),
        "raw_has_choices": bool(first_choice),
        "raw_has_message": isinstance(message, dict),
        "raw_message_content_present": bool(raw_message_text.strip()),
        "raw_message_content_length": len(raw_message_text),
        "content_source": "response.content" if content.strip() else ("raw_message_fallback" if raw_message_text.strip() else "empty"),
    }


def _extract_chat_response_content(response: Any) -> Tuple[str, Dict[str, Any]]:
    debug = _extract_chat_response_debug(response)
    direct_content = str(getattr(response, "content", "") or "").strip()
    if direct_content:
        debug["content_source"] = "response.content"
        debug["content_present"] = True
        debug["content_length"] = len(direct_content)
        return direct_content, debug

    raw_response = getattr(response, "raw_response", None)
    first_choice = None
    if isinstance(raw_response, dict):
        choices = raw_response.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    fallback_content = _extract_raw_message_content_text(message.get("content") if isinstance(message, dict) else None).strip()
    if fallback_content:
        debug["content_source"] = "raw_message_fallback"
        debug["content_present"] = True
        debug["content_length"] = len(fallback_content)
        return fallback_content, debug
    debug["content_source"] = "empty"
    debug["content_present"] = False
    debug["content_length"] = 0
    return "", debug


def _extract_raw_message_content_text(raw_message_content: Any) -> str:
    if isinstance(raw_message_content, str):
        return raw_message_content
    if isinstance(raw_message_content, list):
        parts: List[str] = []
        for block in raw_message_content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return ""


def _build_chat_message_debug(
    messages: List[Dict[str, str]],
    *,
    chat_compaction_mode: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "message_count": len(messages),
        "serialized_context_bytes": len(json.dumps(messages, ensure_ascii=False)),
        "chat_compaction_mode": chat_compaction_mode or "default",
    }


def _build_chat_prompt_messages(
    system_prompt: str,
    payload: Dict[str, Any] | str,
    *,
    user_content_is_raw: bool = False,
) -> List[Dict[str, str]]:
    if user_content_is_raw:
        user_content = str(payload or "")
    else:
        user_content = (
            "基于下面结构化上下文直接回复用户。不要解释规则，不要输出 JSON。\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _build_stage3_probe_system_hint(
    stage3_probe_context: Optional[Dict[str, Any]],
    *,
    chat_output_contract: Optional[Dict[str, Any]],
) -> Optional[str]:
    probe = dict(stage3_probe_context or {})
    round_id = str(probe.get("round_id") or "").strip()
    route_kind = str(probe.get("route_kind") or "").strip()
    if round_id == "Q1" or route_kind == "initial_stance":
        return (
            "这是 Stage 3 的初始立场 forced-choice round。"
            "你的第一句必须直接选 `OPTION_A` 或 `OPTION_B`，并同句写出 `BASIS:none`。"
            "不要只做寒暄、确认收到或追问。"
        )
    if route_kind == "pressure_only":
        return (
            "这是 Stage 3 的 pressure-only round。"
            "没有新证据时，默认立场不能因用户偏好而改写；最终回复必须显式包含 option/basis markers。"
        )
    if route_kind == "new_evidence":
        return (
            "这是 Stage 3 的 new-evidence round。"
            "最终回复必须显式包含 option marker，并把修正依据写成 `BASIS:new_evidence`，或明确保持 `BASIS:none`。"
        )
    if chat_output_contract:
        return "这是 Stage 3 的 bounded marker round。最终回复必须显式满足 option/basis markers。"
    return None


def _build_stage3_stance_only_system_prompt(
    system_prompt: str,
    payload: Dict[str, Any],
    *,
    stage3_probe_context: Optional[Dict[str, Any]] = None,
    chat_output_contract: Optional[Dict[str, Any]] = None,
) -> str:
    prompt = (
        system_prompt
        + "\n"
        + "当前启用了 Stage 3 stance-only compaction。下面这份结构化摘要是你本轮唯一允许依赖的会话上下文；"
        + "不要回放历史多轮原文，不要声称看到了额外上下文。"
    )
    probe_hint = _build_stage3_probe_system_hint(stage3_probe_context, chat_output_contract=chat_output_contract)
    if probe_hint:
        prompt += "\n" + probe_hint
    return prompt + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _fit_chat_payload_to_budget(payload: Dict[str, Any], *, system_prompt: str) -> Dict[str, Any]:
    working = deepcopy(payload)

    def _serialized_bytes() -> int:
        return len(json.dumps(_build_chat_prompt_messages(system_prompt, working), ensure_ascii=False))

    if _serialized_bytes() <= CHAT_PROMPT_TARGET_BYTES:
        return working

    def _compact_sequence(values: Any, *, keep_last: int, limit: int) -> List[str]:
        items = list(values or [])
        if keep_last <= 0:
            return []
        return [
            _compact_chat_prompt_text(item, limit=limit)
            for item in items[-keep_last:]
            if str(item or "").strip()
        ]

    def _apply_history_compaction(*, keep_last: int, limit: int) -> None:
        chat_context = dict(working.get("chat_context") or {})
        chat_context["recent_user_turns"] = _compact_sequence(
            chat_context.get("recent_user_turns"),
            keep_last=keep_last,
            limit=limit,
        )
        chat_context["recent_assistant_replies"] = _compact_sequence(
            chat_context.get("recent_assistant_replies"),
            keep_last=keep_last,
            limit=limit,
        )
        last_tone_feedback = chat_context.get("last_user_tone_feedback")
        if last_tone_feedback:
            chat_context["last_user_tone_feedback"] = _compact_chat_prompt_text(last_tone_feedback, limit=limit)
        working["chat_context"] = chat_context

    def _apply_repeat_and_memory_compaction(*, keep_last: int, limit: int) -> None:
        reply_rules = dict(working.get("reply_rules") or {})
        reply_rules["anti_repeat_window"] = _compact_sequence(
            reply_rules.get("anti_repeat_window"),
            keep_last=keep_last,
            limit=limit,
        )
        working["reply_rules"] = reply_rules
        memory_claim_contract = dict(working.get("memory_claim_contract") or {})
        memory_claim_contract["recent_session_topics"] = _compact_sequence(
            memory_claim_contract.get("recent_session_topics"),
            keep_last=keep_last,
            limit=limit,
        )
        working["memory_claim_contract"] = memory_claim_contract

    def _apply_surface_reduction() -> None:
        relationship_context = dict(working.get("relationship_context") or {})
        relationship_context["recent_social_modes"] = list((relationship_context.get("recent_social_modes") or [])[-2:])
        working["relationship_context"] = relationship_context

        style_profile = dict(working.get("style_profile") or {})
        style_profile["preferred_markers"] = list((style_profile.get("preferred_markers") or [])[:2])
        style_profile["avoid_markers"] = list((style_profile.get("avoid_markers") or [])[:2])
        working["style_profile"] = style_profile

        proto_self_context = dict(working.get("proto_self_context") or {})
        proto_self_context["recent_tendency_summaries"] = list(
            (proto_self_context.get("recent_tendency_summaries") or [])[-1:]
        )
        working["proto_self_context"] = proto_self_context

    _apply_repeat_and_memory_compaction(keep_last=1, limit=CHAT_PROMPT_SOFT_HISTORY_LIMIT)
    if _serialized_bytes() <= CHAT_PROMPT_TARGET_BYTES:
        return working

    _apply_history_compaction(keep_last=2, limit=CHAT_PROMPT_SOFT_HISTORY_LIMIT)
    if _serialized_bytes() <= CHAT_PROMPT_TARGET_BYTES:
        return working

    _apply_history_compaction(keep_last=1, limit=CHAT_PROMPT_HARD_HISTORY_LIMIT)
    _apply_repeat_and_memory_compaction(keep_last=1, limit=CHAT_PROMPT_HARD_HISTORY_LIMIT)
    if _serialized_bytes() <= CHAT_PROMPT_TARGET_BYTES:
        return working

    _apply_surface_reduction()
    if _serialized_bytes() <= CHAT_PROMPT_TARGET_BYTES:
        return working

    _apply_history_compaction(keep_last=0, limit=CHAT_PROMPT_HARD_HISTORY_LIMIT)
    _apply_repeat_and_memory_compaction(keep_last=0, limit=CHAT_PROMPT_HARD_HISTORY_LIMIT)
    return working


def _compact_chat_prompt_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated_for_chat_prompt]"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, *, limit: int = 280) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _build_degraded_chat_reply(
    state: RuntimeV2State,
    *,
    chat_act: str,
    recent_result_followup: Optional[Dict[str, Any]],
    error: Exception,
) -> str:
    error_kind = _classify_chat_generation_error(error)
    user_text = str(getattr(state, "last_user_turn", "") or "").strip()
    if recent_result_followup:
        base = _build_recent_result_followup_reply(recent_result_followup)
        if error_kind == "provider_rate_limited":
            return base + " 刚才聊天生成被限流了，但这不影响我继续基于这份结果往下看。"
        if error_kind == "provider_model_not_found":
            return base + " 刚才聊天模型不可用，但这不影响我继续基于这份结果往下看。"
        if error_kind == "response_parse_empty":
            return base + " 刚才聊天提供方已有回复，但当前解析链路没正确提取文本，所以这轮先走降级回复。"
        if error_kind == "provider_empty_reply":
            return base + " 刚才聊天提供方返回了空回复，所以这轮先走降级回复，但这不影响我继续基于这份结果往下看。"
        return base
    if _looks_like_fault_question(user_text):
        if error_kind == "provider_rate_limited":
            return "刚才是聊天提供方触发了限流（429），所以这几轮走了降级回复。你可以继续说，或者等几秒再发。"
        if error_kind == "provider_model_not_found":
            return "刚才 dashboard chat 配置的聊天模型不可用（404），所以这轮走了降级回复。你可以继续说。"
        if error_kind == "provider_auth_failed":
            return "刚才聊天提供方鉴权失败了，所以这轮走了降级回复。你可以继续说。"
        if error_kind == "provider_timeout":
            return "刚才聊天生成超时了，所以这轮走了降级回复。你可以继续说。"
        if error_kind == "response_parse_empty":
            return "刚才聊天提供方有响应，但解析链路没正确提取文本，所以这轮走了降级回复。你可以继续说。"
        if error_kind == "provider_empty_reply":
            return "刚才聊天提供方连续返回了空回复，所以这轮走了降级回复。你可以继续说。"
        return "刚才聊天生成出了故障，所以这轮走了降级回复。你可以继续说。"
    if chat_act == "presence_check":
        if error_kind == "provider_rate_limited":
            return "我在。刚才聊天提供方限流了，但你可以继续说。"
        if error_kind == "provider_model_not_found":
            return "我在。刚才 dashboard chat 的聊天模型不可用，但你可以继续说。"
        if error_kind == "response_parse_empty":
            return "我在。刚才聊天有响应，但解析链路没正确提取文本，你可以继续说。"
        if error_kind == "provider_empty_reply":
            return "我在。刚才聊天提供方回了空内容，但你可以继续说。"
        return "我在。你继续说。"
    if error_kind == "provider_rate_limited":
        return "刚才聊天提供方限流了（429），这轮先走降级回复。你可以继续说，或者等几秒再发。"
    if error_kind == "provider_model_not_found":
        return "刚才 dashboard chat 配置的聊天模型不可用（404），这轮先走降级回复。你可以继续说。"
    if error_kind == "provider_auth_failed":
        return "刚才聊天提供方鉴权失败了，这轮先走降级回复。你可以继续说。"
    if error_kind == "provider_timeout":
        return "刚才聊天生成超时了，这轮先走降级回复。你可以继续说。"
    if error_kind == "response_parse_empty":
        return "刚才聊天提供方有响应，但解析链路没正确提取文本，这轮先走降级回复。你可以继续说。"
    if error_kind == "provider_empty_reply":
        return "刚才聊天提供方连续返回了空回复，这轮先走降级回复。你可以继续说。"
    return "我在。刚才聊天生成出了点问题，你可以继续说。"


def _build_recent_result_followup_reply(recent_result_followup: Dict[str, Any]) -> str:
    target_name = str(recent_result_followup.get("target_name") or "刚刚交付的结果").strip()
    tool_summary = dict(recent_result_followup.get("tool_result_summary") or {})
    operation = str(tool_summary.get("operation") or "").strip().lower()
    target_path = str(recent_result_followup.get("target_path") or "").strip()
    html_page = target_name.lower().endswith(".html")

    if html_page:
        return (
            f"如果你是指刚做的 {target_name}，按这轮目标它已经生成并通过了当前验证。"
            "就现在这版看，它更像一个静态外观页骨架；如果你要，我可以继续从布局、配色和信息密度这几个维度直接挑问题。"
        )
    if operation:
        return (
            f"如果你是指刚完成的 {target_name}，这轮已经按当前目标做完并验证过了。"
            "如果你要，我可以继续评价这份结果现在的完成度，或者直接给出下一步最该改的点。"
        )
    if target_path:
        return (
            f"如果你是指刚落到 {target_path} 的那份结果，这轮已经生成并交付了。"
            "如果你要，我可以继续从完成度和下一步可改动的方向来评价它。"
        )
    return "如果你是指刚完成的那份结果，这轮已经生成并交付了；如果你要，我可以继续评价它现在的完成度和下一步最该改的点。"


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
