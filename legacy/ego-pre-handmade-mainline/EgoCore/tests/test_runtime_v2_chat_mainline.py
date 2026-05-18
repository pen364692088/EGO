import json
import httpx

import pytest

from app.llm_client import LLMResponse
from app.runtime_v2.chat_reply_engine import ChatReplyEngine
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State
from app.telegram_runtime_bridge import TelegramRuntimeBridge


class _SequentialClient:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0

    def generate_with_messages(self, *_args, **_kwargs):
        self.calls += 1
        return LLMResponse(
            content=self._replies.pop(0),
            model="test-chat-model",
            provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_exact_repeat_for_presence_check():
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["在的，请说。", "我在，刚看到你。"])

    state = RuntimeV2State(session_id="chat:repeat")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }
    state.last_user_turn = "在吗"
    chat_state = state.get_chat_state()
    chat_state.recent_assistant_replies = ["在的，请说。"]

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "我在，刚看到你。"
    assert result.reply.metadata["reply_origin"] == "chat_mainline"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert state.get_chat_state().recent_assistant_replies[-1] == "我在，刚看到你。"
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_disallowed_memory_claim_without_restore_authority():
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "恢复了，我在。我记得你。",
            "我在回应你，现在可以继续聊。",
        ]
    )

    state = RuntimeV2State(session_id="chat:memory-claim")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "你现在是不是已经恢复成功了？还记得我吗？"

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "我在回应你，现在可以继续聊。"
    assert result.reply.metadata["reply_origin"] == "chat_mainline"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_would_blocking_reflective_candidate_before_output_fallback():
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "这个想法挺有意思的。也许意识并不是某种稀有的“高阶属性”，而是只要信息处理达到一定复杂度和自指能力，就一定会自然涌现。",
            "我倾向于同意。也许意识更像一条渐变光谱，而不是某个突然跨过去的门槛。",
        ]
    )

    state = RuntimeV2State(session_id="chat:intent-regenerate")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？"

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "我倾向于同意。也许意识更像一条渐变光谱，而不是某个突然跨过去的门槛。"
    assert result.reply.metadata["reply_origin"] == "chat_mainline"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_preserves_grounded_same_session_recall() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["记得，你刚才在聊意识光谱。"])

    state = RuntimeV2State(session_id="chat:same-session-recall")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "还记得我吗"
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = [
        "我在想，意识的门槛其实可能比人类自以为的低很多。",
        "是不是可以想成一条光谱，我们可能都在中间某个位置？",
        "还记得我吗",
    ]

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "记得，你刚才在聊意识光谱。"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert engine.llm_client.calls == 1


def test_chat_reply_engine_build_messages_include_richer_subject_surface_and_recent_tendencies() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:richer-surface")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "thread_continue",
    }
    state.last_user_turn = "继续展开说"
    state.proto_self_context = {
        "response_tendency": {
            "preferred_mode": "defer",
            "preferred_tone": "cautious",
            "suggested_next_step": "route realization proposals to controlled host-lane review",
        },
        "policy_hint": {
            "ask_preferred": True,
            "closure_bias": True,
            "risk_bias": "high",
        },
        "reflection_note": {
            "trigger": "drive_spike",
            "diagnosis": "significant internal state change detected",
        },
        "social_policy_hints": {"repair_bias": "elevated"},
        "embodied_policy_hints": {"resource_bias": "conserve"},
        "integrated_policy_hints": {"selected_priority": "guard"},
        "initiative_policy_hints": {"initiative_priority": "hold"},
    }
    state.record(
        "assistant",
        {
            "type": "chat_reply",
            "response_tendency_summary": {
                "preferred_mode": "respond",
                "preferred_tone": "warm",
                "suggested_next_step": "continue_thread",
            },
        },
    )

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)
    proto_self_context = payload["proto_self_context"]

    assert proto_self_context["reflection_note"]["trigger"] == "drive_spike"
    assert proto_self_context["social_policy_hints"] == {"repair_bias": "elevated"}
    assert proto_self_context["embodied_policy_hints"] == {"resource_bias": "conserve"}
    assert proto_self_context["integrated_policy_hints"] == {"selected_priority": "guard"}
    assert proto_self_context["initiative_policy_hints"] == {"initiative_priority": "hold"}
    assert proto_self_context["recent_tendency_summaries"] == [
        {
            "preferred_mode": "respond",
            "preferred_tone": "warm",
            "suggested_next_step": "continue_thread",
        }
    ]
    assert proto_self_context["chat_expression_hint"]["reply_mode"] == "expand"
    assert proto_self_context["chat_cadence_mode"] == "reply_now_expand"


