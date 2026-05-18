from app.runtime.request_classifier import classify_request_fallback
from app.runtime.request_registry import RequestRegistry, RequestRecord
from app.runtime.agent_runner import _has_verified_html_effect


def test_followup_affirmative_and_style_rebind_to_active_target():
    state = {
        "active_target": "/tmp/hello.html",
        "active_artifact_path": "/tmp/hello.html",
        "artifact_context_by_path": {"/tmp/hello.html": {}}
    }
    assert classify_request_fallback("对", state)["kind"] == "follow_up"
    assert classify_request_fallback("复古科技朋克", state)["kind"] == "follow_up"
    assert classify_request_fallback("/tmp/hello.html", state)["kind"] == "follow_up"


def test_registry_unresolved_prefers_active_chain_only():
    registry = RequestRegistry()
    old_req = RequestRecord(
        request_id="req_old",
        origin_turn_id="turn_old",
        session_key="telegram:dm:1",
        objective="old",
        request_type="new_task",
        status="running",
    )
    registry.record_request(old_req)
    new_req = RequestRecord(
        request_id="req_new",
        origin_turn_id="turn_new",
        session_key="telegram:dm:1",
        objective="new",
        request_type="follow_up",
        status="running",
    )
    registry.supersede_request("req_old", "req_new")
    registry.record_request(new_req)
    unresolved = registry.get_latest_unresolved_request("telegram:dm:1")
    assert unresolved is not None
    assert unresolved.request_id == "req_new"


def test_verified_html_effect_requires_structured_observation():
    good = [{
        "success": True,
        "tool_name": "html_skill",
        "metadata": {
            "observations": [{
                "target_path": "/tmp/hello.html",
                "applied_edit": {"operation": "choose_and_set"},
                "current_state": {"background_color": "#fff"},
            }]
        }
    }]
    bad = [{
        "success": True,
        "tool_name": "file",
        "params": {"operation": "write", "path": "/tmp/hello.html"},
    }]
    assert _has_verified_html_effect(good, expected_target="/tmp/hello.html") is True
    assert _has_verified_html_effect(bad, expected_target="/tmp/hello.html") is False
