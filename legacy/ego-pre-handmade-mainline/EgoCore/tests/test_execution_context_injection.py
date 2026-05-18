"""
防回归测试: Execution Context Injection

测试场景:
- 场景A: 任务请求上下文注入
- 场景B: 失败任务修复上下文
- 场景C: 能力确认句不进入任务链 (live 防回归)
- 场景D: 无真实落地不标记 completed (live 防回归)
- 场景E: 失败反馈关联上一任务 (live 防回归)

Created: 2026-03-19
Updated: 2026-03-19 (v2.1: 添加 live 防回归)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')


class TestContextAssembler:
    """测试 ContextAssembler"""
    
    def test_assemble_basic_context(self):
        """测试基本上下文组装"""
        from app.runtime.context_assembler import ContextAssembler, ExecutionContext
        
        assembler = ContextAssembler()
        
        context = assembler.assemble(
            user_input="你好",
            session_id="test_session",
            user_id="test_user",
        )
        
        # 验证返回类型
        assert isinstance(context, ExecutionContext)
        
        # 验证必要字段存在
        assert context.conversation_context.session_id == "test_session"
        assert context.task_context is not None
        assert context.runtime_summary is not None
        assert context.safety_context is not None
        assert context.repair_context is not None
    
    def test_assemble_with_active_task(self):
        """测试带活动任务的上下文组装"""
        from app.runtime.context_assembler import ContextAssembler
        
        assembler = ContextAssembler()
        
        active_task = {
            "task_id": "task_001",
            "goal": "创建 hello world 网页",
            "status": "in_progress",
            "current_step": 1,
            "total_steps": 3,
        }
        
        context = assembler.assemble(
            user_input="继续",
            session_id="test_session",
            user_id="test_user",
            active_task=active_task,
        )
        
        # 验证任务上下文注入
        assert context.task_context.active_task_id == "task_001"
        assert context.task_context.task_goal == "创建 hello world 网页"
        assert context.task_context.current_step_index == 1
    
    def test_extract_execution_tracking(self):
        """测试执行追踪信息提取"""
        from app.runtime.context_assembler import ContextAssembler
        
        assembler = ContextAssembler()
        
        # 测试文件创建
        context = assembler.assemble(
            user_input="帮我在 /tmp/hello.html 创建 hello world 网页",
            session_id="test_session",
            user_id="test_user",
        )
        
        assert context.target_path == "/tmp/hello.html"
        assert context.expected_side_effect == "file_created"
        assert context.tool_capability == "file_write"
    
    def test_safety_context_high_risk(self):
        """测试高风险操作识别"""
        from app.runtime.context_assembler import ContextAssembler
        
        assembler = ContextAssembler()
        
        context = assembler.assemble(
            user_input="删除 /tmp/important 文件",
            session_id="test_session",
            user_id="test_user",
        )
        
        assert context.safety_context.risk_level == "high"
        assert context.safety_context.requires_approval is True

    def test_safety_context_matches_canonical_git_push(self):
        """git push 应与 canonical risk scorer 一致归到高风险。"""
        from app.runtime.context_assembler import ContextAssembler

        assembler = ContextAssembler()
        context = assembler.assemble(
            user_input="git push origin main",
            session_id="test_session",
            user_id="test_user",
        )

        assert context.safety_context.risk_level == "high"
        assert context.safety_context.requires_approval is True


class TestCompletionGuard:
    """测试 CompletionGuard"""
    
    def test_verify_file_operation_success(self):
        """测试文件操作验证 - 成功"""
        from app.runtime.completion_guard import CompletionGuard, CompletionStatus
        import tempfile
        import os
        
        guard = CompletionGuard()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("hello world")
            temp_path = f.name
        
        try:
            result = guard.verify(
                task_type="file",
                task_goal="创建文件",
                execution_result={"tool_result": {"success": True}},
                target_path=temp_path,
            )
            
            assert result.status == CompletionStatus.COMPLETED
            assert result.verified is True
            assert any("存在" in e for e in result.evidence)
        finally:
            os.unlink(temp_path)
    
    def test_verify_file_operation_failure(self):
        """测试文件操作验证 - 失败"""
        from app.runtime.completion_guard import CompletionGuard, CompletionStatus
        
        guard = CompletionGuard()
        
        result = guard.verify(
            task_type="file",
            task_goal="创建文件",
            execution_result={"tool_result": {"success": True}},
            target_path="/nonexistent/path/file.txt",
        )
        
        # 文件不存在，应该是 UNVERIFIED 或 INCOMPLETE
        assert result.status in [CompletionStatus.INCOMPLETE, CompletionStatus.UNVERIFIED]
        assert result.verified is False
        assert any("不存在" in m for m in result.missing)
    
    def test_verify_without_execution_result(self):
        """测试没有执行结果时的验证"""
        from app.runtime.completion_guard import CompletionGuard, CompletionStatus
        
        guard = CompletionGuard()
        
        result = guard.verify(
            task_type="file",
            task_goal="创建文件",
            execution_result=None,
        )
        
        assert result.status == CompletionStatus.UNVERIFIED
        assert result.verified is False
        assert "execution_result" in result.missing
    
    def test_classify_task_type(self):
        """测试任务类型分类"""
        from app.runtime.completion_guard import CompletionGuard
        
        guard = CompletionGuard()
        
        assert guard.classify_task_type("创建 hello.html") == "file"
        assert guard.classify_task_type("运行测试") == "test"
        assert guard.classify_task_type("git push") == "git"
        assert guard.classify_task_type("执行脚本") == "command"
        assert guard.classify_task_type("随便聊聊") == "general"


class TestRepairContextManager:
    """测试 RepairContextManager"""
    
    def test_record_failure(self):
        """测试记录失败"""
        from app.runtime.repair_context_manager import RepairContextManager
        
        manager = RepairContextManager()
        
        record = manager.record_failure(
            task_id="task_001",
            session_id="session_001",
            user_id="user_001",
            task_goal="创建 hello.html",
            failure_reason="文件不存在",
        )
        
        assert record.task_id == "task_001"
        assert record.failure_reason == "文件不存在"
        assert record.resolved is False
    
    def test_detect_user_feedback(self):
        """测试检测用户反馈中的失败指示"""
        from app.runtime.repair_context_manager import RepairContextManager
        
        manager = RepairContextManager()
        
        # 先记录一个失败
        manager.record_failure(
            task_id="task_001",
            session_id="session_001",
            user_id="user_001",
            task_goal="创建 hello.html",
            failure_reason="写入失败",
        )
        
        # 检测用户反馈
        record = manager.detect_user_feedback(
            user_input="文件并不存在",
            session_id="session_001",
            user_id="user_001",
        )
        
        assert record is not None
        assert record.user_feedback == "文件并不存在"
    
    def test_get_repair_context(self):
        """测试获取修复上下文"""
        from app.runtime.repair_context_manager import RepairContextManager
        
        manager = RepairContextManager()
        
        # 记录失败
        manager.record_failure(
            task_id="task_001",
            session_id="session_001",
            user_id="user_001",
            task_goal="创建 hello.html",
            failure_reason="权限不足",
        )
        
        # 获取修复上下文
        ctx = manager.get_repair_context("session_001", "user_001")
        
        assert ctx.has_pending_repair is True
        assert ctx.failed_task_id == "task_001"
        assert ctx.failure_reason == "权限不足"
    
    def test_mark_resolved(self):
        """测试标记已解决"""
        from app.runtime.repair_context_manager import RepairContextManager
        
        manager = RepairContextManager()
        
        # 记录失败
        manager.record_failure(
            task_id="task_001",
            session_id="session_001",
            user_id="user_001",
            task_goal="创建 hello.html",
            failure_reason="写入失败",
        )
        
        # 标记解决
        result = manager.mark_resolved("session_001", "user_001")
        assert result is True
        
        # 验证已解决
        ctx = manager.get_repair_context("session_001", "user_001")
        assert ctx.has_pending_repair is False


class TestScenarioA_TaskRequestContext:
    """
    场景A: 任务请求上下文注入
    
    用户说:
    - "现在你能帮我写代码吗"
    - "帮我在 /path 创建 hello world 网页"
    
    断言: 执行上下文中包含 target_path、expected_side_effect、tool_capability
    """
    
    def test_scenario_a_task_request(self):
        """测试场景A: 任务请求上下文注入"""
        from app.runtime.context_assembler import ContextAssembler
        
        assembler = ContextAssembler()
        
        # 模拟用户请求创建网页
        context = assembler.assemble(
            user_input="帮我在 /var/www/hello.html 创建 hello world 网页",
            session_id="session_001",
            user_id="user_001",
        )
        
        # 断言: 上下文包含执行追踪信息
        assert context.target_path is not None, "target_path 应该被提取"
        assert "/var/www/hello.html" in context.target_path or "hello.html" in context.target_path
        assert context.expected_side_effect is not None, "expected_side_effect 应该被识别"
        assert context.tool_capability is not None, "tool_capability 应该被识别"
        
        print(f"✓ 场景A 验证通过:")
        print(f"  target_path: {context.target_path}")
        print(f"  expected_side_effect: {context.expected_side_effect}")
        print(f"  tool_capability: {context.tool_capability}")


class TestScenarioB_FileNotExistsRepair:
    """
    场景B: 文件不存在修复上下文
    
    条件: 若未真实写入文件，则断言 status != completed
    用户说: "文件并不存在"
    断言: repair_context 包含上一轮失败信息
    """
    
    def test_scenario_b_file_not_exists(self):
        """测试场景B: 文件不存在修复上下文"""
        from app.runtime.repair_context_manager import RepairContextManager
        from app.runtime.completion_guard import CompletionGuard, CompletionStatus
        
        manager = RepairContextManager()
        guard = CompletionGuard()
        
        # 1. 模拟任务执行（但文件未真正创建）
        execution_result = {
            "tool_result": {"success": True},
            "output": "模拟成功",
        }
        
        # 2. 验证完成状态 - 文件不存在，应该是 incomplete
        result = guard.verify(
            task_type="file",
            task_goal="创建 /tmp/nonexistent.html",
            execution_result=execution_result,
            target_path="/tmp/nonexistent.html",
        )
        
        # 断言: status != completed
        assert result.status != CompletionStatus.COMPLETED, "文件不存在时不应标记为 completed"
        
        # 3. 记录失败
        manager.record_failure(
            task_id="task_002",
            session_id="session_002",
            user_id="user_002",
            task_goal="创建 /tmp/nonexistent.html",
            failure_reason="文件未真实创建",
            execution_result=execution_result,
        )
        
        # 4. 用户反馈
        user_feedback = "文件并不存在"
        record = manager.detect_user_feedback(
            user_input=user_feedback,
            session_id="session_002",
            user_id="user_002",
        )
        
        # 断言: repair_context 包含上一轮失败信息
        assert record is not None, "应该检测到失败反馈"
        assert record.task_id == "task_002", "应该关联到失败任务"
        assert record.user_feedback == user_feedback, "应该包含用户反馈"
        
        # 5. 获取修复上下文
        repair_ctx = manager.get_repair_context("session_002", "user_002")
        
        assert repair_ctx.has_pending_repair is True, "应该有待修复任务"
        assert repair_ctx.failed_task_id == "task_002", "应该包含失败任务 ID"
        assert repair_ctx.failure_reason is not None, "应该包含失败原因"
        
        print(f"✓ 场景B 验证通过:")
        print(f"  status: {result.status.value} (不是 completed)")
        print(f"  has_pending_repair: {repair_ctx.has_pending_repair}")
        print(f"  failed_task_id: {repair_ctx.failed_task_id}")
        print(f"  failure_reason: {repair_ctx.failure_reason}")


class TestEventBuilderExecutionContext:
    """测试 EventBuilder.build_from_execution_context"""
    
    def test_build_from_execution_context(self):
        """测试从执行上下文构建事件"""
        from app.openemotion_adapter.event_builder import EventBuilder
        from app.runtime.context_assembler import ContextAssembler, ExecutionContext
        
        builder = EventBuilder()
        assembler = ContextAssembler()
        
        # 组装上下文
        context = assembler.assemble(
            user_input="创建文件",
            session_id="session_001",
            user_id="user_001",
            chat_id="chat_001",
            active_task={"task_id": "task_001", "goal": "创建文件"},
        )
        
        # 构建事件
        event = builder.build_from_execution_context(
            execution_context=context,
            content="创建文件",
        )
        
        # 验证事件包含完整上下文
        assert "conversation_context" in event
        assert "task_context" in event
        assert "runtime_summary" in event
        assert "safety_context" in event
        
        # 验证任务上下文
        assert event["task_context"]["active_task_id"] == "task_001"
        
        print(f"✓ EventBuilder.build_from_execution_context 验证通过")
        print(f"  event_id: {event['event_id']}")
        print(f"  has task_context: {event['task_context']['has_task']}")


class TestScenarioC_CapabilityQueryNotTask:
    """
    场景C: 能力确认句不进入任务链 (live 防回归)
    
    用户说: "现在你能帮我写代码吗"
    
    断言:
    - intent != NEW_TASK
    - 应为 CHAT 或 QUESTION
    """
    
    def test_scenario_c_capability_query(self):
        """测试场景C: 能力确认句不进入任务链"""
        from app.runtime.semantic_router import classify_message, SemanticIntent
        
        # 模拟用户能力确认句
        test_messages = [
            "现在你能帮我写代码吗",
            "你现在能做什么？",
            "你能帮我写代码吗？",
        ]
        
        for msg in test_messages:
            result = classify_message(msg)
            
            # 断言: 不应该是 NEW_TASK
            assert result.intent != SemanticIntent.NEW_TASK, \
                f"'{msg}' 不应该被分类为 NEW_TASK，实际是 {result.intent.value}"
            
            # 断言: 应该是 CHAT 或 QUESTION
            assert result.intent in [SemanticIntent.CHAT, SemanticIntent.QUESTION], \
                f"'{msg}' 应该是 CHAT 或 QUESTION，实际是 {result.intent.value}"
            
            print(f"✓ 场景C 验证通过: '{msg}' -> {result.intent.value}")


class TestScenarioD_NoRealExecutionNotCompleted:
    """
    场景D: 无真实落地不标记 completed (live 防回归)
    
    条件: 任务声明"无法直接执行"但被标记为 completed
    
    断言:
    - CompletionGuard 应阻止 completed
    - status 应该是 blocked 或 needs_user_action
    """
    
    def test_scenario_d_no_real_execution(self):
        """测试场景D: 无真实执行不标记 completed"""
        from app.runtime.completion_guard import (
            CompletionGuard, CompletionStatus
        )
        import tempfile
        import os
        
        guard = CompletionGuard()
        
        # 模拟：任务说"无法直接执行"，但 execution_result 表示成功
        execution_result = {
            "success": True,
            "output": "由于我无法直接执行命令，我将提供操作指南...",
            "tool_result": {"success": True, "output": "模拟成功"},
        }
        
        # 目标文件不存在
        target_path = "/tmp/nonexistent_test_file_12345.html"
        
        # 验证完成状态
        result = guard.verify(
            task_type="file",
            task_goal="创建 hello world 网页",
            execution_result=execution_result,
            target_path=target_path,
        )
        
        # 断言: 不应该是 COMPLETED
        assert result.status != CompletionStatus.COMPLETED, \
            f"文件不存在时不应标记为 completed，实际是 {result.status.value}"
        
        # 断言: 应该是 INCOMPLETE 或 UNVERIFIED
        assert result.status in [CompletionStatus.INCOMPLETE, CompletionStatus.UNVERIFIED], \
            f"应该是 INCOMPLETE 或 UNVERIFIED，实际是 {result.status.value}"
        
        print(f"✓ 场景D 验证通过: status={result.status.value}")
        print(f"  missing: {result.missing}")


class TestScenarioE_FailureFeedbackLinked:
    """
    场景E: 失败反馈关联上一任务 (live 防回归)
    
    用户说: "文件并不存在啊" / "没有落地"
    
    断言:
    - repair_context 被检测
    - 关联到上一失败任务
    - 不是新开泛化问答
    """
    
    def test_scenario_e_failure_feedback_linked(self):
        """测试场景E: 失败反馈关联上一任务"""
        from app.runtime.repair_context_manager import RepairContextManager
        
        manager = RepairContextManager()
        
        # 1. 先记录一个失败任务
        manager.record_failure(
            task_id="task_live_001",
            session_id="session_live_001",
            user_id="user_live_001",
            task_goal="创建 hello.html",
            failure_reason="文件未真实创建",
        )
        
        # 2. 用户反馈"文件并不存在"
        user_feedback = "文件并不存在啊"
        
        record = manager.detect_user_feedback(
            user_input=user_feedback,
            session_id="session_live_001",
            user_id="user_live_001",
        )
        
        # 断言: 检测到失败反馈
        assert record is not None, \
            "应该检测到失败反馈"
        
        # 断言: 关联到失败任务
        assert record.task_id == "task_live_001", \
            f"应该关联到 task_live_001，实际是 {record.task_id}"
        
        # 断言: 包含用户反馈
        assert record.user_feedback == user_feedback, \
            f"应该包含用户反馈"
        
        # 3. 获取修复上下文
        repair_ctx = manager.get_repair_context("session_live_001", "user_live_001")
        
        # 断言: 有待修复任务
        assert repair_ctx.has_pending_repair, \
            "应该有待修复任务"
        
        # 断言: 关联正确
        assert repair_ctx.failed_task_id == "task_live_001", \
            f"应该关联到 task_live_001"
        
        print(f"✓ 场景E 验证通过:")
        print(f"  has_pending_repair: {repair_ctx.has_pending_repair}")
        print(f"  failed_task_id: {repair_ctx.failed_task_id}")
        print(f"  failure_reason: {repair_ctx.failure_reason}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
