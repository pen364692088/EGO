from app.runtime_v2 import RuntimeV2TelegramBridge
from app.runtime_v2.state import RuntimeV2State


def test_telegram_bridge_plans_pre_runtime_no_early_return_for_natural_language_status():
    """自然语言进度词退出 control-plane，不再 host 早返回。"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"
    decision = bridge.inspect_ingress("好了吗", state)
    action = bridge.plan_pre_runtime(decision, state)
    assert decision.absorb_as_busy_notice is False
    assert decision.interaction_kind == "chat"
    assert action.should_return_early is False
    assert action.busy_notice_text is None
    assert action.ack_text is None
    assert action.direct_reply_text is None


def test_telegram_bridge_plans_no_ack_for_task():
    """任务不再发送 generic ACK"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("/home/moonlight/test.html 配色不太好看", state)
    action = bridge.plan_pre_runtime(decision, state)
    assert action.should_return_early is False
    assert action.ack_text is None  # 不再发送 generic ACK


def test_telegram_bridge_binds_explicit_path_target_for_read_request():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.add_pending_artifact(
        artifact_id="artifact://compacted/task-sheet",
        filename="P3_closure_real_probe_task.txt",
        artifact_ref="artifact://compacted/task-sheet",
    )

    decision = bridge.inspect_ingress(r"读取 D:\Project\AIProject\MyProject\Test\missing_closure_probe.md 前 1 行", state)
    ingress_context = bridge.build_ingress_context(decision, state)

    assert decision._runtime_action == "execute_task"
    assert ingress_context["resolved_target"]["source"] == "explicit_path"
    assert ingress_context["resolved_target"]["path"].endswith(r"missing_closure_probe.md")
