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
