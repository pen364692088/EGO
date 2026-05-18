"""
Emotion Context Formatter - Integration Tests

模拟与主链的集成场景
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapter.context_adapter import create_adapter, FormatError


class TestIntegrationScenarios:
    """集成测试场景"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_success_path(self):
        """E2E: success 场景"""
        # 模拟 reply_pipeline 调用
        raw_context = "用户询问今天天气怎么样"
        emotion_state = {"valence": 0.7, "arousal": 0.4}  # > 0.6 才是 very_positive
        
        result = self.adapter.format_with_fallback(raw_context, emotion_state)
        
        assert result["emotion_applied"] is True
        assert "[热情]" in result["formatted_context"]
        assert result["meta"]["processing_time_ms"] >= 0
    
    def test_skip_path(self):
        """E2E: skip 场景（中性情绪）"""
        raw_context = "用户询问今天天气怎么样"
        emotion_state = {"valence": 0.0, "arousal": 0.5}
        
        result = self.adapter.format_with_fallback(raw_context, emotion_state)
        
        # 中性情绪不应用格式化
        assert result["emotion_applied"] is False
        assert result["formatted_context"] == raw_context
        assert result["meta"]["emotion_label"] == "neutral"
    
    def test_fallback_path_invalid_input(self):
        """E2E: fallback 场景（无效输入）"""
        raw_context = "用户询问今天天气怎么样"
        invalid_state = {"valence": "not_a_number"}
        
        result = self.adapter.format_with_fallback(raw_context, invalid_state)
        
        # fallback 返回原始上下文
        assert result["emotion_applied"] is False
        assert result["formatted_context"] == raw_context
        assert result["meta"]["emotion_label"] == "none"
    
    def test_fallback_path_missing_state(self):
        """E2E: fallback 场景（缺少情绪状态）"""
        raw_context = "用户询问今天天气怎么样"
        
        result = self.adapter.format_with_fallback(raw_context, None)
        
        assert result["emotion_applied"] is False
        assert result["formatted_context"] == raw_context
    
    def test_error_path(self):
        """E2E: error 场景（直接调用抛出异常）"""
        with pytest.raises(FormatError) as exc_info:
            self.adapter.format_context(
                "测试",
                {"valence": "invalid"}
            )
        
        assert exc_info.value.code == "INVALID_STATE"
        assert "input" in exc_info.value.details


class TestContractCompliance:
    """契约合规性测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_input_schema_compliance(self):
        """测试输入 schema 合规"""
        # 必填字段: raw_context, emotion_state
        result = self.adapter.format_with_fallback(
            raw_context="测试",
            emotion_state_data={
                "valence": 0.5,
                "arousal": 0.3
            }
        )
        
        # 输出应包含必填字段
        assert "formatted_context" in result
        assert "emotion_applied" in result
        assert "meta" in result
        assert "emotion_label" in result["meta"]
        assert "processing_time_ms" in result["meta"]
    
    def test_output_schema_compliance(self):
        """测试输出 schema 合规"""
        result = self.adapter.format_with_fallback(
            "测试",
            {"valence": 0.5, "arousal": 0.3}
        )
        
        # 验证字段类型
        assert isinstance(result["formatted_context"], str)
        assert isinstance(result["emotion_applied"], bool)
        assert isinstance(result["meta"]["emotion_label"], str)
        assert isinstance(result["meta"]["processing_time_ms"], int)
    
    def test_error_schema_compliance(self):
        """测试错误 schema 合规"""
        try:
            self.adapter.format_context("测试", {"valence": "invalid"})
            pytest.fail("应该抛出 FormatError")
        except FormatError as e:
            # 验证错误结构
            assert hasattr(e, 'code')
            assert hasattr(e, 'message')
            assert hasattr(e, 'details')
            assert isinstance(e.code, str)
            assert isinstance(e.message, str)


class TestBoundaryConditions:
    """边界条件测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_empty_context(self):
        """测试空上下文"""
        result = self.adapter.format_with_fallback(
            "",
            {"valence": 0.5, "arousal": 0.3}
        )
        assert result["formatted_context"] == "[友好] "
    
    def test_very_long_context(self):
        """测试超长上下文"""
        long_context = "测试" * 1000
        result = self.adapter.format_with_fallback(
            long_context,
            {"valence": 0.5, "arousal": 0.3}
        )
        assert len(result["formatted_context"]) > len(long_context)
    
    def test_special_characters(self):
        """测试特殊字符"""
        special = "测试!@#$%^&*()_+-=[]{}|;':\",./<>?"
