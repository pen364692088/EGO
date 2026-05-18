"""
Emotion Context Formatter - Unit Tests
"""

import pytest
import sys
from pathlib import Path

# 添加 core 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.formatter import (
    EmotionContextFormatter,
    EmotionState,
    EmotionLabel,
    create_formatter
)


class TestEmotionState:
    """测试情绪状态值对象"""
    
    def test_valid_state(self):
        """测试有效状态"""
        state = EmotionState(valence=0.5, arousal=0.3)
        assert state.valence == 0.5
        assert state.arousal == 0.3
    
    def test_valence_boundary_min(self):
        """测试 valence 最小边界"""
        state = EmotionState(valence=-1.0, arousal=0.5)
        assert state.valence == -1.0
    
    def test_valence_boundary_max(self):
        """测试 valence 最大边界"""
        state = EmotionState(valence=1.0, arousal=0.5)
        assert state.valence == 1.0
    
    def test_arousal_boundary_min(self):
        """测试 arousal 最小边界"""
        state = EmotionState(valence=0.0, arousal=0.0)
        assert state.arousal == 0.0
    
    def test_arousal_boundary_max(self):
        """测试 arousal 最大边界"""
        state = EmotionState(valence=0.0, arousal=1.0)
        assert state.arousal == 1.0
    
    def test_invalid_valence_too_low(self):
        """测试 valence 过低"""
        with pytest.raises(ValueError, match="valence must be in"):
            EmotionState(valence=-1.1, arousal=0.5)
    
    def test_invalid_valence_too_high(self):
        """测试 valence 过高"""
        with pytest.raises(ValueError, match="valence must be in"):
            EmotionState(valence=1.1, arousal=0.5)
    
    def test_invalid_arousal_negative(self):
        """测试 arousal 负数"""
        with pytest.raises(ValueError, match="arousal must be in"):
            EmotionState(valence=0.0, arousal=-0.1)
    
    def test_invalid_arousal_too_high(self):
        """测试 arousal 过高"""
        with pytest.raises(ValueError, match="arousal must be in"):
            EmotionState(valence=0.0, arousal=1.1)


class TestEmotionContextFormatter:
    """测试情绪格式化器"""
    
    def setup_method(self):
        """每个测试前创建 formatter"""
        self.formatter = create_formatter()
    
    def test_very_positive_emotion(self):
        """测试非常正面情绪"""
        state = EmotionState(valence=0.8, arousal=0.6)
        result = self.formatter.format("用户询问天气", state)
        
        assert result.formatted_context == "[热情] 用户询问天气"
        assert result.emotion_applied is True
        assert result.emotion_label == "very_positive"
        assert result.processing_time_ms >= 0
    
    def test_positive_emotion(self):
        """测试正面情绪"""
        state = EmotionState(valence=0.4, arousal=0.5)
        result = self.formatter.format("用户询问天气", state)
        
        assert result.formatted_context == "[友好] 用户询问天气"
        assert result.emotion_applied is True
        assert result.emotion_label == "positive"
    
    def test_neutral_emotion(self):
        """测试中性情绪 - 不应用格式化"""
        state = EmotionState(valence=0.0, arousal=0.5)
        result = self.formatter.format("用户询问天气", state)
        
        assert result.formatted_context == "用户询问天气"
        assert result.emotion_applied is False
        assert result.emotion_label == "neutral"
    
    def test_negative_emotion(self):
        """测试负面情绪"""
        state = EmotionState(valence=-0.4, arousal=0.5)
        result = self.formatter.format("用户询问天气", state)
        
        assert result.formatted_context == "[关切] 用户询问天气"
        assert result.emotion_applied is True
        assert result.emotion_label == "negative"
    
    def test_very_negative_emotion(self):
        """测试非常负面情绪"""
        state = EmotionState(valence=-0.8, arousal=0.5)
        result = self.formatter.format("用户询问天气", state)
        
        assert result.formatted_context == "[沉重] 用户询问天气"
        assert result.emotion_applied is True
        assert result.emotion_label == "very_negative"
    
    def test_boundary_neutral_to_positive(self):
        """测试中性到正面边界"""
        state = EmotionState(valence=0.21, arousal=0.5)
        result = self.formatter.format("测试", state)
        assert result.emotion_label == "positive"
    
    def test_boundary_neutral_to_negative(self):
        """测试中性到负面边界"""
        state = EmotionState(valence=-0.21, arousal=0.5)
        result = self.formatter.format("测试", state)
        assert result.emotion_label == "negative"
    
    def test_empty_context(self):
        """测试空上下文"""
        state = EmotionState(valence=0.5, arousal=0.5)
        result = self.formatter.format("", state)
        
        assert result.formatted_context == "[友好] "
        assert result.emotion_applied is True
    
    def test_should_apply_positive(self):
        """测试应该应用格式化的正面情绪"""
        state = EmotionState(valence=0.3, arousal=0.5)
        assert self.formatter.should_apply(state) is True
    
    def test_should_apply_negative(self):
        """测试应该应用格式化的负面情绪"""
        state = EmotionState(valence=-0.3, arousal=0.5)
        assert self.formatter.should_apply(state) is True
    
    def test_should_not_apply_neutral(self):
        """测试不应该应用格式化的中性情绪"""
        state = EmotionState(valence=0.0, arousal=0.5)
        assert self.formatter.should_apply(state) is False
    
    def test_should_not_apply_near_neutral(self):
        """测试接近中性时不应用"""
        state = EmotionState(valence=0.1, arousal=0.5)
        assert self.formatter.should_apply(state) is False


class TestFactory:
    """测试工厂函数"""
    
    def test_create_formatter_default(self):
        """测试默认创建"""
        formatter = create_formatter()
        assert isinstance(formatter, EmotionContextFormatter)
        assert formatter.timeout_ms == 100
    
    def test_create_formatter_custom_timeout(self):
        """测试自定义超时"""
        formatter = create_formatter(timeout_ms=200)
        assert formatter.timeout_ms == 200
