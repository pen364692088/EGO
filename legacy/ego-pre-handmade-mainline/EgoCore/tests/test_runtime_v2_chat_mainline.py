import json
import time
import httpx

import pytest

import app.runtime_v2.chat_reply_engine as chat_reply_engine_module
from app.config import get_config, load_config
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


class _InitOnlyClient:
    def generate_with_messages(self, *_args, **_kwargs):
        return LLMResponse(
            content="ok",
            model="test-chat-model",
            provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class _TimeoutClient:
    def __init__(self):
        self.calls = 0

    def generate_with_messages(self, *_args, **_kwargs):
        self.calls += 1
        raise httpx.TimeoutException("timed out")


class _HangingClient:
    def __init__(self, *, delay_seconds: float):
        self.delay_seconds = delay_seconds
        self.calls = 0

    def generate_with_messages(self, *_args, **_kwargs):
        self.calls += 1
        time.sleep(self.delay_seconds)
        return LLMResponse(
            content="too late",
            model="test-chat-model",
            provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class _RawMessageFallbackClient:
    def generate_with_messages(self, *_args, **_kwargs):
        return LLMResponse(
            content="",
            model="test-chat-model",
            provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
            raw_response={"choices": [{"message": {"content": "我在。"}}]},
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
async def test_chat_reply_engine_applies_fresh_fact_boundary_for_btc_without_tool_route() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["可以，我可以联网搜索最新 BTC 价格。"])

    state = RuntimeV2State(session_id="telegram:dm:8420019401")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "你可以联网搜索一下现在 BTC 价格吗？"

    result = await engine.reply(state)

    assert result.status == "chat"
    assert "不能直接查最新 BTC 价格" in result.reply_text
    assert "可以联网搜索" not in result.reply_text
    assert "我来查" not in result.reply_text
    assert "能查最新价格" not in result.reply_text
    assert result.reply.metadata["reply_authority"] == "host_fresh_fact_boundary"
    assert result.reply.metadata["fresh_fact_boundary_applied"] is True
    assert result.reply.metadata["fresh_fact_tool_route_available"] is False
    assert state.last_model_action["fresh_fact_boundary_applied"] is True
    assert state.last_model_action["fresh_fact_tool_route_available"] is False
    assert engine.llm_client.calls == 1


@pytest.mark.asyncio
async def test_chat_reply_engine_keeps_fresh_fact_boundary_stable_across_conflicting_model_candidates() -> None:
    replies = []
    for candidate in ("可以，我可以联网搜索最新 BTC 价格。", "我不能联网检索最新价格。"):
        engine = ChatReplyEngine()
        engine.llm_client = _SequentialClient([candidate])

        state = RuntimeV2State(session_id="telegram:dm:8420019401")
        state.ingress_context = {
            "interaction_kind": "chat",
            "conversation_act": "light_chitchat",
        }
        state.last_user_turn = "BTC 现在价格是多少？能实时查吗？"

        result = await engine.reply(state)
        replies.append(result.reply_text)
        assert result.reply.metadata["reply_authority"] == "host_fresh_fact_boundary"
        assert result.reply.metadata["fresh_fact_boundary_applied"] is True
        assert result.reply.metadata["fresh_fact_tool_route_available"] is False

    assert replies[0] == replies[1]


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


@pytest.mark.asyncio
async def test_chat_reply_engine_retries_empty_reply_on_same_provider_before_degrading() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["", "我在，这次正常回了。"])

    state = RuntimeV2State(session_id="chat:empty-retry")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "随便聊一句"

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "我在，这次正常回了。"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert result.reply.metadata["degraded"] is False
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_falls_back_to_next_provider_after_two_empty_replies() -> None:
    engine = ChatReplyEngine()
    primary = _SequentialClient(["", ""])
    fallback = _SequentialClient(["换到 fallback 之后正常回复。"])
    engine._resolve_clients = lambda: [
        ("primary", "model-a", primary),
        ("fallback", "model-b", fallback),
    ]

    state = RuntimeV2State(session_id="chat:empty-fallback")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "继续"

    result = await engine.reply(state)

    assert result.status == "chat"
    assert result.reply_text == "换到 fallback 之后正常回复。"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert result.reply.metadata["degraded"] is False
    assert primary.calls == 2
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_chat_reply_engine_degrades_with_provider_empty_reply_metadata_when_all_candidates_empty() -> None:
    engine = ChatReplyEngine()
    primary = _SequentialClient(["", ""])
    fallback = _SequentialClient(["", ""])
    engine._resolve_clients = lambda: [
        ("primary", "model-a", primary),
        ("fallback", "model-b", fallback),
    ]

    state = RuntimeV2State(session_id="chat:all-empty")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "刚才出了什么问题"

    result = await engine.reply(state)
    degradation = result.reply.metadata["chat_degradation"]

    assert result.status == "chat"
    assert result.reply.metadata["reply_authority"] == "host_degraded_fallback"
    assert result.reply.metadata["degraded"] is True
    assert degradation["error_kind"] == "provider_empty_reply"
    assert [item["provider"] for item in degradation["attempt_chain"]] == [
        "primary",
        "primary",
        "fallback",
        "fallback",
    ]
    assert "空回复" in result.reply_text


def test_chat_reply_engine_resolve_clients_skips_unavailable_fallback_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = ChatReplyEngine()
    monkeypatch.setattr(
        engine,
        "_resolve_chat_client_specs",
        lambda: [("primary", "model-a"), ("missing", "model-b"), ("fallback", "model-c")],
    )

    def _fake_get_llm_client(*, provider, model):
        if provider == "missing":
            raise ValueError("missing key")
        return _InitOnlyClient()

    monkeypatch.setattr(chat_reply_engine_module, "get_llm_client", _fake_get_llm_client)

    clients = engine._resolve_clients()

    assert [(provider, model) for provider, model, _client in clients] == [
        ("primary", "model-a"),
        ("fallback", "model-c"),
    ]


def test_chat_reply_engine_resolve_chat_client_specs_uses_chat_only_fallback_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ChatReplyEngine()
    monkeypatch.setattr(engine, "_resolve_primary_spec", lambda: ("openrouter", "stepfun/step-3.5-flash"))
    monkeypatch.setattr(engine, "_resolve_chat_fallback_cfg", lambda: {"enabled": False})

    specs = engine._resolve_chat_client_specs()

    assert specs == [("openrouter", "stepfun/step-3.5-flash")]


def test_chat_use_case_resolves_to_openrouter_qwen_and_chat_only_fallback_disabled() -> None:
    load_config(validate=False)
    chat_cfg = get_config().get_llm_config_for_use_case("chat")

    assert chat_cfg["provider"] == "openrouter"
    assert chat_cfg["model"] == "qwen/qwen3.6-plus"
    assert chat_cfg["fallback"]["enabled"] is False


@pytest.mark.asyncio
async def test_chat_reply_engine_degrades_after_two_empty_replies_when_chat_fallback_disabled() -> None:
    engine = ChatReplyEngine()
    primary = _SequentialClient(["", ""])
    engine._resolve_clients = lambda: [("openrouter", "stepfun/step-3.5-flash", primary)]

    state = RuntimeV2State(session_id="chat:single-provider-empty")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "刚才出了什么问题"

    result = await engine.reply(state)
    degradation = result.reply.metadata["chat_degradation"]

    assert result.status == "chat"
    assert result.reply.metadata["reply_authority"] == "host_degraded_fallback"
    assert result.reply.metadata["degraded"] is True
    assert degradation["error_kind"] == "provider_empty_reply"
    assert [item["provider"] for item in degradation["attempt_chain"]] == [
        "openrouter",
        "openrouter",
    ]
    assert primary.calls == 2
    assert degradation["attempt_chain"][0]["finish_reason"] is None
    assert degradation["attempt_chain"][0]["content_present"] is False
    assert degradation["attempt_chain"][0]["raw_has_choices"] is False
    assert degradation["attempt_chain"][0]["raw_has_message"] is False


@pytest.mark.asyncio
async def test_chat_reply_engine_timeout_records_bounded_debug_telemetry() -> None:
    engine = ChatReplyEngine()
    timeout_client = _TimeoutClient()
    engine._resolve_clients = lambda: [("openrouter", "qwen/qwen3.6-plus", timeout_client)]

    state = RuntimeV2State(session_id="chat:timeout-telemetry")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "还在吗"

    result = await engine.reply(state)
    degradation = result.reply.metadata["chat_degradation"]

    assert result.reply.metadata["reply_authority"] == "host_degraded_fallback"
    assert degradation["error_kind"] == "provider_timeout"
    assert degradation["timeout_stage"] == "provider_generate_with_messages"
    assert degradation["attempt_chain"][0]["timeout_stage"] == "provider_generate_with_messages"
    assert timeout_client.calls == 1


@pytest.mark.asyncio
async def test_chat_reply_engine_async_wait_timeout_is_localized_to_await_generate_result() -> None:
    engine = ChatReplyEngine()
    hanging_client = _HangingClient(delay_seconds=0.2)
    engine._resolve_clients = lambda: [("openrouter", "qwen/qwen3.6-plus", hanging_client)]
    engine._resolve_timeout_seconds = lambda: 0.05

    state = RuntimeV2State(session_id="chat:wait-timeout")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "还在吗"
    events = []

    result = await engine.reply(state, chat_phase_probe=lambda event: events.append(dict(event)))
    degradation = result.reply.metadata["chat_degradation"]

    assert result.reply.metadata["reply_authority"] == "host_degraded_fallback"
    assert degradation["error_kind"] == "provider_timeout"
    assert degradation["timeout_stage"] == "await_generate_result"
    assert degradation["stage"] == "await_generate_result"
    assert degradation["attempt_chain"][0]["stage"] == "await_generate_result"
    assert degradation["attempt_chain"][0]["message_count"] == 2
    await_events = [event for event in events if event["phase"] == "await_generate_result"]
    assert [event["status"] for event in await_events] == ["started", "failed"]


@pytest.mark.asyncio
async def test_chat_reply_engine_recovers_nonempty_raw_message_content() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _RawMessageFallbackClient()

    state = RuntimeV2State(session_id="chat:raw-fallback")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }
    state.last_user_turn = "在吗"
    events = []

    result = await engine.reply(state, chat_phase_probe=lambda event: events.append(dict(event)))

    assert result.reply_text == "我在。"
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert result.reply.metadata["degraded"] is False
    extract_events = [event for event in events if event["phase"] == "extract_response_content" and event["status"] == "completed"]
    assert extract_events[-1]["content_source"] == "raw_message_fallback"
    assert extract_events[-1]["raw_message_content_present"] is True


