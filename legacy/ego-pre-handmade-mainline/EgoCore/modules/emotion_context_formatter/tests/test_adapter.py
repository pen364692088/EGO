"""
Emotion Context Formatter - Adapter Tests
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapter.context_adapter import (
    EmotionFormatterAdapter,
    FormatError,
    parse_emotion_state,
    format_result_to_dict,
    create_adapter
)


class TestParseEmotionState:
    """测试情绪状态解析"""
    
    def test_valid_data(self):
        """测试有效数据"""
        data = {"valence": 0.5, "arousal": 0.3}
        state = parse_emotion_state(data)
        assert state.valence == 0.5
        assert state.arousal == 0.3
    
    def test_integer_values(self):
        """测试整数值"""
        data = {"valence": 1, "arousal": 0}
        state = parse_emotion_state(data)
        assert state.valence == 1.0
        assert state.arousal == 0.0
    
    def test_string_numbers(self):
        """测试字符串数字"""
        data = {"valence": "0.5", "arousal": "0.3"}
        state = parse_emotion_state(data)
        assert state.valence == 0.5
        assert state.arousal == 0.3
    
    def test_missing_valence(self):
        """测试缺少 valence"""
        data = {"arousal": 0.5}
        state = parse_emotion_state(data)
        assert state.valence == 0  # default
        assert state.arousal == 0.5
    
    def test_missing_arousal(self):
        """测试缺少 arousal"""
        data = {"valence": 0.5}
        state = parse_emotion_state(data)
        assert state.valence == 0.5
        assert state.arousal == 0.5  # default
    
    def test_invalid_type(self):
        """测试无效类型"""
        data = {"valence": "invalid", "arousal": 0.5}
        with pytest.raises(FormatError) as exc_info:
            parse_emotion_state(data)
        assert exc_info.value.code == "INVALID_STATE"
    
    def test_none_input(self):
        """测试 None 输入"""
        data = {"valence": None, "arousal": 0.5}
        with pytest.raises(FormatError) as exc_info:
            parse_emotion_state(data)
        assert exc_info.value.code == "INVALID_STATE"


class TestFormatResultToDict:
    """测试结果转字典"""
    
    def test_conversion(self):
        """测试正常转换"""
        from core.formatter import FormatResult
        result = FormatResult(
            formatted_context="[友好] 测试",
            emotion_applied=True,
            emotion_label="positive",
            processing_time_ms=5
        )
        
        data = format_result_to_dict(result)
        
        assert data["formatted_context"] == "[友好] 测试"
        assert data["emotion_applied"] is True
        assert data["meta"]["emotion_label"] == "positive"
        assert data["meta"]["processing_time_ms"] == 5


class TestEmotionFormatterAdapter:
    """测试适配器"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_format_context_success(self):
        """测试成功格式化"""
        result = self.adapter.format_context(
            "用户询问天气",
            {"valence": 0.5, "arousal": 0.3}
        )
        
        assert result["formatted_context"] == "[友好] 用户询问天气"
        assert result["emotion_applied"] is True
        assert result["meta"]["emotion_label"] == "positive"
    
    def test_format_context_invalid_state(self):
        """测试无效状态抛出异常"""
        with pytest.raises(FormatError) as exc_info:
            self.adapter.format_context(
                "测试",
                {"valence": "invalid"}
            )
        assert exc_info.value.code == "INVALID_STATE"
    
    def test_format_with_fallback_success(self):
        """测试带 fallback 的成功场景"""
        result = self.adapter.format_with_fallback(
            "用户询问天气",
            {"valence": 0.5, "arousal": 0.3}
        )
        
        assert result["formatted_context"] == "[友好] 用户询问天气"
        assert result["emotion_applied"] is True
    
    def test_format_with_fallback_invalid_state(self):
        """测试带 fallback 的无效状态场景"""
        result = self.adapter.format_with_fallback(
            "用户询问天气",
            {"valence": "invalid"}
        )
        
        # 应该返回 fallback 结果
        assert result["formatted_context"] == "用户询问天气"
        assert result["emotion_applied"] is False
        assert result["meta"]["emotion_label"] == "none"
    
    def test_format_with_fallback_none_state(self):
        """测试带 fallback 的 None 状态"""
        result = self.adapter.format_with_fallback(
            "用户询问天气",
            None
        )
        
        assert result["formatted_context"] == "用户询问天气"
        assert result["emotion_applied"] is False
        assert result["meta"]["emotion_label"] == "none"
    
    def test_format_with_fallback_neutral(self):
        """测试中性情绪的 fallback"""
        result = self.adapter.format_with_fallback(
            "用户询问天气",
            {"valence": 0.0, "arousal": 0.5}
        )
        
        # 中性情绪不应用格式化，但不是 fallback
        assert result["formatted_context"] == "用户询问天气"
        assert result["emotion_applied"] is False
        assert result["meta"]["emotion_label"] == "neutral"


class TestFactory:
    """测试工厂函数"""
    
    def test_create_adapter_default(self):
        """测试默认创建"""
        adapter = create_adapter()
        assert isinstance(adapter, EmotionFormatterAdapter)
    
    def test_create_adapter_custom_timeout(self):
        """测试自定义超时"""
        adapter = create_adapter(timeout_ms=200)
        assert adapter.formatter.timeout_ms == 200
