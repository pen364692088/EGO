"""
OpenEmotion Result v1 - 正式输出类型

对应 schema: schemas/openemotion_result_v1.schema.json
用途: OpenEmotion → EgoCore 的标准输出格式

版本: v1.0.0
冻结状态: FROZEN (不允许破坏性修改)

重要: v1 只保留程序真正消费的字段，自由文本只作解释层。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ResultType(str, Enum):
    """结果类型"""
    INTERPRETATION = "interpretation"
    MEMORY_UPDATE = "memory_update"
    POLICY_CHANGE = "policy_change"
    ERROR = "error"


class HintType(str, Enum):
    """策略提示类型"""
    PREFER = "prefer"
    AVOID = "avoid"
    ESCALATE = "escalate"
    DEFER = "defer"
    IGNORE = "ignore"


class ResponseTone(str, Enum):
    """响应语调"""
    WARM = "warm"
    NEUTRAL = "neutral"
    GUARDED = "guarded"
    APOLOGETIC = "apologetic"
    ENTHUSIASTIC = "enthusiastic"
    CAUTIOUS = "cautious"


class ResponseLength(str, Enum):
    """响应长度"""
    BRIEF = "brief"
    MODERATE = "moderate"
    DETAILED = "detailed"


@dataclass
class SelfModelDelta:
    """自我模型变化"""
    field: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = None


@dataclass
class MemoryUpdate:
    """记忆更新"""
    event_stored: bool = False
    narrative_created: bool = False
    policy_candidate: bool = False
    salience_score: float = 0.0


@dataclass
class PolicyHint:
    """策略提示（给 EgoCore 参考）"""
    hint_type: HintType
    reason: Optional[str] = None
    confidence: float = 0.0
    expires_at: Optional[datetime] = None


@dataclass
class ResponseTendency:
    """响应倾向（给 EgoCore 参考，非强制）"""
    tone: ResponseTone = ResponseTone.NEUTRAL
    length: ResponseLength = ResponseLength.MODERATE
    urgency: float = 0.5


@dataclass
class Stability:
    """稳定性指标"""
    self_model_stable: bool = True
    memory_integrity: bool = True
    policy_consistent: bool = True


@dataclass
class Error:
    """错误信息"""
    code: str
    message: str
    recoverable: bool = False


@dataclass
class OpenEmotionResultV1:
    """
    OpenEmotion 正式输出 v1

    用途: OpenEmotion → EgoCore 的标准输出格式
    版本: v1.0.0
    冻结: 是

    重要: EgoCore 程序端只消费结构字段，自由文本只作解释层。
    """

    # 必需字段
    event_id: str
    result_type: ResultType
    confidence: float

    # 可选字段 - 程序真正消费的字段
    self_model_delta: Optional[SelfModelDelta] = None
    memory_update: Optional[MemoryUpdate] = None
    policy_hint: Optional[PolicyHint] = None
    response_tendency: Optional[ResponseTendency] = None
    stability: Optional[Stability] = None
    error: Optional[Error] = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "result_type": self.result_type.value,
            "self_model_delta": self._self_model_delta_to_dict(),
            "memory_update": self._memory_update_to_dict(),
            "policy_hint": self._policy_hint_to_dict(),
            "response_tendency": self._response_tendency_to_dict(),
            "confidence": self.confidence,
            "stability": self._stability_to_dict(),
            "error": self._error_to_dict(),
            "processing_time_ms": self.processing_time_ms,
        }

    def _self_model_delta_to_dict(self) -> Optional[dict]:
        if not self.self_model_delta:
            return None
        return {
            "field": self.self_model_delta.field,
            "old_value": self.self_model_delta.old_value,
            "new_value": self.self_model_delta.new_value,
            "reason": self.self_model_delta.reason,
        }

    def _memory_update_to_dict(self) -> Optional[dict]:
        if not self.memory_update:
            return None
        return {
            "event_stored": self.memory_update.event_stored,
            "narrative_created": self.memory_update.narrative_created,
            "policy_candidate": self.memory_update.policy_candidate,
            "salience_score": self.memory_update.salience_score,
        }

    def _policy_hint_to_dict(self) -> Optional[dict]:
        if not self.policy_hint:
            return None
        return {
            "hint_type": self.policy_hint.hint_type.value,
            "reason": self.policy_hint.reason,
            "confidence": self.policy_hint.confidence,
            "expires_at": self.policy_hint.expires_at.isoformat() if self.policy_hint.expires_at else None,
        }

    def _response_tendency_to_dict(self) -> Optional[dict]:
        if not self.response_tendency:
            return None
        return {
            "tone": self.response_tendency.tone.value,
            "length": self.response_tendency.length.value,
            "urgency": self.response_tendency.urgency,
        }

    def _stability_to_dict(self) -> Optional[dict]:
        if not self.stability:
            return None
        return {
            "self_model_stable": self.stability.self_model_stable,
            "memory_integrity": self.stability.memory_integrity,
            "policy_consistent": self.stability.policy_consistent,
        }

    def _error_to_dict(self) -> Optional[dict]:
        if not self.error:
            return None
        return {
            "code": self.error.code,
            "message": self.error.message,
            "recoverable": self.error.recoverable,
        }


# 版本标记
RESULT_V1_VERSION = "1.0.0"
RESULT_V1_FROZEN = True
