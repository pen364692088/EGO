import httpx
import pytest

from app.llm_client import LLMResponse
from app.runtime_v2.decision_engine import RuntimeV2DecisionEngine
from app.runtime_v2.state import RuntimeV2State


def test_decision_engine_uses_large_budget_for_html_write_requests():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:html")
    state.ingress_context = {
        "request_mode": "write",
        "requested_output": {
            "format": "html",
            "effective_path": r"D:\Project\AIProject\MyProject\Test\egocore_intro.html",
        },
    }
    assert engine._decide_max_tokens(state) == 8000


def test_decision_engine_uses_medium_budget_for_generic_write_requests():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:write")
    state.ingress_context = {
        "request_mode": "write",
        "requested_output": {
            "format": None,
        },
    }
    assert engine._decide_max_tokens(state) == 4000


def test_decision_engine_uses_small_budget_for_non_write_requests():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:chat")
    state.ingress_context = {
        "request_mode": "execute",
    }
    assert engine._decide_max_tokens(state) == 1200


def test_decision_engine_uses_configured_request_timeout(monkeypatch):
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:timeout-default")
    state.ingress_context = {"request_mode": "execute"}

    class DummyConfig:
        llm = {"request": {"timeout": 60}}

    monkeypatch.setattr("app.runtime_v2.decision_engine.get_config", lambda: DummyConfig())

    assert engine._decide_timeout_seconds(state) == 60


def test_decision_engine_boosts_timeout_for_html_writes(monkeypatch):
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:timeout-html")
    state.ingress_context = {
        "request_mode": "write",
        "requested_output": {"format": "html"},
    }

    class DummyConfig:
        llm = {"request": {"timeout": 60}}

    monkeypatch.setattr("app.runtime_v2.decision_engine.get_config", lambda: DummyConfig())

    assert engine._decide_timeout_seconds(state) == 90


def test_decision_engine_prefers_qianfan_only_model_rotation(monkeypatch):
    engine = RuntimeV2DecisionEngine()

    class DummyConfig:
        llm = {
            "default_provider": "qianfan",
            "default_model": "glm-5",
            "use_cases": {
                "execution": {"provider": "qianfan", "model": "deepseek-v3.2"},
            },
            "providers": {
                "qianfan": {
                    "enabled": True,
                    "runtime_v2_fallback_models": ["qianfan-code-latest", "glm-5"],
                }
            },
            "fallback": {
                "enabled": True,
                "providers": ["openai", "anthropic", "deepseek"],
            },
        }

        def get_llm_config_for_use_case(self, use_case):
            return self.llm["use_cases"][use_case]

    monkeypatch.setattr("app.runtime_v2.decision_engine.get_config", lambda: DummyConfig())

    assert engine._resolve_runtime_v2_client_specs() == [
        ("qianfan", "deepseek-v3.2"),
        ("qianfan", "qianfan-code-latest"),
        ("qianfan", "glm-5"),
    ]


def test_decision_engine_builds_restore_context_from_ingress_observation():
    engine = RuntimeV2DecisionEngine()
    context = engine.build_restore_context(
        {
            "restore_observation": {
                "restore_status": "partial",
                "recovery_hints_present": True,
                "standing_commitments_preview": ["protect continuity"],
            }
        }
    )
    assert "显式 restore 后的首条真实用户消息" in context
    assert "restore_status: partial" in context
    assert "protect continuity" in context


def test_decision_engine_builds_presence_check_context():
    engine = RuntimeV2DecisionEngine()
    context = engine.build_conversation_act_context(
        {
            "interaction_kind": "chat",
            "conversation_act": "presence_check",
        }
    )
    assert "interaction_kind: chat" in context
    assert "conversation_act: presence_check" in context
    assert "不是任务状态查询" in context