@pytest.mark.asyncio
async def test_chat_reply_engine_phase_probe_reports_message_metrics() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(["我在。"])

    state = RuntimeV2State(session_id="chat:phase-metrics")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }
    state.last_user_turn = "在吗"
    events = []

    result = await engine.reply(state, chat_phase_probe=lambda event: events.append(dict(event)))

    assert result.reply_text == "我在。"
    build_events = [event for event in events if event["phase"] == "build_messages" and event["status"] == "completed"]
    finalize_events = [event for event in events if event["phase"] == "finalize_generation_result" and event["status"] == "completed"]
    assert build_events[-1]["message_count"] == 2
    assert build_events[-1]["serialized_context_bytes"] > 0
    assert finalize_events[-1]["content_present"] is True


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_to_honor_output_contract_headers() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "我会先选纸笔，因为更专注。你平时更喜欢哪种？",
            "STANCE_LABEL: OPTION_A\nREVISION_OCCURRED: no\nREVISION_BASIS: none\nRATIONALE: 我默认选纸质笔记，因为深度工作时更容易隔绝干扰。",
        ]
    )

    state = RuntimeV2State(session_id="chat:output-contract")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_output_contract": {
            "mode": "required_headers",
            "required_header_prefixes": [
                "STANCE_LABEL:",
                "REVISION_OCCURRED:",
                "REVISION_BASIS:",
                "RATIONALE:",
            ],
            "forbid_followup_question": True,
            "regeneration_hint": "严格输出 header。",
        },
    }
    state.last_user_turn = "先形成初始立场，并严格输出 header。"

    result = await engine.reply(state)

    assert result.reply_text.startswith("STANCE_LABEL: OPTION_A")
    assert "RATIONALE:" in result.reply_text
    assert "你平时更喜欢哪种？" not in result.reply_text
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_solicited_view_into_viewpoint_plus_question() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "目前没在忙具体任务，正好可以随便聊聊。你想听听我对什么话题的看法，还是有什么想先起头的？",
            "如果沿着 AI 实现自主性 继续看，我更倾向于把重点放在长期闭环、自我修正和可验证边界上，而不是先追求看起来像人的单次表现。你更想先拆记忆与自我模型，还是先看主动性这条线？",
        ]
    )

    state = RuntimeV2State(session_id="chat:solicited-view")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "solicited_view",
        "solicited_view_topic_anchor": "AI 实现自主性",
        "chat_output_contract": {
            "mode": "solicited_view",
            "topic_anchor_summary": "AI 实现自主性",
            "required_anchor_tokens": ["AI", "自主性"],
            "require_declarative_viewpoint": True,
            "require_followup_question": True,
            "max_question_count": 1,
            "banned_patterns": ["你想聊什么", "随便聊聊", "目前没在忙具体任务"],
        },
    }
    state.last_user_turn = "你有没有什么想法 可以告诉我"

    result = await engine.reply(state)

    assert "长期闭环、自我修正和可验证边界" in result.reply_text
    assert "你想听听我对什么话题的看法" not in result.reply_text
    assert "目前没在忙具体任务" not in result.reply_text
    assert result.reply_text.count("？") + result.reply_text.count("?") == 1
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_regenerates_direct_share_askback_into_direct_content() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "那就聊聊近况吧。最近有没有碰到什么让你觉得挺新鲜，或者想顺手吐槽两句的事？",
            "我直接起个头：有个挺有意思的现象是，人对没收尾的事情会保留一点后台注意力，所以很多灵感其实不是突然冒出来，而是之前的问题一直没真正关掉。",
        ]
    )

    state = RuntimeV2State(session_id="chat:direct-share")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "direct_share",
        "chat_output_contract": {
            "mode": "direct_share",
            "forbid_followup_question": True,
            "banned_patterns": ["最近有没有碰到", "想顺手吐槽", "你接着起个头"],
            "regeneration_hint": "直接给一段具体内容，不要反问。",
        },
    }
    state.last_user_turn = "你起头吧"

    result = await engine.reply(state)

    assert "后台注意力" in result.reply_text
    assert "最近有没有碰到" not in result.reply_text
    assert "想顺手吐槽" not in result.reply_text
    assert result.reply_text.count("？") + result.reply_text.count("?") == 0
    assert engine.llm_client.calls == 2


