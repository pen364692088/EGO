import pytest

from app.runtime_v2 import RuntimeV2TelegramBridge
from app.runtime_v2.state import RuntimeV2State


def test_telegram_bridge_explicit_file_task_with_path_is_task_request():
    """路径 + 明确修改任务应直达 task_request，不要误降成 reference_material。"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("/home/moonlight/test.html 配色不太好看,你换一个好看的颜色", state)

    assert decision.looks_like_task is True
    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._parsed_intent_graph.requires_clarification is False
    assert decision.ack_text is None  # 不再发送 generic ACK

    assert decision._runtime_action == "execute_task"


def test_telegram_bridge_path_only_is_reference_material():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("/home/moonlight/test.html", state)
    assert decision.looks_like_task is False
    assert decision._parsed_intent_graph.primary_intent == "reference_material"
    assert decision._runtime_action == "waiting_input"


def test_telegram_bridge_short_probe_now_stays_in_chat_mainline():
    """自然语言进度词已退出 control-plane，按聊天处理。"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"

    decision = bridge.inspect_ingress("好了吗", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.interaction_kind == "chat"
    assert decision._runtime_action == "chat"
    assert decision._parsed_intent_graph.primary_intent == "chat"
    assert ingress["conversation_act"] == "social_keepalive"


def test_telegram_bridge_presence_probe_when_idle_falls_back_to_chat():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("在吗", state)
    assert decision.is_short_probe is False
    assert decision._runtime_action == "chat"
    assert decision._parsed_intent_graph.primary_intent == "chat"


def test_telegram_bridge_presence_probe_even_if_busy_stays_chat() -> None:
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"

    decision = bridge.inspect_ingress("还在吗", state)

    assert decision.is_short_probe is False
    assert decision._runtime_action == "chat"
    assert decision._parsed_intent_graph.primary_intent == "chat"


def test_telegram_bridge_marks_challenge_turn_programmatically():
    """挑战轮次应由程序化入口直接识别，避免前置 parser LLM。"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"

    decision = bridge.inspect_ingress("你没改啊", state)
    assert decision.is_challenge_turn is True
    assert decision._runtime_action == "repair_or_reframe"
    assert decision._parsed_intent_graph.primary_intent == "correction"


def test_telegram_bridge_discussion_not_task():
    """heuristic parser 只处理显式硬信号。讨论性句式需要 LLM 识别。"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")

    decision = bridge.inspect_ingress("你觉得要怎么实现比较好？", state)
    assert decision.looks_like_task is False
    assert decision.ack_text is None


def test_telegram_bridge_explicit_command():
    """显式命令应该被 heuristic 识别为 task_request"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("/status", state)
    assert decision.looks_like_task is True
    assert decision._parsed_intent_graph.primary_intent == "task_request"


def test_telegram_bridge_attachment_is_reference_material():
    """附件应该被识别为 reference_material"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("[用户发送了文件: test.html]", state)

    assert decision.looks_like_task is False
    assert decision._parsed_intent_graph.primary_intent == "reference_material"
    assert decision._parsed_intent_graph.requires_clarification is True


