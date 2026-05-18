from app.runtime.request_classifier import classify_request_fallback
from app.runtime.task_planning import build_minimal_task_plan
from app.runtime.request_registry import RequestRegistry, RequestRecord


def test_case1_explicit_path_enters_task_chain():
    text = "/home/moonlight/demo/test.html 背景颜色不太好看,你选一个好看的颜色"
    out = classify_request_fallback(text, session_state={})
    assert out["kind"] == "new_task"
    assert out["force_target_path"] == "/home/moonlight/demo/test.html"


def test_case2_agent_choice_not_missing_operation():
    text = "/home/moonlight/demo/test.html 背景颜色不太好看,你选一个好看的颜色"
    plan = build_minimal_task_plan(text, {"artifact_context_by_path": {}, "active_target": None})
    assert plan.plan_steps
    step = plan.plan_steps[0]
    assert step["kind"] == "batch_edit_artifacts"
    assert step["edits"][0]["operation"] == "choose_and_set"


def test_case3_single_target_new_request_no_old_fanout():
    text = "/home/moonlight/demo/test.html 背景颜色不太好看,你选一个好看的颜色"
    session_state = {
        "artifact_context_by_path": {
            "/home/moonlight/demo/test.html": {},
            "/home/moonlight/demo/hello.html": {},
        },
        "active_target": "/home/moonlight/demo/hello.html",
    }
    plan = build_minimal_task_plan(text, session_state)
    step = plan.plan_steps[0]
    targets = [t["path"] for t in step["targets"]]
    assert targets == ["/home/moonlight/demo/test.html"]


def test_case4_unresolved_request_tracking_baseline():
    registry = RequestRegistry()
    req = RequestRecord(
        request_id="req_1",
        origin_turn_id="turn_1",
        session_key="telegram:dm:1",
        objective="/home/a/test.html 背景颜色改好看",
        request_type="new_task",
        status="running",
    )
    registry.record_request(req)
    unresolved = registry.get_latest_unresolved_request("telegram:dm:1")
    assert unresolved is not None
    assert unresolved.request_id == "req_1"
