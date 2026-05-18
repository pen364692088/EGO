from app.interaction.classify_interaction import InteractionKind, classify_interaction
from app.runtime_v2.semantic_parser import ParsedIntentGraph, SessionControlIntent
from app.runtime_v2.state import RuntimeV2State


def test_classify_manual_resume_as_resume() -> None:
    state = RuntimeV2State(session_id="s")
    result = classify_interaction(
        "继续",
        state,
        control_intent=SessionControlIntent(kind="manual_resume"),
        runtime_action="execute_task",
    )
    assert result.kind == InteractionKind.RESUME


def test_classify_waiting_input_as_ask() -> None:
    state = RuntimeV2State(session_id="s", waiting_for_user_input=True)
    result = classify_interaction(
        "这个参数什么意思",
        state,
        control_intent=SessionControlIntent(kind="execute_task"),
        runtime_action="clarify",
    )
    assert result.kind == InteractionKind.ASK


def test_classify_task_request_as_task() -> None:
    state = RuntimeV2State(session_id="s")
    graph = ParsedIntentGraph(primary_intent="task_request")
    result = classify_interaction(
        "在这个目录下创建 demo.txt",
        state,
        graph=graph,
        control_intent=SessionControlIntent(kind="execute_task"),
        runtime_action="execute_task",
    )
    assert result.kind == InteractionKind.TASK