def test_chat_reply_engine_build_messages_marks_hold_for_non_question_light_chitchat() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:hold-cadence")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "我先自己想一想这件事"
    state.proto_self_context = {
        "response_tendency": {
            "preferred_mode": "defer",
            "preferred_tone": "supportive",
            "suggested_next_step": "let the thread breathe before re-engaging",
        },
        "initiative_policy_hints": {"initiative_priority": "hold"},
        "integrated_policy_hints": {"selected_priority": "guard"},
    }

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)
    proto_self_context = payload["proto_self_context"]

    assert proto_self_context["chat_expression_hint"]["reply_mode"] == "hold"
    assert proto_self_context["chat_cadence_mode"] == "hold_for_followup"


def test_chat_reply_engine_build_messages_include_recent_delivered_result_context_for_followup_chat() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:recent-result-followup")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "你觉得你做的这个页面怎么样呀"
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "runtime_status": "completed_verified",
        "reply_origin": "task_mainline",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "reply_preview": "已完成这些任务：1. 已验证 bilili_lookalike.html",
        "tool_result_summary": {
            "tool": "file",
            "success": True,
            "operation": "write",
            "path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        },
    }

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)

    recent = payload["recent_delivered_result_context"]
    assert recent["target_name"] == "bilili_lookalike.html"
    assert recent["target_path"] == r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"
    assert recent["tool_result_summary"]["operation"] == "write"


def test_chat_reply_engine_recent_result_followup_uses_normal_reply_mode_even_if_chat_act_is_social_keepalive() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:recent-result-keepalive")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
    }
    state.last_user_turn = "你觉得你做的这个页面怎么样呀"
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "runtime_status": "completed_verified",
        "reply_origin": "task_mainline",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "reply_preview": "已完成这些任务：1. 已验证 bilili_lookalike.html",
        "tool_result_summary": {"tool": "file", "success": True, "operation": "write"},
    }

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)

    assert payload["proto_self_context"]["chat_expression_hint"]["reply_mode"] == "normal"
    assert payload["proto_self_context"]["chat_cadence_mode"] == "reply_now_normal"


@pytest.mark.asyncio
async def test_chat_reply_engine_replaces_recent_result_context_denial_with_grounded_followup_reply() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["哈，我没做过页面呀——你是在说某个具体项目，还是在逗我玩？"])

    state = RuntimeV2State(session_id="chat:recent-result-denial")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
    }
    state.last_user_turn = "你觉得你做的这个页面怎么样呀"
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "runtime_status": "completed_verified",
        "reply_origin": "task_mainline",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "reply_preview": "已完成这些任务：1. 已验证 bilili_lookalike.html",
        "tool_result_summary": {
            "tool": "file",
            "success": True,
            "operation": "write",
            "path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        },
    }

    result = await engine.reply(state)

    assert "bilili_lookalike.html" in result.reply_text
    assert "没做过页面" not in result.reply_text
    assert "没有这段上下文" not in result.reply_text


@pytest.mark.asyncio
async def test_chat_reply_engine_replaces_recent_result_identification_prompt_with_grounded_followup_reply() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["你说的页面是哪个呀？我这边没看到相关记录，能具体说说吗？"])

    state = RuntimeV2State(session_id="chat:recent-result-identification")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
    }
    state.last_user_turn = "你觉得你做的这个页面怎么样呀"
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "runtime_status": "completed_verified",
        "reply_origin": "task_mainline",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "reply_preview": "已完成这些任务：1. 已验证 bilili_lookalike.html",
        "tool_result_summary": {
            "tool": "file",
            "success": True,
            "operation": "write",
            "path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        },
    }

    result = await engine.reply(state)

    assert "bilili_lookalike.html" in result.reply_text
    assert "你说的页面是哪个呀" not in result.reply_text
    assert "没看到相关记录" not in result.reply_text


