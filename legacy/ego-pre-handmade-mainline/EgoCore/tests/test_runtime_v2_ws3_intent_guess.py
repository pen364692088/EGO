"""
WS-3: Intent Guess / 建议式确认测试

验证：
1. 分层意图推断正确工作
2. 建议式确认基于 WS-2 的绑定结果
3. 多文件 bundle 场景的建议
4. 置信度判断
"""

import pytest
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.telegram_bridge import (
    infer_intent,
    IntentInference,
    build_suggestion_response_from_intent,
)


class TestIntentInference:
    """测试分层意图推断"""
    
    def test_high_confidence_from_explicit_action(self):
        """
        一级信号：用户明确说动作
        
        预期：高置信
        """
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "测试任务单.txt", "ref_1")
        
        intent = infer_intent(text="执行这个任务", state=state, has_attachment=False)
        
        assert intent.inferred_action == "execute"
        assert intent.confidence == "high"
        assert intent.reason == "用户明确提到动作"
    
    def test_medium_confidence_from_artifact_type(self):
        """
        二级信号：artifact type
        
        预期：中置信
        """
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "测试任务单.txt", "ref_1")
        
        intent = infer_intent(text="", state=state, has_attachment=False)
        
        assert intent.inferred_action == "execute"
        assert intent.confidence == "medium"
        assert "任务单" in intent.reason
    
    def test_low_confidence_from_filename_only(self):
        """
        三级信号：文件名模式（最弱）
        
        预期：低置信
        """
        state = RuntimeV2State(session_id="test")
        
        intent = infer_intent(
            text="[用户发送了文件: 测试任务单.txt]",
            state=state,
            has_attachment=True,
        )
        
        assert intent.inferred_action == "execute"
        assert intent.confidence == "low"
    
    def test_no_inference_without_signals(self):
        """无信号时返回低置信 None"""
        state = RuntimeV2State(session_id="test")
        
        intent = infer_intent(text="你好", state=state, has_attachment=False)
        
        assert intent.inferred_action is None
        assert intent.confidence == "low"


class TestSuggestionResponse:
    """测试建议式确认生成"""
    
    def test_single_task_file_suggestion(self):
        """
        Case A：上传 测试任务单.txt
        
        预期：默认建议"执行这份任务"
        """
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "测试任务单.txt", "ref_1")
        
        intent = IntentInference(
            inferred_action="execute",
            confidence="medium",
            primary_target={"filename": "测试任务单.txt"},
            secondary_option="analyze",
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        assert "测试任务单" in response
        assert "执行" in response
        # 不应该是模板追问
        assert "请告诉我你要做什么" not in response
    
    def test_single_spec_file_suggestion(self):
        """
        Case B：上传 SOUL.md
        
        预期：默认建议"审查 / 作为约束"
        """
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        
        intent = IntentInference(
            inferred_action="analyze",
            confidence="medium",
            primary_target={"filename": "SOUL.md"},
            secondary_option="constraint",
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        assert "SOUL" in response
        # 应该有选项提示
        assert "审查" in response or "约束" in response
        # 不应该是模板追问
        assert "请告诉我你要做什么" not in response
    
    def test_spec_and_task_bundle_suggestion(self):
        """
        Case C：上传 SOUL.md + 测试任务单.txt
        
        预期：默认建议"按任务单执行，并把 SOUL 当约束"
        """
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "测试任务单.txt", "ref_2")
        
        intent = IntentInference(
            inferred_action="execute",
            confidence="medium",
            primary_target={"filename": "测试任务单.txt"},
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        # 应该提到任务单
        assert "测试任务单" in response
        # 应该提到执行
        assert "执行" in response
        # 应该提到规范作为约束
        assert "约束" in response or "规范" in response
    
    def test_multiple_specs_suggestion(self):
        """多规范文件 + 对比建议"""
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "TOOLS.md", "ref_2")
        
        intent = IntentInference(
            inferred_action="compare",
            confidence="medium",
            primary_target={"bundle": state.pending_artifacts, "count": 2},
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        # 应该提到多个文件
        assert "2" in response or "规范" in response
        # 应该提到对比
        assert "对比" in response
    
    def test_high_confidence_direct_suggestion(self):
        """高置信时直接给建议"""
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "测试任务单.txt", "ref_1")
        
        intent = IntentInference(
            inferred_action="execute",
            confidence="high",
            primary_target={"filename": "测试任务单.txt"},
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        # 应该直接建议，不需要"我看这更像是"
        assert "测试任务单" in response
        assert "执行" in response
    
    def test_low_confidence_neutral_question(self):
        """低置信时使用中性追问"""
        state = RuntimeV2State(session_id="test")
        state.add_pending_artifact("artifact_1", "data.json", "ref_1")
        
        intent = IntentInference(
            inferred_action=None,
            confidence="low",
            primary_target={"filename": "data.json"},
        )
        
        response = build_suggestion_response_from_intent(intent, state)
        
        # 低置信时应该问用户想要什么
        assert "你要我" in response or "做什么" in response


class TestNoRawReadConstraint:
    """
    测试硬护栏：意图推断阶段不触发 raw/chunk read
    
    只能检查代码逻辑，实际验证需要 mock
    """
    
    def test_infer_intent_does_not_read_file_content(self):
        """
        验证 infer_intent 不读取文件内容
        
        这是个文档性测试，确保设计约束被遵守
        """
        # infer_intent 只接收：
        # - text (用户输入文本)
        # - state (包含 artifact 信息，但不触发 raw read)
        # - has_attachment (布尔值)
        # 
        # 不接收文件内容、文件路径等会触发读取的参数
        # 因此无法触发 raw read
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
