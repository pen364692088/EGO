"""
OpenEmotion Memory Module

三层记忆模型 v1:
- Event Memory: 原始事件存储
- Narrative Memory: 聚合/结构化叙事
- Policy Memory: 长期偏好/约束

权威源: OpenEmotion
边界: EgoCore 只能读取产物，不能定义字段语义
"""

from .event_memory import EventMemory, Event
from .narrative_memory import NarrativeMemory, Narrative
from .policy_memory import PolicyMemory, Policy

__all__ = [
    "EventMemory", "Event",
    "NarrativeMemory", "Narrative", 
    "PolicyMemory", "Policy",
]
