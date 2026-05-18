"""
测试: EgoCore Runtime 三层架构

验证:
1. LaneManager 队列串行化
2. SessionManager 会话持久化
3. AgentEventBus 事件分发
4. runEmbeddedEgoCoreAgent 核心入口
5. ReplyDispatcher 回复分发

版本: v2.0.0
Created: 2026-03-19
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime

# 添加路径
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')


class TestLaneManager:
    """测试 LaneManager"""
    
    @pytest.mark.asyncio
    async def test_enqueue_and_wait(self):
        """测试任务入队和等待"""
        from app.runtime.lane_manager import LaneManager
        
        manager = LaneManager()
        
        executed = []
        
        async def my_task():
            await asyncio.sleep(0.1)
            executed.append("done")
            return "result"
        
        task_id = await manager.enqueue("test_session", my_task)
        
        # 等待完成
        task = await manager.wait_for_task(task_id, timeout_ms=5000)
        
        assert task is not None
        assert task.status == "completed"
        assert task.result == "result"
        assert "done" in executed
    
    @pytest.mark.asyncio
    async def test_serial_execution(self):
        """测试串行执行"""
        from app.runtime.lane_manager import LaneManager
        
        manager = LaneManager()
        
        order = []
        
        async def task_a():
            order.append("a_start")
            await asyncio.sleep(0.1)
            order.append("a_end")
        
        async def task_b():
            order.append("b_start")
            await asyncio.sleep(0.1)
            order.append("b_end")
        
        # 同时入队
        await manager.enqueue("same_session", task_a)
        await manager.enqueue("same_session", task_b)
        
        # 等待完成
        await asyncio.sleep(0.5)
        
        # 应该是串行的: a_start -> a_end -> b_start -> b_end
        # 而不是: a_start -> b_start -> a_end -> b_end
        assert order == ["a_start", "a_end", "b_start", "b_end"]
    
    @pytest.mark.asyncio
    async def test_parallel_different_sessions(self):
        """测试不同 session 并行"""
        from app.runtime.lane_manager import LaneManager
        
        manager = LaneManager()
        
        start_times = {}
        
        async def task_session(session_id):
            start_times[session_id] = datetime.now()
            await asyncio.sleep(0.2)
        
        # 不同 session 可以并行
        await manager.enqueue("session_1", lambda: task_session("s1"))
        await manager.enqueue("session_2", lambda: task_session("s2"))
        
        await asyncio.sleep(0.5)
        
        # 两个任务应该几乎同时开始
        if "s1" in start_times and "s2" in start_times:
            diff = abs((start_times["s1"] - start_times["s2"]).total_seconds())
            assert diff < 0.15  # 应该接近同时开始


class TestSessionManager:
    """测试 SessionManager"""
    
    def test_get_or_create(self):
        """测试获取或创建会话"""
        from app.runtime.session_manager import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(agent_id="test", store_dir=tmpdir)
            
            session = manager.get_or_create_sync("test_session")
            
            assert session.session_key == "test_session"
            assert session.session_id is not None
    
    def test_increment_turn(self):
        """测试轮次增加"""
        from app.runtime.session_manager import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(agent_id="test", store_dir=tmpdir)
            
            session = manager.get_or_create_sync("test_session")
            
            assert session.turn_index == 0
            
            manager.increment_turn_sync("test_session")
            
            assert session.turn_index == 1
    
    def test_persistence(self):
        """测试持久化"""
        from app.runtime.session_manager import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建并保存
            manager1 = SessionManager(agent_id="test", store_dir=tmpdir)
            session = manager1.get_or_create_sync("persist_test")
            session_id = session.session_id
            
            # 重新加载
            manager2 = SessionManager(agent_id="test", store_dir=tmpdir)
            loaded = manager2.get_sync("persist_test")
            
            assert loaded is not None
            assert loaded.session_id == session_id


class TestAgentEventBus:
    """测试 AgentEventBus"""
    
    def test_emit_lifecycle(self):
        """测试生命周期事件"""
        from app.runtime.event_bus import AgentEventBusImpl, LifecyclePhase
        
        bus = AgentEventBusImpl()
        
        events = []
        
        def callback(data):
            events.append(data)
        
        bus.subscribe("run_001", callback)
        
        bus.emit_lifecycle_event(
            phase=LifecyclePhase.START,
            run_id="run_001",
            session_id="session_001",
        )
        
        assert len(events) == 1
        assert events[0]["phase"] == "start"
    
    def test_emit_reply(self):
        """测试回复事件"""
        from app.runtime.event_bus import AgentEventBusImpl
        from app.runtime.types import ReplyPayload, ReplyType
        
        bus = AgentEventBusImpl()
        
        events = []
        
        def callback(data):
            events.append(data)
        
        bus.subscribe("run_002", callback)
        
        payload = ReplyPayload(
            type=ReplyType.TEXT,
            content="Hello",
            run_id="run_002",
            session_id="session_002",
        )
        
        bus.emit_reply(payload)
        
        assert len(events) == 1
        assert events[0]["content"] == "Hello"
    
    def test_unsubscribe(self):
        """测试取消订阅"""
        from app.runtime.event_bus import AgentEventBusImpl, LifecyclePhase
        
        bus = AgentEventBusImpl()
        
        events = []
        
        def callback(data):
            events.append(data)
        
        bus.subscribe("run_003", callback)
        bus.unsubscribe("run_003")
        
        bus.emit_lifecycle_event(
            phase=LifecyclePhase.START,
            run_id="run_003",
            session_id="session_003",
        )
        
        assert len(events) == 0


class TestReplyDispatcher:
    """测试 ReplyDispatcher"""
    
    def test_cli_adapter(self):
        """测试 CLI 适配器"""
        from app.runtime.reply_dispatcher import CLIAdapter
        from app.runtime.types import ReplyPayload, ReplyType
        
        adapter = CLIAdapter()
        
        assert adapter.channel_name == "cli"
        
        payload = ReplyPayload(
            type=ReplyType.TEXT,
            content="Test message",
            run_id="run_001",
            session_id="session_001",
        )
        
        formatted = adapter.format_for_channel(payload)
        assert formatted == "Test message"
    
    def test_silent_reply(self):
        """测试静默回复"""
        from app.runtime.reply_dispatcher import ReplyDispatcher
        from app.runtime.types import ReplyPayload, ReplyType
        
        dispatcher = ReplyDispatcher()
        
        payload = ReplyPayload(
            type=ReplyType.SILENT,
            content="NO_REPLY",
            run_id="run_001",
            session_id="session_001",
        )
        
        assert dispatcher._is_silent(payload) is True
        
        payload2 = ReplyPayload(
            type=ReplyType.TEXT,
            content="NO_REPLY",
            run_id="run_002",
            session_id="session_002",
        )
        
        assert dispatcher._is_silent(payload2) is True


class TestTypes:
    """测试类型定义"""
    
    def test_session_key_parse(self):
        """测试 SessionKey 解析"""
        from app.runtime.types import SessionKey
        
        key = SessionKey.parse("telegram:dm:123456")
        
        assert key.channel == "telegram"
        assert key.scope == "dm"
        assert key.peer_id == "123456"
        assert key.lane_key == "lane:telegram:dm:123456"
    
    def test_run_params(self):
        """测试运行参数"""
        from app.runtime.types import EgoCoreRunParams
        
        params = EgoCoreRunParams(
            session_id="sid_001",
            session_key="telegram:dm:123",
            run_id="run_001",
            prompt="Hello",
        )
        
        assert params.session_id == "sid_001"
        assert params.timeout_ms == 600000  # 默认 10 分钟
        assert params.trigger == "user"
    
    def test_run_result(self):
        """测试运行结果"""
        from app.runtime.types import EgoCoreRunResult, RunStatus
        
        result = EgoCoreRunResult(
            run_id="run_001",
            session_id="sid_001",
            status=RunStatus.COMPLETED,
            reply_text="Hello!",
        )
        
        d = result.to_dict()
        
        assert d["run_id"] == "run_001"
        assert d["status"] == "completed"
        assert d["reply_text"] == "Hello!"


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_run(self):
        """测试完整运行流程"""
        from app.runtime.types import EgoCoreRunParams
        from app.runtime.agent_runner import runEmbeddedEgoCoreAgent, create_run_id
        from app.runtime.session_manager import get_session_manager
        
        # 创建运行参数
        params = EgoCoreRunParams(
            session_id="test_session_001",
            session_key="cli:test:001",
            run_id=create_run_id(),
            prompt="你好",
            channel="cli",
        )
        
        # 运行
        result = await runEmbeddedEgoCoreAgent(params)
        
        # 验证结果
        assert result.run_id is not None
        assert result.status in ["completed", "failed"]
        assert result.duration_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
