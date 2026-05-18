"""
WS-4: Progress Events / 替换 generic busy notice 测试

验证：
1. 进度事件从真实状态推进触发
2. generic busy 不再默认发送
3. terminal 后不再发 progress
4. 快任务可以直接 final
"""

import pytest
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.progress_events import (
    ProgressEvent,
    ProgressEventType,
    build_progress_event,
    is_terminal_event,
    should_emit_progress,
)
from app.runtime_v2.telegram_bridge import RuntimeV2TelegramBridge, TelegramDeliveryAction
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult


class TestProgressEvents:
    """测试进度事件构建"""
    
    def test_build_target_selected_event(self):
        """构建 target_selected 事件"""
        event = build_progress_event(
            ProgressEventType.TARGET_SELECTED,
            context="task",
            filename="测试任务单.txt",
        )
        
        assert event.event_type == ProgressEventType.TARGET_SELECTED
        assert "目标" in event.message
        assert event.target_filename == "测试任务单.txt"
    
    def test_build_executing_step_event(self):
        """构建 executing_step 事件"""
        event = build_progress_event(
            ProgressEventType.EXECUTING_STEP,
            context="step",
            step=1,
            action="创建目标文件",
        )
        
        assert event.event_type == ProgressEventType.EXECUTING_STEP
        assert event.message == "我先推进当前步骤。"

    def test_build_executing_step_event_uses_non_mechanical_file_copy(self):
        event = build_progress_event(
            ProgressEventType.EXECUTING_STEP,
            context="step",
            step=1,
            action="file",
        )

        assert event.event_type == ProgressEventType.EXECUTING_STEP
        assert event.message == "我先处理需要的文件。"
    
    def test_build_blocked_event(self):
        """构建 blocked 事件"""
        event = build_progress_event(
            ProgressEventType.BLOCKED,
            reason="default",
        )
        
        assert event.event_type == ProgressEventType.BLOCKED
        assert "卡住" in event.message
    
    def test_build_completed_event(self):
        """构建 completed 事件"""
        event = build_progress_event(ProgressEventType.COMPLETED)
        
        assert event.event_type == ProgressEventType.COMPLETED
        assert "完成" in event.message


class TestTerminalEvent:
    """测试 terminal 事件判断"""
    
    def test_completed_is_terminal(self):
        """completed 是 terminal 事件"""
        assert is_terminal_event(ProgressEventType.COMPLETED) is True
    
    def test_blocked_is_terminal(self):
        """blocked 是 terminal 事件"""
        assert is_terminal_event(ProgressEventType.BLOCKED) is True
    
    def test_executing_step_is_not_terminal(self):
        """executing_step 不是 terminal 事件"""
        assert is_terminal_event(ProgressEventType.EXECUTING_STEP) is False
    
    def test_target_selected_is_not_terminal(self):
        """target_selected 不是 terminal 事件"""
        assert is_terminal_event(ProgressEventType.TARGET_SELECTED) is False


class TestShouldEmitProgress:
    """测试进度事件发送判断"""
    
    def test_emit_progress_in_running_state(self):
        """running 状态可以发送 progress"""
        state = RuntimeV2State(session_id="test")
        state.active_turn_status = "running"
        
        event = build_progress_event(ProgressEventType.EXECUTING_STEP)
        
        assert should_emit_progress(event, state) is True
    
    def test_no_progress_after_terminal(self):
        """terminal 状态后不发 progress"""
        state = RuntimeV2State(session_id="test")
        state.active_turn_status = "terminal"
        
        event = build_progress_event(ProgressEventType.EXECUTING_STEP)
        
        assert should_emit_progress(event, state) is False
    
    def test_no_progress_after_final_sent(self):
        """final_sent 后不发 progress"""
        state = RuntimeV2State(session_id="test")
        state.final_sent = True
        
        event = build_progress_event(ProgressEventType.EXECUTING_STEP)
        
        assert should_emit_progress(event, state) is False
    
    def test_terminal_event_can_be_sent(self):
        """terminal 事件可以发送"""
        state = RuntimeV2State(session_id="test")
        state.final_sent = False
        
        event = build_progress_event(ProgressEventType.BLOCKED)
        
        assert should_emit_progress(event, state) is True


class TestProgressEventsInState:
    """测试 state 中的进度事件管理"""
    
    def test_push_and_pop_events(self):
        """添加和取出事件"""
        state = RuntimeV2State(session_id="test")
        
        event1 = build_progress_event(ProgressEventType.TARGET_SELECTED)
        event2 = build_progress_event(ProgressEventType.EXECUTING_STEP)
        
        state.push_progress_event(event1)
        state.push_progress_event(event2)
        
        assert state.has_pending_progress_events() is True
        
        events = state.pop_progress_events()
        
        assert len(events) == 2
        assert state.has_pending_progress_events() is False


class TestGenericBusyReplaced:
    """测试 generic busy 被进度事件替换"""
    
    def test_generic_busy_is_dropped(self):
        """generic busy 被 drop"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test")
        
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
        
        assert action.should_send is False
    
    def test_progress_event_is_sent(self):
        """进度事件被发送"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test")
        
        event = build_progress_event(
            ProgressEventType.EXECUTING_STEP,
            context="step",
            action="修改文件",
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
        assert action.text == "我先推进当前步骤。"
    
    def test_terminal_event_updates_delivery_type(self):
        """terminal 事件更新 last_delivery_type"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test")
        
        event = build_progress_event(ProgressEventType.BLOCKED)
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
        
        bridge.plan_delivery(result, state, is_challenge_turn=False)
        
        assert state.last_delivery_type == "blocked"


class TestNoProgressAfterFinal:
    """测试 final 后不再发 progress"""
    
    def test_no_progress_after_completed(self):
        """completed 后不发 progress"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test")
        state.task_status = "completed_verified"
        
        # 尝试发送 progress
        event = build_progress_event(ProgressEventType.EXECUTING_STEP)
        state.push_progress_event(event)
        
        result = RuntimeV2TurnResult(
            status="completed_verified",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="任务完成",
                delivery_kind="final",
                status="completed_verified",
            ),
        )
        
        # 进度事件应该被忽略，只发送 final result
        action = bridge.plan_delivery(result, state, is_challenge_turn=False)
        
        # 应该发送 final result
        assert action.should_send is True
        assert action.text == "任务完成"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
