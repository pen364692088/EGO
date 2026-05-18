"""
Emotion Context Formatter - Adapter Module

负责外部上下文转换和依赖注入。
将外部输入转换为 core 可处理的格式。
"""

from typing import Dict, Any, Optional
from core.formatter import (
    EmotionContextFormatter,
    EmotionState,
    FormatResult,
    create_formatter
)


class FormatError(Exception):
    """格式化错误"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def parse_emotion_state(data: Dict[str, Any]) -> EmotionState:
    """
    解析情绪状态
    
    Args:
        data: 原始情绪状态数据
        
    Returns:
        EmotionState: 解析后的情绪状态
        
    Raises:
        FormatError: 解析失败
    """
    try:
        valence = float(data.get("valence", 0))
        arousal = float(data.get("arousal", 0.5))
        return EmotionState(valence=valence, arousal=arousal)
    except (TypeError, ValueError) as e:
        raise FormatError(
            code="INVALID_STATE",
            message=f"Invalid emotion state: {e}",
            details={"input": data}
        )


def format_result_to_dict(result: FormatResult) -> Dict[str, Any]:
    """
    将结果转换为字典格式
    
    Args:
        result: 格式化结果
        
    Returns:
        Dict: 输出字典
    """
    return {
        "formatted_context": result.formatted_context,
        "emotion_applied": result.emotion_applied,
        "meta": {
            "emotion_label": result.emotion_label,
            "processing_time_ms": result.processing_time_ms
        }
    }


class EmotionFormatterAdapter:
    """情绪格式化适配器"""
    
    def __init__(self, timeout_ms: int = 100):
        self.formatter = create_formatter(timeout_ms=timeout_ms)
    
    def format_context(self, raw_context: str, emotion_state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化上下文（适配器入口）
        
        Args:
            raw_context: 原始上下文
            emotion_state_data: 情绪状态数据
            
        Returns:
            Dict: 格式化结果
            
        Raises:
            FormatError: 格式化失败
        """
        # 解析情绪状态
        emotion_state = parse_emotion_state(emotion_state_data)
        
        # 调用 core
        result = self.formatter.format(raw_context, emotion_state)
        
        # 转换输出
        return format_result_to_dict(result)
    
    def format_with_fallback(self, raw_context: str, emotion_state_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        带 fallback 的格式化
        
        Args:
            raw_context: 原始上下文
            emotion_state_data: 情绪状态数据（可选）
            
        Returns:
            Dict: 格式化结果或 fallback 结果
        """
        try:
            if emotion_state_data is None:
                raise FormatError(
                    code="INVALID_STATE",
                    message="emotion_state is required"
                )
            return self.format_context(raw_context, emotion_state_data)
        except FormatError:
            # Fallback: 返回原始上下文
            return {
                "formatted_context": raw_context,
                "emotion_applied": False,
                "meta": {
                    "emotion_label": "none",
                    "processing_time_ms": 0
                }
            }


def create_adapter(timeout_ms: int = 100) -> EmotionFormatterAdapter:
    """工厂函数"""
    return EmotionFormatterAdapter(timeout_ms=timeout_ms)
