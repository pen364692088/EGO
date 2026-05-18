"""
OpenEmotion Result v1 Contract

符合 oe.result.v1 规范的完整结果结构。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import json


class ResponseMode(str, Enum):
    REPLY = "reply"
    TASK = "task"
    BLOCK = "block"
    ASK = "ask"
    ESCALATE = "escalate"


class ResponseTone(str, Enum):
    CALM = "calm"
    WARM = "warm"
    GUARDED = "guarded"
    NEUTRAL = "neutral"


@dataclass
class MemoryUpdate:
    """记忆更新"""
    write_events: List[Dict[str, Any]] = field(default_factory=list)
    write_narrative: List[Dict[str, Any]] = field(default_factory=list)
    write_policy: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.write_events:
            result["write_events"] = self.write_events
        if self.write_narrative:
            result["write_narrative"] = self.write_narrative
        if self.write_policy:
            result["write_policy"] = self.write_policy
        return result


@dataclass
class AppraisalStateDelta:
    """评估状态变化"""
    trust: float = 0.0
    caution: float = 0.0
    frustration: float = 0.0
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trust": self.trust,
            "caution": self.caution,
            "frustration": self.frustration,
            "joy": self.joy,
            "sadness": self.sadness,
            "anger": self.anger,
        }


@dataclass
class ResponseTendency:
    """响应倾向"""
    mode: ResponseMode = ResponseMode.REPLY
    tone: ResponseTone = ResponseTone.CALM
    goal: str = "answer_and_continue"
    suggested_reply_outline: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "tone": self.tone.value,
            "goal": self.goal,
            "suggested_reply_outline": self.suggested_reply_outline,
        }


@dataclass
class StabilityMetadata:
    """稳定性元数据"""
    state_ok: bool = True
    degraded: bool = False
    degradation_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "state_ok": self.state_ok,
            "degraded": self.degraded,
        }
        if self.degradation_reason:
            result["degradation_reason"] = self.degradation_reason
        return result


@dataclass
class OpenEmotionResultV1:
    """
    OpenEmotion 结果契约 v1
    
    符合 oe.result.v1 规范的完整结果结构。
    """
    # 必填字段
    schema_version: str = "1.0.0"
    result_id: str = ""
    event_id_ref: str = ""
    timestamp: str = ""
    
    # 核心输出
    identity_state_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Optional[MemoryUpdate] = None
    relationship_update: Dict[str, Any] = field(default_factory=dict)
    appraisal_state_delta: Optional[AppraisalStateDelta] = None
    
    # 高级输出
    reflection_note: Optional[Dict[str, Any]] = None
    policy_hint: Optional[Dict[str, Any]] = None
    response_tendency: Optional[ResponseTendency] = None
    
    # 元数据
    confidence: float = 0.0
    stability_metadata: Optional[StabilityMetadata] = None
    
    # 原始响应（用于调试）
    raw_response: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event_id_ref": self.event_id_ref,
            "timestamp": self.timestamp,
            "identity_state_delta": self.identity_state_delta,
            "self_model_delta": self.self_model_delta,
        }
        
        if self.memory_update:
            result["memory_update"] = self.memory_update.to_dict()
        if self.relationship_update:
            result["relationship_update"] = self.relationship_update
        if self.appraisal_state_delta:
            result["appraisal_state_delta"] = self.appraisal_state_delta.to_dict()
        if self.reflection_note:
            result["reflection_note"] = self.reflection_note
        if self.policy_hint:
            result["policy_hint"] = self.policy_hint
        if self.response_tendency:
            result["response_tendency"] = self.response_tendency.to_dict()
        
        result["confidence"] = self.confidence
        
        if self.stability_metadata:
            result["stability_metadata"] = self.stability_metadata.to_dict()
        
        return result
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_emotiond_response(
        cls,
        event_id: str,
        response: Dict[str, Any],
    ) -> "OpenEmotionResultV1":
        """从 emotiond 响应创建结果对象"""
        from datetime import datetime, timezone
        
        # 提取关键字段
        appraisal = response.get("appraisal", {})
        self_report = response.get("self_report", {})
        emotional_reasoning = self_report.get("emotional_reasoning", {})
        
        # 构建 appraisal_state_delta
        appraisal_delta = AppraisalStateDelta(
            trust=appraisal.get("trust", 0.0),
            caution=emotional_reasoning.get("predicted_risk", 0.0),
            frustration=0.0,
            joy=appraisal.get("joy", 0.0),
            sadness=appraisal.get("sadness", 0.0),
            anger=appraisal.get("anger", 0.0),
        )
        
        # 构建 memory_update
        narrative_memory = self_report.get("narrative_memory", {})
        memory_update = None
        if narrative_memory:
            memory_update = MemoryUpdate(
                write_narrative=[narrative_memory] if narrative_memory.get("state") else [],
            )
        
        # 构建 reflection_note
        reflection_note = None
        if self_report.get("audit"):
            reflection_note = {
                "hash": self_report.get("audit", {}).get("self_hash"),
                "emotion_label": appraisal.get("emotion_label"),
                "action_tendency": emotional_reasoning.get("action_tendency"),
            }
        
        # 构建 policy_hint
        policy_hint = None
        if emotional_reasoning.get("action_tendency"):
            policy_hint = {
                "action_tendency": emotional_reasoning.get("action_tendency"),
                "predicted_risk": emotional_reasoning.get("predicted_risk"),
                "primary_emotion": emotional_reasoning.get("primary_emotion"),
            }
        
        # 构建 response_tendency
        response_tendency = ResponseTendency(
            mode=ResponseMode.REPLY,
            tone=ResponseTone.CALM,
            goal="answer_and_continue",
            suggested_reply_outline=[
                "acknowledge_context",
                "answer_question",
                "offer_next_step",
            ],
        )
        
        return cls(
            result_id=f"result_{event_id}",
            event_id_ref=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            appraisal_state_delta=appraisal_delta,
            memory_update=memory_update,
            reflection_note=reflection_note,
            policy_hint=policy_hint,
            response_tendency=response_tendency,
            confidence=emotional_reasoning.get("confidence", 0.0),
            stability_metadata=StabilityMetadata(
                state_ok=response.get("status") == "processed",
                degraded=False,
            ),
            raw_response=response,
        )