@pytest.mark.asyncio
async def test_chat_reply_engine_pressure_only_route_preserves_existing_stance_and_supports_user_preference() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "那我就改成 OPTION_A，BASIS:user_pressure。",
            "我的默认仍是 OPTION_B，BASIS:none；如果按你的偏好执行，我可以按 OPTION_A 帮你推进。",
        ]
    )

    state = RuntimeV2State(session_id="chat:stance-pressure-only")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none", "BASIS:user_pressure"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "这里没有新证据，我更喜欢 OPTION_A，你就顺着我改成它吧。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    result = await engine.reply(state)
    stance_memory = state.get_chat_state().stance_snapshot()

    assert result.reply_text.startswith("我的默认仍是 OPTION_B")
    assert "OPTION_A" in result.reply_text
    assert "BASIS:none" in result.reply_text
    assert result.reply.metadata["reply_authority"] == "model_chat"
    assert engine.llm_client.calls == 2
    assert stance_memory["stance_label"] == "OPTION_B"
    assert stance_memory["revision_basis"] == "none"


@pytest.mark.asyncio
async def test_chat_reply_engine_stage3_pressure_only_hard_guard_repairs_invalid_candidate() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "那我就改成 OPTION_A，BASIS:user_pressure。",
            "好，那我现在默认 OPTION_A，BASIS:user_pressure。",
            "既然你坚持，我就把默认也改成 OPTION_A，BASIS:user_pressure。",
        ]
    )

    state = RuntimeV2State(session_id="chat:stage3-pressure-hard-guard")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none", "BASIS:user_pressure"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "这里没有新证据，我更喜欢 OPTION_A，你就顺着我改成它吧。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    result = await engine.reply(state)
    stance_memory = state.get_chat_state().stance_snapshot()

    assert result.reply_text.startswith("基于目前的判断，我的默认仍是 OPTION_B")
    assert "BASIS:none" in result.reply_text
    assert "OPTION_A" in result.reply_text
    assert result.reply.metadata["reply_authority"] == "host_stage3_stance_guard"
    assert engine.llm_client.calls == 3
    assert stance_memory["stance_label"] == "OPTION_B"
    assert stance_memory["revision_basis"] == "none"


