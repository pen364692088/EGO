"""
WS-1: Turn Isolation / Reset 真隔离测试

验证：
1. /new 后 generation_id 递增
2. 旧 generation 的消息被 drop
3. final_sent 后的 busy/progress 被 drop
"""

import pytest
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.telegram_bridge import RuntimeV2TelegramBridge
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult


class TestGenerationIsolation:
    """测试 generation 隔离"""
    
    def test_increment_generation(self):
        """验证 increment_generation 递增 generation_id"""
        state = RuntimeV2State(session_id="test_session")
        assert state.generation_id == 0
        
        new_gen = state.increment_generation()
        assert new_gen == 1
        assert state.generation_id == 1
        
        state.increment_generation()
        assert state.generation_id == 2
    
    def test_increment_generation_resets_state(self):
        """验证 increment_generation 重置相关状态"""
        state = RuntimeV2State(session_id="test_session")
        state.task_status = "running"
        state.current_goal = "some goal"
        state.final_sent = True
        state.active_turn_id = "turn_123"
        state.active_turn_status = "running"
        
        state.increment_generation()
        
        assert state.task_status == "idle"
        assert state.current_goal is None
        assert state.final_sent is False
        assert state.active_turn_id is None
        assert state.active_turn_status == "idle"
    
    def test_start_turn(self):
        """验证 start_turn 创建新 turn_id"""
        state = RuntimeV2State(session_id="test_session")
        
        turn_id = state.start_turn()
        assert turn_id.startswith("turn_")
        assert state.active_turn_id == turn_id
        assert state.active_turn_status == "running"
    
    def test_is_stale_delivery_generation_mismatch(self):
        """验证 generation 不匹配时消息被标记为 stale"""
        state = RuntimeV2State(session_id="test_session")
        state.generation_id = 2
        
        # generation 1 的消息应该被 drop
        assert state.is_stale_delivery(generation_id=1) is True
        
        # generation 2 的消息不应该被 drop
        assert state.is_stale_delivery(generation_id=2) is False
    
    def test_is_stale_delivery_turn_terminal(self):
        """验证 turn 已 terminal 时旧 turn 消息被 drop"""
        state = RuntimeV2State(session_id="test_session")
        state.generation_id = 1
        state.active_turn_id = "turn_new"
        state.active_turn_status = "terminal"
        
        # 旧 turn 的消息应该被 drop
        assert state.is_stale_delivery(generation_id=1, turn_id="turn_old") is True
        
        # 当前 turn 的消息不应该被 drop
        assert state.is_stale_delivery(generation_id=1, turn_id="turn_new") is False
    
    def test_should_drop_progress(self):
        """验证 final_sent 后的 busy/progress 被 drop"""
        state = RuntimeV2State(session_id="test_session")
        
        # 正常情况不 drop
        assert state.should_drop_progress() is False
        
        # final_sent 后应该 drop
        state.final_sent = True
        assert state.should_drop_progress() is True
        
        # terminal 状态也应该 drop
        state.final_sent = False
        state.active_turn_status = "terminal"
        assert state.should_drop_progress() is True


class TestResetSession:
    """测试 reset_session 隔离"""
    
    def test_reset_session_increments_generation(self):
        """验证 reset_session 递增 generation_id"""
        loop = RuntimeV2Loop()
        
        # 第一次创建 state
        state = loop.get_state("test_session")
        assert state.generation_id == 0
        
        # reset 后 generation_id 应该递增
        loop.reset_session("test_session")
        state = loop.get_state("test_session")
        assert state.generation_id == 1
    
    def test_reset_session_clears_history(self):
        """验证 reset_session 清空 history"""
        loop = RuntimeV2Loop()
        state = loop.get_state("test_session")
        state.history.append({"role": "user", "content": {"text": "hello"}})
        
        loop.reset_session("test_session")
        state = loop.get_state("test_session")
        assert len(state.history) == 0


class TestDeliveryStaleCheck:
    """测试 delivery stale check"""
    
    def test_plan_delivery_drops_stale_generation(self):
        """验证 plan_delivery drop 过期 generation 的消息"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test_session")
        state.generation_id = 2
        
        # 创建一个 generation=1 的 reply
        result = RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="test message",
                delivery_kind="chat",
                status="chat",
                generation_id=1,
            ),
        )
        
        action = bridge.plan_delivery(result, state, is_challenge_turn=False)
        assert action.should_send is False
    
    def test_plan_delivery_drops_progress_after_final(self):
        """验证 plan_delivery drop final_sent 后的 progress"""
        bridge = RuntimeV2TelegramBridge()
        state = RuntimeV2State(session_id="test_session")
        state.final_sent = True
        
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
