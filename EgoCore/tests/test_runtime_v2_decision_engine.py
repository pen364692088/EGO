import httpx
import pytest

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