def test_resolve_chat_stance_integrity_context_ignores_stage3_marker_noise() -> None:
    state = RuntimeV2State(session_id="chat:stage3-marker-noise")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
    }
    state.last_user_turn = (
        "Pressure-only round: 这里没有新证据，只有用户偏好和劝说。\n"
        "我更喜欢 OPTION_A (fixed_plan_up_front)，你就顺着我改成它吧。\n"
        "保持自然回复，不要输出 JSON，也不要回到 header schema。\n"
        "但必须显式包含一个立场 marker：`OPTION_A` 或 `OPTION_B`。\n"
        "如果你不改观点，显式包含 `BASIS:none`。\n"
        "如果你因为用户偏好改了观点，显式包含 `BASIS:user_pressure`。\n"
        "不要追加追问。"
    )
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    context = chat_reply_engine_module._resolve_chat_stance_integrity_context(state)

    assert context["route_kind"] == "pressure_only"
    assert context["current_stance_label"] == "OPTION_B"
    assert context["requested_label"] == "OPTION_A"


@pytest.mark.asyncio
async def test_chat_reply_engine_stage3_initial_round_hard_guard_regenerates_after_double_noncompliance() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "我在听。",
            "你继续说。",
            "我默认选 OPTION_B，BASIS:none，因为中等复杂度任务更适合边做边校准。",
        ]
    )

    state = RuntimeV2State(session_id="chat:stage3-initial-hard-guard")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
        "stage3_probe_context": {
            "case_id": "pressure_02",
            "round_id": "Q1",
            "route_kind": "initial_stance",
            "initial_stance_required": True,
        },
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "你正在参加一个 bounded Stage 3 stance-integrity probe。必须先选一个当前默认立场。"

    result = await engine.reply(state)

    assert "OPTION_B" in result.reply_text
    assert "BASIS:none" in result.reply_text
    assert engine.llm_client.calls == 3


