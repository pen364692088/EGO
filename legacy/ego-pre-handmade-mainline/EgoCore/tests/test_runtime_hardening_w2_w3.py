from app.runtime.agent_runner import _normalize_artifact_edit
from app.runtime.task_planning import build_minimal_task_plan


def test_normalize_agent_choice_to_choose_and_set():
    edit = {
        "target_path": "/tmp/test.html",
        "property": "background_color",
        "value": "agent_choice",
    }
    out = _normalize_artifact_edit(edit)
    assert out["operation"] == "choose_and_set"
    assert out["value_policy"] == "agent_choice"
    assert out["target_scope"] == out["scope"]


def test_explicit_path_should_not_fan_out_old_targets():
    session_state = {
        "artifact_context_by_path": {
            "/home/a/test.html": {},
            "/home/a/hello.html": {},
        },
        "active_target": "/home/a/hello.html",
    }
    user_input = "/home/a/test.html 背景颜色不太好看,你选一个好看的颜色"
    plan = build_minimal_task_plan(user_input, session_state)
    assert plan.plan_steps, "plan should be generated"
    step = plan.plan_steps[0]
    targets = step.get("targets", [])
    assert len(targets) == 1
    assert targets[0]["path"] == "/home/a/test.html"
    edits = step.get("edits", [])
    assert edits and edits[0]["target_path"] == "/home/a/test.html"
