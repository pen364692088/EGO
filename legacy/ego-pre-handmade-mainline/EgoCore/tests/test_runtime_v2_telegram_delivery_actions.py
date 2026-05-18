from app.runtime_v2 import RuntimeV2Reply, RuntimeV2TelegramBridge, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.progress_events import ProgressEvent, ProgressEventType


def test_telegram_bridge_drops_generic_busy():
    """
    WS-4: generic busy 不再默认发送
    
    旧行为：发送 "我还在继续处理刚才那个任务。"
    新行为：drop generic busy
    """
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.task_status = "running"
    result = RuntimeV2TurnResult(
        status="waiting_input",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我还在继续处理刚才那个任务。",
            delivery_kind="progress",
            status="waiting_input",
        ),
    )
    action = bridge.plan_delivery(result, state, is_challenge_turn=False)
    # WS-4: generic busy 被 drop
    assert action.should_send is False


def test_telegram_bridge_sends_progress_events():
    """
    WS-4: 有进度事件时发送事件
    """
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    
    # 添加进度事件
    event = ProgressEvent(
        event_type=ProgressEventType.EXECUTING_STEP,
        message="开始执行第一步。",
    )
    state.push_progress_event(event)
    
    result = RuntimeV2TurnResult(
        status="waiting_input",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="",
            delivery_kind="progress",
            status="waiting_input",
        ),
    )
    
    action = bridge.plan_delivery(result, state, is_challenge_turn=False)
    assert action.should_send is True
    assert "执行" in action.text


def test_telegram_bridge_keeps_specific_progress_text_for_challenge():
    """挑战轮次保留具体进度文本"""
    bridge = RuntimeV2TelegramBridge()
    state = RuntimeV2State(session_id="telegram:dm:1")
    
    # 添加进度事件
    event = ProgressEvent(
        event_type=ProgressEventType.EXECUTING_STEP,
        message="我继续检查刚才那个文件。",
    )
    state.push_progress_event(event)
    
    result = RuntimeV2TurnResult(
        status="waiting_input",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我继续检查刚才那个文件。",
            delivery_kind="progress",
            status="waiting_input",
        ),
    )
    action = bridge.plan_delivery(result, state, is_challenge_turn=True)
    assert action.should_send is True
    assert action.text == "我继续检查刚才那个文件。"