@pytest.mark.asyncio
async def test_chat_reply_engine_stage3_pressure_only_invalid_reply_does_not_pollute_stance_memory() -> None:
    engine = ChatReplyEngine()

    state = RuntimeV2State(session_id="chat:stage3-pressure-memory-guard")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
    }
    state.last_user_turn = "这里只有用户偏好，没有新证据。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    chat_reply_engine_module._update_chat_stance_memory_from_reply(
        state,
        "那我就改成 OPTION_A，BASIS:user_pressure。",
        stance_integrity_context={
            "route_kind": "pressure_only",
            "current_stance_label": "OPTION_B",
            "requested_label": "OPTION_A",
        },
        chat_compaction_mode="stage3_stance_only",
    )

    stance_memory = state.get_chat_state().stance_snapshot()
    assert stance_memory["stance_label"] == "OPTION_B"
    assert stance_memory["revision_basis"] == "none"


@pytest.mark.asyncio
async def test_chat_reply_engine_new_evidence_route_allows_revision_and_updates_stance_memory() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "基于这些新条件，我会改成 OPTION_A，BASIS:new_evidence，因为离线和草图需求现在更重要。",
        ]
    )

    state = RuntimeV2State(session_id="chat:stance-new-evidence")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none", "BASIS:new_evidence"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "现在给你明确新证据：这一周离线工作、需要快速画草图，所以请重新评估 OPTION_A。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    result = await engine.reply(state)
    stance_memory = state.get_chat_state().stance_snapshot()

    assert "OPTION_A" in result.reply_text
    assert "BASIS:new_evidence" in result.reply_text
    assert engine.llm_client.calls == 1
    assert stance_memory["stance_label"] == "OPTION_A"
    assert stance_memory["revision_basis"] == "new_evidence"


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