def test_telegram_bridge_chat_default():
    """普通聊天应该被识别为 chat"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    decision = bridge.inspect_ingress("你好", state)

    assert decision.looks_like_task is False
    assert decision._parsed_intent_graph.primary_intent == "chat"


def test_telegram_bridge_extracts_requested_output_for_html_page():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    text = r"你能帮我在D:\Project\AIProject\MyProject\Test里创建一个介绍egocore的页面吗"
    decision = bridge.inspect_ingress(text, state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.looks_like_task is True
    assert decision._runtime_action == "execute_task"
    assert ingress["requested_output"]["format"] == "html"
    assert ingress["requested_output"]["target_is_directory"] is True
    assert ingress["requested_output"]["effective_path"] == r"D:\Project\AIProject\MyProject\Test\egocore_intro.html"
    assert ingress["requested_output"]["topic"] == "EgoCore"


def test_telegram_bridge_promotes_execute_confirmation_for_pending_task():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.add_pending_artifact("artifact://task", "任务单.txt", "artifact://task")
    state.last_inferred_action = "execute"
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True

    decision = bridge.inspect_ingress("执行", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.is_confirm_execution is True
    assert decision.looks_like_task is True
    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "execute"
    assert ingress["resolved_target"]["artifact_id"] == "artifact://task"


def test_telegram_bridge_bare_continue_on_planning_stalled_task_stays_chat_with_resume_hint():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.add_pending_artifact("artifact://task", "任务单.txt", "artifact://task")
    state.last_inferred_action = "execute"
    state.task_contract = {"task_id": "contract_1"}
    state.contract_phase = "planning_stalled"
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True

    decision = bridge.inspect_ingress("继续", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.is_confirm_execution is False
    assert decision.interaction_kind == "chat"
    assert decision._runtime_action == "chat"
    assert ingress["conversation_act"] == "light_chitchat"
    assert ingress["resume_hint_eligible"] is True


def test_telegram_bridge_marks_continue_say_family_as_thread_continue():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")

    decision = bridge.inspect_ingress("继续说 多说点", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.interaction_kind == "chat"
    assert decision._runtime_action == "chat"
    assert ingress["conversation_act"] == "thread_continue"


def test_telegram_bridge_bare_continue_after_chat_reply_becomes_thread_continue():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.last_model_action = {"type": "chat", "message": "上一条回复"}
    state.last_delivery_type = "chat"
    state.get_chat_state().recent_assistant_replies = ["上一条回复"]

    decision = bridge.inspect_ingress("继续", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision.interaction_kind == "chat"
    assert decision._runtime_action == "chat"
    assert ingress["conversation_act"] == "thread_continue"
    assert ingress["resume_hint_eligible"] is False


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
    assert ingress_context["request_mode"] == "analyze"
    assert ingress_context["resolved_target"]["source"] == "explicit_path"
    assert ingress_context["resolved_target"]["path"].endswith(r"missing_closure_probe.md")


def test_telegram_bridge_promotes_full_read_followup_to_previous_explicit_target():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.last_explicit_target = r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"

    decision = bridge.inspect_ingress("继续读取完整内容，不要截断", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["resolved_target"]["source"] == "explicit_path"
    assert ingress["resolved_target"]["path"] == r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"


def test_telegram_bridge_promotes_recent_result_review_followup_to_analyze():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    decision = bridge.inspect_ingress("你打开看看呢", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["resolved_target"]["path"] == r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"


def test_telegram_bridge_promotes_recent_result_issue_feedback_to_analyze():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    decision = bridge.inspect_ingress("排版有些问题 你检查一下", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["resolved_target"]["path"] == r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"


def test_telegram_bridge_promotes_recent_result_confirmation_after_clarification_to_analyze():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }
    state.get_chat_state().recent_assistant_replies.append("好的，你是指刚才那个页面排版吗？")

    decision = bridge.inspect_ingress("对", state)
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.primary_intent == "task_request"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["resolved_target"]["path"] == r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_handles_ordinary_discussion_question():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "你觉得什么才是构建一个有自我意识的AI最核心的框架?", "kind": "small_talk", "confidence": 0.92}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic(
        "你觉得什么才是构建一个有自我意识的AI最核心的框架?",
        state,
        llm_client=MockLLMClient(),
    )

    assert decision._parsed_intent_graph.parser_source == "semantic_parser"
    assert decision.interaction_kind == "chat"
    assert decision._runtime_action == "chat"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_prefers_recent_result_issue_feedback():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    class MockLLMClient:
        async def complete(self, prompt):
            assert "recent_delivered_result_context" in prompt
            class Response:
                content = '{"segments": [{"text": "排版有些问题 你检查一下", "kind": "task_request", "confidence": 0.95, "refers_to_previous": true, "target_ref": "D:\\\\Project\\\\AIProject\\\\MyProject\\\\Test2\\\\bilili_lookalike.html", "request_mode": "analyze"}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic("排版有些问题 你检查一下", state, llm_client=MockLLMClient())
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.parser_source == "semantic_parser"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_handles_recent_result_confirmation():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }
    state.get_chat_state().recent_assistant_replies.append("好的，你是指刚才那个页面排版吗？")

    class MockLLMClient:
        async def complete(self, prompt):
            assert "last_assistant_reply" in prompt
            class Response:
                content = '{"segments": [{"text": "对", "kind": "task_request", "confidence": 0.94, "refers_to_previous": true, "target_ref": "D:\\\\Project\\\\AIProject\\\\MyProject\\\\Test2\\\\bilili_lookalike.html", "request_mode": "analyze"}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic("对", state, llm_client=MockLLMClient())
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.parser_source == "semantic_parser"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_handles_recent_result_correction_without_chat_fallback():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "没有改啊 搜索按钮跑到搜索框下面了", "kind": "correction", "confidence": 0.96, "refers_to_previous": true, "target_ref": "D:\\\\Project\\\\AIProject\\\\MyProject\\\\Test2\\\\bilili_lookalike.html"}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic(
        "没有改啊 搜索按钮跑到搜索框下面了",
        state,
        llm_client=MockLLMClient(),
    )

    assert decision._parsed_intent_graph.parser_source == "semantic_parser"
    assert decision._runtime_action != "chat"
    assert decision._parsed_intent_graph.primary_intent in {"correction", "task_request"}


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_promotes_recent_result_modify_feedback_to_analyze():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "顶部导航栏右边的图标换一下", "kind": "small_talk", "confidence": 0.61}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic(
        "顶部导航栏右边的图标换一下",
        state,
        llm_client=MockLLMClient(),
    )
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._parsed_intent_graph.parser_source == "semantic_parser"
    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["recent_result_binding"] is True


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_promotes_pending_continuation_write_permission():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }
    state.set_pending_result_continuation(
        {
            "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
            "target_name": "bilili_lookalike.html",
            "requested_mode": "analyze",
            "status": "pending",
            "bound_to_recent_result": True,
        }
    )

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "你先换个你觉得好看的", "kind": "small_talk", "confidence": 0.62}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic("你先换个你觉得好看的", state, llm_client=MockLLMClient())
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "write"
    assert ingress["resolved_target"]["path"] == r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_status_followup_with_pending_continuation_becomes_runtime_status():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.set_pending_result_continuation(
        {
            "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
            "target_name": "bilili_lookalike.html",
            "requested_mode": "write",
            "status": "pending",
            "bound_to_recent_result": True,
        }
    )

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "改了吗", "kind": "status_query", "confidence": 0.95}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic("改了吗", state, llm_client=MockLLMClient())
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._runtime_action == "return_runtime_status"
    assert ingress["conversation_act"] == "status_probe"
    assert ingress["pending_result_continuation"]["requested_mode"] == "write"


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_recent_result_correction_sets_correction_context():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.set_pending_result_continuation(
        {
            "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
            "target_name": "bilili_lookalike.html",
            "requested_mode": "write",
            "status": "pending",
            "bound_to_recent_result": True,
        }
    )

    class MockLLMClient:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "还是没修改哦", "kind": "small_talk", "confidence": 0.52}]}'
            return Response()

    decision = await bridge.inspect_ingress_semantic("还是没修改哦", state, llm_client=MockLLMClient())
    ingress = bridge.build_ingress_context(decision, state)

    assert decision._runtime_action == "execute_task"
    assert ingress["request_mode"] == "analyze"
    assert ingress["correction_context"] is True


@pytest.mark.asyncio
async def test_telegram_bridge_semantic_parser_falls_back_cleanly_on_llm_error():
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")

    class FailingLLMClient:
        async def complete(self, prompt):
            raise RuntimeError("provider transient failure")

    decision = await bridge.inspect_ingress_semantic("你好", state, llm_client=FailingLLMClient())

    assert decision._parsed_intent_graph.parser_source == "chat_default"
    assert decision._runtime_action == "chat"