@pytest.mark.asyncio
async def test_decision_engine_classifies_http_500_as_transient():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:http-500")

    class DummyClient:
        def generate_with_messages(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://qianfan.baidubce.com/v2/coding/chat/completions")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)

    engine.llm_client = DummyClient()
    action = await engine.decide(state)

    assert action.type == "ask"
    assert action.raw["kind"] == "transient_decision_error"
    assert action.raw["retryable"] is True
    assert action.raw["status_code"] == 500
    assert "自动重试" in (action.question or "")


@pytest.mark.asyncio
async def test_decision_engine_marks_http_429_with_longer_retry_hint():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:http-429")

    class DummyClient:
        def generate_with_messages(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://qianfan.baidubce.com/v2/coding/chat/completions")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    engine.llm_client = DummyClient()
    action = await engine.decide(state)

    assert action.type == "ask"
    assert action.raw["kind"] == "transient_decision_error"
    assert action.raw["status_code"] == 429
    assert action.raw["retry_after_seconds"] == 45
    assert action.raw["transient_kind"] == "rate_limited"
    assert "模型繁忙" in (action.question or "")


@pytest.mark.asyncio
async def test_decision_engine_keeps_http_400_as_non_transient():
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:http-400")

    class DummyClient:
        def generate_with_messages(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://qianfan.baidubce.com/v2/coding/chat/completions")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("bad request", request=request, response=response)

    engine.llm_client = DummyClient()
    action = await engine.decide(state)

    assert action.type == "ask"
    assert action.raw["kind"] == "decision_error"
    assert action.raw["retryable"] is False
    assert action.raw["status_code"] == 400
    assert "bad request" in (action.question or "")


@pytest.mark.asyncio
async def test_decision_engine_uses_fallback_provider_after_transient_primary_failure(monkeypatch):
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:fallback")
    calls = []

    class DummyPrimaryClient:
        def generate_with_messages(self, *_args, **_kwargs):
            calls.append(("qianfan", "glm-5"))
            request = httpx.Request("POST", "https://qianfan.baidubce.com/v2/coding/chat/completions")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)

    class DummyFallbackClient:
        def generate_with_messages(self, *_args, **_kwargs):
            calls.append(("openai", "gpt-4o"))
            return LLMResponse(
                content='{"type":"chat","message":"fallback ok"}',
                model="gpt-4o",
                provider="openai",
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            )

    def fake_get_llm_client(provider=None, model=None):
        if (provider, model) == ("qianfan", "glm-5"):
            return DummyPrimaryClient()
        if (provider, model) == ("openai", "gpt-4o"):
            return DummyFallbackClient()
        raise ValueError(f"unexpected provider/model: {(provider, model)}")

    monkeypatch.setattr(
        engine,
        "_resolve_runtime_v2_client_specs",
        lambda: [("qianfan", "glm-5"), ("openai", "gpt-4o")],
    )
    monkeypatch.setattr("app.runtime_v2.decision_engine.get_llm_client", fake_get_llm_client)

    action = await engine.decide(state)

    assert action.type == "chat"
    assert action.message == "fallback ok"
    assert calls == [("qianfan", "glm-5"), ("openai", "gpt-4o")]


@pytest.mark.asyncio
async def test_decision_engine_does_not_surface_fallback_401_over_primary_transient(monkeypatch):
    engine = RuntimeV2DecisionEngine()
    state = RuntimeV2State(session_id="decision:fallback-401")
    calls = []

    class DummyPrimaryClient:
        def generate_with_messages(self, *_args, **_kwargs):
            calls.append(("qianfan", "glm-5"))
            raise httpx.ReadTimeout("The read operation timed out")

    class DummyOpenAIClient:
        def generate_with_messages(self, *_args, **_kwargs):
            calls.append(("openai", "gpt-4o"))
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    class DummyAnthropicClient:
        def generate_with_messages(self, *_args, **_kwargs):
            calls.append(("anthropic", "claude-3-5-sonnet-20241022"))
            return LLMResponse(
                content='{"type":"chat","message":"anthropic fallback ok"}',
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                usage={"input_tokens": 12, "output_tokens": 4},
            )

    def fake_get_llm_client(provider=None, model=None):
        if (provider, model) == ("qianfan", "glm-5"):
            return DummyPrimaryClient()
        if (provider, model) == ("openai", "gpt-4o"):
            return DummyOpenAIClient()
        if (provider, model) == ("anthropic", "claude-3-5-sonnet-20241022"):
            return DummyAnthropicClient()
        raise ValueError(f"unexpected provider/model: {(provider, model)}")

    monkeypatch.setattr(
        engine,
        "_resolve_runtime_v2_client_specs",
        lambda: [
            ("qianfan", "glm-5"),
            ("openai", "gpt-4o"),
            ("anthropic", "claude-3-5-sonnet-20241022"),
        ],
    )
    monkeypatch.setattr("app.runtime_v2.decision_engine.get_llm_client", fake_get_llm_client)

    action = await engine.decide(state)

    assert action.type == "chat"
    assert action.message == "anthropic fallback ok"
    assert calls == [
        ("qianfan", "glm-5"),
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
    ]