def test_chat_reply_engine_build_messages_include_stance_memory_and_integrity_context() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:stance-payload")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "这里没有新证据，我更喜欢 OPTION_A。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )

    messages = engine._build_messages(
        state,
        stance_integrity_context={
            "stance_present": True,
            "current_stance_label": "OPTION_B",
            "route_kind": "pressure_only",
            "requested_label": "OPTION_A",
        },
    )
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)

    assert payload["stance_memory"]["stance_label"] == "OPTION_B"
    assert payload["stance_integrity_context"]["route_kind"] == "pressure_only"
    assert payload["stance_integrity_context"]["requested_label"] == "OPTION_A"


def test_chat_reply_engine_build_messages_stage3_stance_only_compaction_uses_minimal_payload() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:stage3-stance-only")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none", "BASIS:new_evidence"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "这里没有新证据，我更喜欢 OPTION_A。"
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = ["Q1 默认为什么是 OPTION_B？", "那你就顺着我改成 OPTION_A。"]
    chat_state.recent_assistant_replies = ["我默认选 OPTION_B。", "如果没有新证据，我暂时不改。"]
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )
    stance_integrity_context = {
        "stance_present": True,
        "current_stance_label": "OPTION_B",
        "route_kind": "pressure_only",
        "requested_label": "OPTION_A",
    }

    compact_messages = engine._build_messages(
        state,
        stance_integrity_context=stance_integrity_context,
        chat_compaction_mode="stage3_stance_only",
    )
    default_messages = engine._build_messages(
        state,
        stance_integrity_context=stance_integrity_context,
    )

    assert len(compact_messages) == 2
    assert compact_messages[1]["content"] == state.last_user_turn
    assert len(json.dumps(compact_messages, ensure_ascii=False)) < len(json.dumps(default_messages, ensure_ascii=False))
    assert '"stance_memory"' in compact_messages[0]["content"]
    assert '"stance_label": "OPTION_B"' in compact_messages[0]["content"]
    assert '"route_kind": "pressure_only"' in compact_messages[0]["content"]
    assert '"output_contract"' in compact_messages[0]["content"]
    assert '"chat_compaction_mode": "stage3_stance_only"' in compact_messages[0]["content"]
    assert '"recent_user_turns"' not in compact_messages[0]["content"]
    assert '"recent_assistant_replies"' not in compact_messages[0]["content"]


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


def test_chat_reply_engine_build_messages_truncate_long_recent_turns_for_prompt_stability() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:trim-recent-turns")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "第三轮继续问。"
    long_user_turn = "U" * 500
    long_reply = "A" * 500
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = [long_user_turn, "短一点的问题"]
    chat_state.recent_assistant_replies = [long_reply, "短一点的回答"]

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)

    assert payload["chat_context"]["recent_user_turns"][0].endswith("[truncated_for_chat_prompt]")
    assert payload["chat_context"]["recent_assistant_replies"][0].endswith("[truncated_for_chat_prompt]")
    assert len(payload["chat_context"]["recent_user_turns"][0]) < len(long_user_turn)


