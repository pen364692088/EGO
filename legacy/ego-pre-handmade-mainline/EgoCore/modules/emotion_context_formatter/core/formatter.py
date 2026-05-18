"""
Emotion Context Formatter - Core Module

纯业务逻辑，无副作用。
负责根据情绪状态格式化上下文。
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import time


class EmotionLabel(Enum):
    """情绪标签"""
    VERY_NEGATIVE = "very_negative"    # valence < -0.6
    NEGATIVE = "negative"               # -0.6 <= valence < -0.2
    NEUTRAL = "neutral"                 # -0.2 <= valence <= 0.2
    POSITIVE = "positive"               # 0.2 < valence <= 0.6
    VERY_POSITIVE = "very_positive"     # valence > 0.6


@dataclass(frozen=True)
class EmotionState:
    """情绪状态值对象"""
    valence: float   # -1 to 1
    arousal: float   # 0 to 1
    
    def __post_init__(self):
        if not -1 <= self.valence <= 1:
            raise ValueError(f"valence must be in [-1, 1], got {self.valence}")
        if not 0 <= self.arousal <= 1:
            raise ValueError(f"arousal must be in [0, 1], got {self.arousal}")


@dataclass(frozen=True)
class FormatResult:
    """格式化结果"""
    formatted_context: str
    emotion_applied: bool
    emotion_label: str
    processing_time_ms: int


class EmotionContextFormatter:
    """情绪上下文格式化器"""
    
    # 情绪标签映射
    LABEL_MAP = [
        (-0.6, EmotionLabel.VERY_NEGATIVE),
        (-0.2, EmotionLabel.NEGATIVE),
        (0.2, EmotionLabel.NEUTRAL),
        (0.6, EmotionLabel.POSITIVE),
        (float('inf'), EmotionLabel.VERY_POSITIVE),
    ]
    
    # 情绪前缀模板
    PREFIX_TEMPLATES = {
        EmotionLabel.VERY_NEGATIVE: "[沉重] ",
        EmotionLabel.NEGATIVE: "[关切] ",
        EmotionLabel.NEUTRAL: "",
        EmotionLabel.POSITIVE: "[友好] ",
        EmotionLabel.VERY_POSITIVE: "[热情] ",
    }
    
    def __init__(self, timeout_ms: int = 100):
        self.timeout_ms = timeout_ms
    
    def format(self, raw_context: str, emotion_state: EmotionState) -> FormatResult:
        """
        根据情绪状态格式化上下文
        
        Args:
            raw_context: 原始上下文
            emotion_state: 情绪状态
            
        Returns:
            FormatResult: 格式化结果
        """
        start_time = time.time()
        
        # 确定情绪标签
        emotion_label = self._classify_emotion(emotion_state)
        
        # 获取前缀
        prefix = self.PREFIX_TEMPLATES.get(emotion_label, "")
        
        # 格式化
        if prefix:
            formatted = f"{prefix}{raw_context}"
            applied = True
        else:
            formatted = raw_context
            applied = False
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return FormatResult(
            formatted_context=formatted,
            emotion_applied=applied,
            emotion_label=emotion_label.value,
            processing_time_ms=processing_time_ms
        )
    
    def _classify_emotion(self, state: EmotionState) -> EmotionLabel:
        """根据 valence 分类情绪"""
        for threshold, label in self.LABEL_MAP:
            if state.valence <= threshold:
                return label
        return EmotionLabel.NEUTRAL  # fallback
    
    def should_apply(self, emotion_state: EmotionState) -> bool:
        """判断是否应该应用情绪格式化"""
        # 中性情绪不应用格式化
        return emotion_state.valence < -0.2 or emotion_state.valence > 0.2


def create_formatter(timeout_ms: int = 100) -> EmotionContextFormatter:
    """工厂函数"""
    return EmotionContextFormatter(timeout_ms=timeout_ms)