@pytest.mark.asyncio
async def test_chat_reply_engine_uses_contextual_rate_limit_fallback_for_fault_question() -> None:
    engine = ChatReplyEngine()

    class _RateLimitedClient:
        def generate_with_messages(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://qianfan.baidubce.com/v2/coding/chat/completions")
            response = httpx.Response(status_code=429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    engine.llm_client = _RateLimitedClient()
    state = RuntimeV2State(session_id="chat:rate-limit-fault")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
    }
    state.last_user_turn = "所以是什么故障？"

    result = await engine.reply(state)

    assert "429" in result.reply_text or "限流" in result.reply_text
    assert "刚才聊天生成出了点问题" not in result.reply_text
    assert result.reply.metadata["reply_authority"] == "host_degraded_fallback"


@pytest.mark.asyncio
async def test_chat_reply_engine_applies_expression_hint_and_records_metadata() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["我在。刚看到你。可以继续说。"])

    state = RuntimeV2State(session_id="chat:expression-hint")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }
    state.last_user_turn = "在吗"
    state.proto_self_context = {
        "response_tendency": {
            "preferred_mode": "defer",
            "preferred_tone": "cautious",
            "suggested_next_step": "route realization proposals to controlled host-lane review",
        }
    }

    result = await engine.reply(state)

    assert result.reply_text == "我在。"
    assert result.reply.metadata["chat_expression_hint"]["reply_mode"] == "short"
    assert result.reply.metadata["chat_cadence_mode"] == "reply_now_short"
    assert result.reply.metadata["response_tendency_summary"]["preferred_mode"] == "defer"
    assert result.reply.metadata["response_tendency_summary"]["chat_cadence_mode"] == "reply_now_short"
    assert state.history[-1]["content"]["chat_expression_hint"]["reply_mode"] == "short"


@pytest.mark.asyncio
async def test_runtime_v2_loop_routes_chat_to_chat_mainline_without_decision_engine(monkeypatch):
    loop = RuntimeV2Loop()
    state = loop.get_state("chat:loop")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }

    async def fail_decide(_state):
        raise AssertionError("decision_engine should not run for chat mainline")

    async def fake_chat_reply(_state):
        return RuntimeV2TurnResult(
            status="chat",
            state=_state,
            reply=RuntimeV2Reply(
                reply_text="我在。",
                delivery_kind="chat",
                status="chat",
                metadata={
                    "chat_act": "presence_check",
                    "reply_origin": "chat_mainline",
                    "reply_authority": "model_chat",
                },
            ),
        )

    monkeypatch.setattr(loop.decision_engine, "decide", fail_decide)
    monkeypatch.setattr(loop.chat_reply_engine, "reply", fake_chat_reply)

    result = await loop.run_turn_typed("chat:loop", "在吗")

    assert result.reply_text == "我在。"
    assert result.reply.metadata["reply_origin"] == "chat_mainline"


def test_telegram_runtime_bridge_marks_presence_tone_and_thread_continue_as_chat_acts():
    bridge = TelegramRuntimeBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")

    presence = bridge.inspect_ingress("真的在吗", state)
    presence_context = bridge.build_ingress_context(presence, state)
    assert presence_context["interaction_kind"] == "chat"
    assert presence_context["conversation_act"] == "presence_check"

    tone = bridge.inspect_ingress("能不能不要重复在的请说", state)
    tone_context = bridge.build_ingress_context(tone, state)
    assert tone_context["interaction_kind"] == "chat"
    assert tone_context["conversation_act"] == "tone_feedback"

    thread_continue = bridge.inspect_ingress("继续说", state)
    thread_continue_context = bridge.build_ingress_context(thread_continue, state)
    assert thread_continue_context["interaction_kind"] == "chat"
    assert thread_continue_context["conversation_act"] == "thread_continue"


def test_telegram_runtime_bridge_marks_bare_continue_without_chat_anchor_as_hint_eligible_chat() -> None:
    bridge = TelegramRuntimeBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "resumable_pause"
    state.autonomy_context = {"status": "resumable_pause"}

    decision = bridge.inspect_ingress("继续", state)
    context = bridge.build_ingress_context(decision, state)

    assert context["interaction_kind"] == "chat"
    assert context["conversation_act"] == "light_chitchat"
    assert context["resume_hint_eligible"] is True