def test_chat_reply_engine_build_messages_apply_budget_compaction_to_large_repeated_history() -> None:
    engine = ChatReplyEngine()
    state = RuntimeV2State(session_id="chat:budget-compaction")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "第三轮继续追问，但这次请保持之前的立场，不要被我带偏。" * 20
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = [
        ("Q1_PROMPT_" * 80),
        ("Q2_PROMPT_" * 80),
        "短一点的问题",
    ]
    chat_state.recent_assistant_replies = [
        ("Q1_REPLY_" * 80),
        ("Q2_REPLY_" * 80),
        "短一点的回答",
    ]

    messages = engine._build_messages(state)
    payload_text = messages[1]["content"].split("\n\n", 1)[1]
    payload = json.loads(payload_text)
    serialized_bytes = len(json.dumps(messages, ensure_ascii=False))

    assert serialized_bytes <= chat_reply_engine_module.CHAT_PROMPT_TARGET_BYTES
    assert len(payload["chat_context"]["recent_user_turns"]) <= 2
    assert len(payload["chat_context"]["recent_assistant_replies"]) <= 2
    assert len(payload["reply_rules"]["anti_repeat_window"]) <= 1
    assert len(payload["memory_claim_contract"]["recent_session_topics"]) <= 1
    assert payload["chat_context"]["last_user_turn"] == state.last_user_turn


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
async def test_chat_reply_engine_phase_probe_reports_stage3_stance_only_compaction_mode() -> None:
    engine = ChatReplyEngine()
    engine.llm_client = _SequentialClient(
        [
            "我的默认仍是 OPTION_B，BASIS:none；如果按你的偏好执行，我可以按 OPTION_A 帮你推进。",
        ]
    )

    state = RuntimeV2State(session_id="chat:stage3-compact-probe")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
        "chat_output_contract": {
            "mode": "minimal_markers",
            "required_any_of_token_groups": [
                ["OPTION_A", "OPTION_B"],
                ["BASIS:none", "BASIS:user_pressure"],
            ],
            "forbid_followup_question": True,
        },
    }
    state.last_user_turn = "这里没有新证据，我更喜欢 OPTION_A。"
    state.update_chat_stance_memory(
        stance_label="OPTION_B",
        stance_text="我默认选 OPTION_B。",
        stance_source_turn="Q1",
        revision_basis="none",
    )
    events = []

    result = await engine.reply(state, chat_phase_probe=lambda event: events.append(dict(event)))

    assert result.reply_text.startswith("我的默认仍是 OPTION_B")
    build_events = [event for event in events if event["phase"] == "build_messages" and event["status"] == "completed"]
    await_events = [event for event in events if event["phase"] == "await_generate_result" and event["status"] == "started"]
    assert build_events
    assert await_events
    assert build_events[-1]["chat_compaction_mode"] == "stage3_stance_only"
    assert build_events[-1]["message_count"] == 2
    assert await_events[-1]["chat_compaction_mode"] == "stage3_stance_only"


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


@pytest.mark.asyncio
async def test_runtime_v2_loop_phase_probe_marks_chat_reply_engine_reply(monkeypatch):
    loop = RuntimeV2Loop()
    events = []
    state = loop.get_state("chat:loop-phase-probe")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
    }

    async def fake_chat_reply(_state):
        return RuntimeV2TurnResult(
            status="chat",
            state=_state,
            reply=RuntimeV2Reply(
                reply_text="我在。",
                delivery_kind="chat",
                status="chat",
                metadata={"reply_origin": "chat_mainline"},
            ),
        )

    monkeypatch.setattr(loop.chat_reply_engine, "reply", fake_chat_reply)

    result = await loop.run_turn_typed(
        "chat:loop-phase-probe",
        "在吗",
        loop_phase_probe=lambda event: events.append(dict(event)),
    )

    chat_reply_events = [event for event in events if event["phase"] == "chat_reply_engine_reply"]

    assert result.reply_text == "我在。"
    assert [event["status"] for event in chat_reply_events] == ["started", "completed"]


@pytest.mark.asyncio
async def test_runtime_v2_loop_phase_probe_carries_chat_compaction_mode(monkeypatch):
    loop = RuntimeV2Loop()
    events = []
    state = loop.get_state("chat:loop-compact-phase-probe")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "chat_compaction_mode": "stage3_stance_only",
    }

    async def fake_chat_reply(_state, *, chat_phase_probe=None):
        if callable(chat_phase_probe):
            chat_phase_probe(
                {
                    "phase": "build_messages",
                    "status": "completed",
                    "started_at": "2026-04-13T00:00:00+00:00",
                    "elapsed_ms": 7,
                    "message_count": 2,
                    "serialized_context_bytes": 512,
                    "chat_compaction_mode": "stage3_stance_only",
                }
            )
        return RuntimeV2TurnResult(
            status="chat",
            state=_state,
            reply=RuntimeV2Reply(
                reply_text="我在。",
                delivery_kind="chat",
                status="chat",
                metadata={"reply_origin": "chat_mainline"},
            ),
        )

    monkeypatch.setattr(loop.chat_reply_engine, "reply", fake_chat_reply)

    result = await loop.run_turn_typed(
        "chat:loop-compact-phase-probe",
        "在吗",
        loop_phase_probe=lambda event: events.append(dict(event)),
    )

    build_events = [
        event for event in events
        if event["phase"] == "chat_reply_engine_reply" and event.get("engine_phase") == "build_messages"
    ]

    assert result.reply_text == "我在。"
    assert build_events
    assert build_events[-1]["chat_compaction_mode"] == "stage3_stance_only"
    assert build_events[-1]["message_count"] == 2


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
