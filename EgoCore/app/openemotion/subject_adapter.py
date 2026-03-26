"""
Subject Adapter - EgoCore

调用 OpenEmotion 端点，获取主体解释。

归属：EgoCore
作用：调用 OpenEmotion，处理超时/bridge down/schema mismatch。

重要说明：
- cycle() 是正式主体链 (Cycle Core v1)，优先使用
- interpret() 是 fallback / legacy，仅在 /cycle 不可用时触发
"""

import logging
import time
import httpx
from typing import Optional, Dict, Any

from egocore.contracts.interaction_event_envelope_v1 import InteractionEventEnvelope

logger = logging.getLogger(__name__)


class SubjectAdapter:
    """
    主体解释适配器
    
    负责调用 OpenEmotion /interpret 端点并处理错误。
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:18080",
        timeout_ms: int = 3000,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self._client: Optional[httpx.Client] = None
        
        # 统计
        self._stats = {
            "total_calls": 0,
            "successful": 0,
            "fallback": 0,
            "timeout": 0,
            "error": 0,
        }
    
    @property
    def client(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_ms / 1000.0)
        return self._client
    
    def interpret(
        self,
        envelope: InteractionEventEnvelope,
    ) -> Dict[str, Any]:
        """
        [LEGACY / FALLBACK ONLY]
        调用 OpenEmotion /interpret 获取主体解释
        
        注意：此方法已废弃，仅在 /cycle 不可用时作为 fallback。
        正式入口应使用 cycle() 方法。
        
        Args:
            envelope: InteractionEventEnvelope
        
        Returns:
            SubjectInterpretationResult dict（可能为降级结果）
        """
        self._stats["total_calls"] += 1
        start_time = time.time()
        
        try:
            envelope_dict = envelope.to_dict()
            
            response = self.client.post(
                f"{self.base_url}/interpret",
                json=envelope_dict,
                headers={"Content-Type": "application/json"},
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                
                # 验证 schema
                if self._validate_result(result):
                    self._stats["successful"] += 1
                    logger.info(
                        f"Interpretation success: envelope={envelope.envelope_id}, "
                        f"latency={latency_ms:.1f}ms"
                    )
                    return result
                else:
                    logger.warning(f"Invalid result schema, using fallback")
                    self._stats["fallback"] += 1
                    return self._create_fallback_result(envelope.envelope_id, "invalid_schema")
            
            else:
                logger.warning(f"Interpretation failed: status={response.status_code}")
                self._stats["error"] += 1
                return self._create_fallback_result(envelope.envelope_id, f"http_{response.status_code}")
        
        except httpx.TimeoutException:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Interpretation timeout: latency={latency_ms:.1f}ms")
            self._stats["timeout"] += 1
            return self._create_fallback_result(envelope.envelope_id, "timeout")
        
        except httpx.ConnectError:
            logger.warning(f"OpenEmotion connection refused")
            self._stats["error"] += 1
            return self._create_fallback_result(envelope.envelope_id, "connection_refused")
        
        except Exception as e:
            logger.error(f"Interpretation error: {e}")
            self._stats["error"] += 1
            return self._create_fallback_result(envelope.envelope_id, str(e))
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """验证结果格式"""
        required_fields = ["result_id", "schema_version", "interaction_interpretation"]
        for field in required_fields:
            if field not in result:
                return False
        
        # 验证不包含禁止字段
        forbidden = ["should_reply", "should_start_task", "should_call_tool", "runtime_route", "safety_decision"]
        for field in forbidden:
            if field in result:
                logger.warning(f"Result contains forbidden field: {field}")
                return False
        
        return True
    
    def _create_fallback_result(
        self,
        envelope_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        创建降级结果
        
        关键原则：
        - 不伪造 appraisal / relationship / reflection
        - 标记 degraded = True
        - 使用保守的默认值
        """
        import uuid
        
        return {
            "result_id": f"res_fallback_{uuid.uuid4().hex[:8]}",
            "schema_version": "1.0.0",
            "envelope_id": envelope_id,
            "interaction_interpretation": {
                "primary_mode": "unknown",
                "secondary_modes": [],
                "user_goal_rewrite": None,
                "ambiguity_level": 0.5,
                "confidence": 0.3,
            },
            "social_signals": [],
            "relationship_implication": {
                "interaction_effect": "neutral",
                "trust_delta": 0.0,
                "tension_delta": 0.0,
                "repair_needed": False,
                "notes": None,
            },
            "appraisal_state_delta": {},
            "response_tendency": {
                "preferred_action": "acknowledge",
                "should_acknowledge_context": False,
                "should_acknowledge_affect": False,
                "should_invite_next_step": False,
                "should_explain_self": False,
                "should_shift_to_task_mode": False,
            },
            "expressive_intent_candidate": {
                "speaker_stance": "neutral",
                "warmth_preference": 0.5,
                "directness_preference": 0.5,
                "preferred_opening": None,
                "must_include_candidates": [],
                "must_avoid_candidates": [],
            },
            "reply_urge": {
                "value": 0.5,
                "reason": "fallback",
            },
            "reflection_note": f"OpenEmotion 暂时不可用 ({reason})，使用降级模式",
            "policy_hint": None,
            "stability": {
                "model_confidence": 0.3,
                "ood_flag": True,
                "degraded": True,
            },
            "processing_time_ms": 0.0,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()
    
    def cycle(
        self,
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        [正式主体链 - PRIMARY]
        调用 OpenEmotion /cycle 端点执行循环核心 v1
        
        这是正式主体接口，用于：
        - event -> state update -> memory gate -> readout
        - 跨轮状态连续性
        - 显式偏好/目标/约束类事件写入
        
        Args:
            event: OpenEmotionEventV1 dict (符合 schemas/openemotion_event_v1.schema.json)
        
        Returns:
            dict:
                status: "ok" | "error"
                result: OpenEmotionResultV1 dict
                trace_id: 追踪 ID
        """
        self._stats["total_calls"] += 1
        start_time = time.time()
        
        try:
            response = self.client.post(
                f"{self.base_url}/cycle",
                json=event,
                headers={"Content-Type": "application/json"},
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                self._stats["successful"] += 1
                logger.info(
                    f"Cycle success: event={event.get('event_id')}, "
                    f"trace={result.get('trace_id')}, "
                    f"latency={latency_ms:.1f}ms"
                )
                return result
            else:
                logger.warning(f"Cycle failed: status={response.status_code}")
                self._stats["error"] += 1
                return {
                    "status": "error",
                    "error": f"http_{response.status_code}",
                    "event_id": event.get("event_id"),
                }
        
        except httpx.TimeoutException:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Cycle timeout: latency={latency_ms:.1f}ms")
            self._stats["timeout"] += 1
            return {
                "status": "error",
                "error": "timeout",
                "event_id": event.get("event_id"),
            }
        
        except httpx.ConnectError:
            logger.warning(f"OpenEmotion connection refused")
            self._stats["error"] += 1
            return {
                "status": "error",
                "error": "connection_refused",
                "event_id": event.get("event_id"),
            }
        
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            self._stats["error"] += 1
            return {
                "status": "error",
                "error": str(e),
                "event_id": event.get("event_id"),
            }
    
    def close(self):
        """关闭客户端"""
        if self._client:
            self._client.close()
            self._client = None


# 全局实例
_adapter: Optional[SubjectAdapter] = None


def get_subject_adapter() -> SubjectAdapter:
    """获取全局主体适配器"""
    global _adapter
    if _adapter is None:
        _adapter = SubjectAdapter()
    return _adapter


def interpret(envelope: InteractionEventEnvelope) -> Dict[str, Any]:
    """
    便捷函数：获取主体解释
    
    Args:
        envelope: InteractionEventEnvelope
    
    Returns:
        SubjectInterpretationResult dict
    """
    return get_subject_adapter().interpret(envelope)
