"""
OpenEmotion Adapter v2

EgoCore 与 OpenEmotion 之间的唯一正式接线入口。
负责事件输入转换、OpenEmotion 调用、输出解析和错误处理。

v2 新增:
- REAL_HTTP 模式：通过 HTTP 调用 OpenEmotion 服务
- 支持 health check
- 支持 timeout 和 retry
- 传输层 artifact 落盘

原则:
- adapter 只负责转换、传递、隔离、降级
- 不负责定义主体本体
- 所有逻辑必须可测试
"""

import json
import uuid
import time
import asyncio
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable


class AdapterMode(Enum):
    """适配器运行模式"""
    MOCK = "mock"  # 模拟模式，用于测试
    REAL_HTTP = "real_http"  # 真实 HTTP 模式


class AdapterError(Exception):
    """适配器错误基类"""
    pass


class ValidationError(AdapterError):
    """验证错误"""
    pass


class ConnectionError(AdapterError):
    """连接错误"""
    pass


class TimeoutError(AdapterError):
    """超时错误"""
    pass


@dataclass
class EventInput:
    """事件输入结构"""
    event_id: str
    timestamp: str
    actor: Dict[str, Any]
    source: Dict[str, Any]
    event_type: str
    user_intent: Dict[str, Any]
    safety_context: Dict[str, Any]
    task_context: Optional[Dict[str, Any]] = None
    conversation_context: Optional[Dict[str, Any]] = None
    runtime_summary: Optional[Dict[str, Any]] = None
    external_result: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    # v2 新增：trace 相关字段
    trace_id: Optional[str] = None
    case_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventInput":
        """从字典创建"""
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            actor=data["actor"],
            source=data["source"],
            event_type=data["event_type"],
            user_intent=data["user_intent"],
            safety_context=data["safety_context"],
            task_context=data.get("task_context"),
            conversation_context=data.get("conversation_context"),
            runtime_summary=data.get("runtime_summary"),
            external_result=data.get("external_result"),
            metadata=data.get("metadata"),
            trace_id=data.get("trace_id"),
            case_id=data.get("case_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "source": self.source,
            "event_type": self.event_type,
            "user_intent": self.user_intent,
            "safety_context": self.safety_context,
        }
        if self.task_context:
            result["task_context"] = self.task_context
        if self.conversation_context:
            result["conversation_context"] = self.conversation_context
        if self.runtime_summary:
            result["runtime_summary"] = self.runtime_summary
        if self.external_result:
            result["external_result"] = self.external_result
        if self.metadata:
            result["metadata"] = self.metadata
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.case_id:
            result["case_id"] = self.case_id
        return result
    
    def to_openemotion_event(self) -> Dict[str, Any]:
        """
        转换为 OpenEmotion Event 格式
        
        OpenEmotion Event 结构:
        {
            "type": "user_message" | "assistant_reply" | "world_event",
            "actor": str,
            "target": str,
            "text": str (optional),
            "meta": dict (optional)
        }
        """
        return {
            "type": self.event_type,
            "actor": self.actor.get("actor_id", "unknown"),
            "target": "assistant",
            "text": self.metadata.get("user_message", "") if self.metadata else "",
            "meta": {
                "event_id": self.event_id,
                "trace_id": self.trace_id,
                "case_id": self.case_id,
                "source": self.source.get("channel", "unknown"),
                "timestamp": self.timestamp,
            }
        }


@dataclass
class OpenEmotionOutput:
    """OpenEmotion 输出结构"""
    output_id: str
    timestamp: str
    event_id_ref: str
    confidence_metadata: Dict[str, Any]
    valence: float = 0.0
    arousal: float = 0.3
    identity_state_delta: Optional[Dict[str, Any]] = None
    self_model_delta: Optional[Dict[str, Any]] = None
    memory_update: Optional[Dict[str, Any]] = None
    relationship_update: Optional[Dict[str, Any]] = None
    appraisal_state_delta: Optional[Dict[str, Any]] = None
    reflection_note: Optional[Dict[str, Any]] = None
    policy_hint: Optional[Dict[str, Any]] = None
    response_tendency: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    # v2 新增：传输层信息
    transport_metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenEmotionOutput":
        """从字典创建"""
        return cls(
            output_id=data.get("output_id", f"out_{uuid.uuid4().hex[:8]}"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            event_id_ref=data.get("event_id_ref", data.get("event_id", "unknown")),
            confidence_metadata=data.get("confidence_metadata", {"overall_confidence": 0.9}),
            valence=data.get("valence", 0.0),
            arousal=data.get("arousal", 0.3),
            identity_state_delta=data.get("identity_state_delta"),
            self_model_delta=data.get("self_model_delta"),
            memory_update=data.get("memory_update"),
            relationship_update=data.get("relationship_update"),
            appraisal_state_delta=data.get("appraisal_state_delta"),
            reflection_note=data.get("reflection_note"),
            policy_hint=data.get("policy_hint"),
            response_tendency=data.get("response_tendency"),
            metadata=data.get("metadata"),
            transport_metadata=data.get("transport_metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "output_id": self.output_id,
            "timestamp": self.timestamp,
            "event_id_ref": self.event_id_ref,
            "confidence_metadata": self.confidence_metadata,
            "valence": self.valence,
            "arousal": self.arousal,
        }
        if self.identity_state_delta:
            result["identity_state_delta"] = self.identity_state_delta
        if self.self_model_delta:
            result["self_model_delta"] = self.self_model_delta
        if self.memory_update:
            result["memory_update"] = self.memory_update
        if self.relationship_update:
            result["relationship_update"] = self.relationship_update
        if self.appraisal_state_delta:
            result["appraisal_state_delta"] = self.appraisal_state_delta
        if self.reflection_note:
            result["reflection_note"] = self.reflection_note
        if self.policy_hint:
            result["policy_hint"] = self.policy_hint
        if self.response_tendency:
            result["response_tendency"] = self.response_tendency
        if self.metadata:
            result["metadata"] = self.metadata
        if self.transport_metadata:
            result["transport_metadata"] = self.transport_metadata
        return result
    
    @classmethod
    def from_openemotion_response(cls, response_data: Dict[str, Any], event_id: str, transport_metadata: Optional[Dict] = None) -> "OpenEmotionOutput":
        """
        从 OpenEmotion /event 响应创建输出
        
        OpenEmotion 返回格式:
        {
            "status": "processed",
            "valence": float,
            "arousal": float,
            "prediction_error": float,
            "memory_strength": float,
            ...
        }
        """
        return cls(
            output_id=f"out_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id_ref=event_id,
            confidence_metadata={
                "overall_confidence": 0.9,
                "status": response_data.get("status", "unknown"),
                "prediction_error": response_data.get("prediction_error", 0.0),
            },
            valence=response_data.get("valence", 0.0),
            arousal=response_data.get("arousal", 0.3),
            appraisal_state_delta={
                "emotion_label": response_data.get("appraisal", {}).get("emotion_label"),
                "intensity": response_data.get("appraisal", {}).get("intensity"),
            },
            policy_hint={
                "preferred_action_type": "respond",
                "risk_tolerance": "moderate",
            },
            response_tendency={
                "tone": "neutral",
                "verbosity": "moderate",
            },
            metadata={
                "openemotion_response": response_data,
            },
            transport_metadata=transport_metadata,
        )


class OpenEmotionBackend(ABC):
    """OpenEmotion 后端抽象"""

    @abstractmethod
    def process(self, event: EventInput) -> OpenEmotionOutput:
        """处理事件并返回输出"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查服务健康状态"""
        pass


class MockBackend(OpenEmotionBackend):
    """模拟后端，用于测试"""

    def __init__(self, response_generator: Optional[Callable] = None):
        """
        初始化模拟后端

        Args:
            response_generator: 可选的自定义响应生成器
        """
        self.response_generator = response_generator or self._default_response
        self.call_history: List[Dict[str, Any]] = []

    def _default_response(self, event: EventInput) -> OpenEmotionOutput:
        """默认响应生成器"""
        # 基于事件类型生成简单响应
        valence = 0.0
        if event.event_type == "user_message":
            valence = 0.2
        elif event.event_type == "task_completed":
            valence = 0.5
        elif event.event_type == "task_failed":
            valence = -0.3

        return OpenEmotionOutput(
            output_id=f"out_mock_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id_ref=event.event_id,
            confidence_metadata={
                "overall_confidence": 0.9,
                "identity_confidence": 1.0,
                "memory_confidence": 0.8,
            },
            valence=valence,
            arousal=0.3,
            appraisal_state_delta={
                "valence": valence,
                "arousal": 0.3,
                "dominance": 0.5,
            },
            policy_hint={
                "preferred_action_type": "respond",
                "risk_tolerance": "moderate",
            },
            response_tendency={
                "tone": "neutral",
                "verbosity": "moderate",
                "proactivity": 0.5,
            },
        )

    def process(self, event: EventInput) -> OpenEmotionOutput:
        """处理事件"""
        self.call_history.append({
            "event_id": event.event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return self.response_generator(event)
    
    async def health_check(self) -> bool:
        """模拟后端总是健康"""
        return True


class RealHTTPBackend(OpenEmotionBackend):
    """
    真实 HTTP 后端，通过 HTTP 调用 OpenEmotion 服务
    
    v3 实现：真实传输层调用
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_sec: float = 30.0,
        retry_count: int = 3,
        artifact_dir: Optional[Path] = None,
    ):
        """
        初始化真实 HTTP 后端

        Args:
            base_url: OpenEmotion 服务基础 URL
            timeout_sec: 超时时间（秒）
            retry_count: 重试次数
            artifact_dir: artifact 存储目录
        """
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.retry_count = retry_count
        self.artifact_dir = artifact_dir
        
        # HTTP 客户端
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_sec),
        )
        
        # 调用统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "timeouts": 0,
        }
        
        # 请求历史
        self.request_history: List[Dict[str, Any]] = []

    async def health_check(self) -> bool:
        """检查 OpenEmotion 服务健康状态"""
        try:
            response = await self.client.get("/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("ok", False) and data.get("emotiond", {}).get("status") == "running"
            return False
        except Exception:
            return False

    def process(self, event: EventInput) -> OpenEmotionOutput:
        """同步处理事件（包装异步方法）"""
        return asyncio.run(self._process_async(event))
    
    async def process_async(self, event: EventInput) -> OpenEmotionOutput:
        """异步处理事件"""
        return await self._process_async(event)

    async def _process_async(self, event: EventInput) -> OpenEmotionOutput:
        """异步处理事件核心逻辑"""
        self.stats["total_calls"] += 1
        
        # 构造 OpenEmotion Event
        oe_event = event.to_openemotion_event()
        
        # 记录请求
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        request_timestamp = datetime.now(timezone.utc).isoformat()
        
        request_record = {
            "request_id": request_id,
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "case_id": event.case_id,
            "timestamp": request_timestamp,
            "endpoint": "/event",
            "payload": oe_event,
        }
        self.request_history.append(request_record)
        
        # 保存请求 artifact
        if self.artifact_dir:
            self._save_artifact(
                self.artifact_dir / "transport_requests" / f"{event.event_id}.json",
                request_record
            )
        
        # 带重试的 HTTP 调用
        last_error = None
        for attempt in range(self.retry_count):
            try:
                start_time = time.time()
                
                response = await self.client.post(
                    "/event",
                    json=oe_event,
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-Id": event.trace_id or "",
                        "X-Case-Id": event.case_id or "",
                    }
                )
                
                duration_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # 记录响应
                    response_record = {
                        "request_id": request_id,
                        "event_id": event.event_id,
                        "trace_id": event.trace_id,
                        "case_id": event.case_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "response": response_data,
                    }
                    
                    # 保存响应 artifact
                    if self.artifact_dir:
                        self._save_artifact(
                            self.artifact_dir / "transport_responses" / f"{event.event_id}.json",
                            response_record
                        )
                    
                    self.stats["successful_calls"] += 1
                    
                    # 构造输出
                    transport_metadata = {
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "attempt": attempt + 1,
                        "base_url": self.base_url,
                    }
                    
                    return OpenEmotionOutput.from_openemotion_response(
                        response_data,
                        event.event_id,
                        transport_metadata
                    )
                
                elif response.status_code in (429, 502, 503, 504):
                    # 可重试的错误
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    self.stats["retries"] += 1
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                    continue
                
                else:
                    # 不可重试的错误
                    self.stats["failed_calls"] += 1
                    return self._create_error_output(
                        event.event_id,
                        f"HTTP {response.status_code}: {response.text}",
                        transport_metadata={"request_id": request_id}
                    )
                    
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                self.stats["timeouts"] += 1
                self.stats["retries"] += 1
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
                
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                self.stats["retries"] += 1
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
                
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                self.stats["failed_calls"] += 1
                return self._create_error_output(
                    event.event_id,
                    str(e),
                    transport_metadata={"request_id": request_id}
                )
        
        # 所有重试失败
        self.stats["failed_calls"] += 1
        return self._create_error_output(
            event.event_id,
            f"All retries failed: {last_error}",
            transport_metadata={"request_id": request_id, "attempts": self.retry_count}
        )
    
    def _save_artifact(self, path: Path, data: Dict[str, Any]) -> None:
        """保存 artifact"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
    
    def _create_error_output(
        self,
        event_id: str,
        error_message: str,
        transport_metadata: Optional[Dict] = None,
    ) -> OpenEmotionOutput:
        """创建错误输出"""
        return OpenEmotionOutput(
            output_id=f"out_error_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id_ref=event_id,
            confidence_metadata={
                "overall_confidence": 0.0,
                "uncertainty_reasons": [error_message],
            },
            valence=0.0,
            arousal=0.3,
            metadata={
                "error": True,
                "error_message": error_message,
            },
            transport_metadata=transport_metadata,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """重置统计"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "timeouts": 0,
        }
    
    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self.client.aclose()


class OpenEmotionAdapter:
    """
    OpenEmotion 适配器

    作为 EgoCore 与 OpenEmotion 之间的唯一正式接线入口。
    
    v2 支持:
    - MOCK 模式：模拟后端
    - REAL_HTTP 模式：真实 HTTP 调用
    """

    def __init__(
        self,
        mode: AdapterMode = AdapterMode.MOCK,
        backend: Optional[OpenEmotionBackend] = None,
        schema_dir: Optional[Path] = None,
        artifact_dir: Optional[Path] = None,
        base_url: str = "http://localhost:8000",
    ):
        """
        初始化适配器

        Args:
            mode: 运行模式
            backend: 后端实例（如果为 None，根据模式自动创建）
            schema_dir: schema 目录路径
            artifact_dir: artifact 存储目录
            base_url: OpenEmotion 服务 URL（REAL_HTTP 模式）
        """
        self.mode = mode
        self.schema_dir = schema_dir
        self.artifact_dir = artifact_dir
        self.base_url = base_url

        if backend:
            self.backend = backend
        elif mode == AdapterMode.MOCK:
            self.backend = MockBackend()
        elif mode == AdapterMode.REAL_HTTP:
            self.backend = RealHTTPBackend(
                base_url=base_url,
                artifact_dir=artifact_dir,
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # 调用统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "mode": mode.value,
        }

    async def health_check(self) -> bool:
        """检查 OpenEmotion 服务健康状态"""
        return await self.backend.health_check()

    def process_event(
        self,
        event_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        处理事件

        Args:
            event_input: 事件输入字典

        Returns:
            OpenEmotion 输出字典
        """
        self.stats["total_calls"] += 1

        try:
            # 1. 解析并验证输入
            event = self._parse_and_validate_input(event_input)

            # 2. 调用后端
            if isinstance(self.backend, RealHTTPBackend):
                output = asyncio.run(self.backend.process_async(event))
            else:
                output = self.backend.process(event)

            # 3. 验证输出
            self._validate_output(output)

            self.stats["successful_calls"] += 1

            return output.to_dict()

        except ValidationError as e:
            self.stats["failed_calls"] += 1
            return self._create_error_output(
                event_input.get("event_id", "unknown"),
                f"Validation error: {e}",
            )

        except Exception as e:
            self.stats["failed_calls"] += 1
            return self._create_error_output(
                event_input.get("event_id", "unknown"),
                f"Processing error: {e}",
            )
    
    async def process_event_async(
        self,
        event_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """异步处理事件"""
        self.stats["total_calls"] += 1

        try:
            event = self._parse_and_validate_input(event_input)

            if isinstance(self.backend, RealHTTPBackend):
                output = await self.backend.process_async(event)
            else:
                output = self.backend.process(event)

            self._validate_output(output)

            self.stats["successful_calls"] += 1

            return output.to_dict()

        except Exception as e:
            self.stats["failed_calls"] += 1
            return self._create_error_output(
                event_input.get("event_id", "unknown"),
                str(e),
            )

    def _parse_and_validate_input(
        self,
        data: Dict[str, Any],
    ) -> EventInput:
        """解析并验证输入"""
        required_fields = [
            "event_id", "timestamp", "actor", "source",
            "event_type", "user_intent", "safety_context"
        ]

        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")

        return EventInput.from_dict(data)

    def _validate_output(self, output: OpenEmotionOutput) -> None:
        """验证输出"""
        if not output.output_id:
            raise ValidationError("output_id is required")
        if not output.event_id_ref:
            raise ValidationError("event_id_ref is required")

    def _create_error_output(
        self,
        event_id: str,
        error_message: str,
    ) -> Dict[str, Any]:
        """创建错误输出"""
        return {
            "output_id": f"out_error_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id_ref": event_id,
            "confidence_metadata": {
                "overall_confidence": 0.0,
                "uncertainty_reasons": [error_message],
            },
            "valence": 0.0,
            "arousal": 0.3,
            "metadata": {
                "error": True,
                "error_message": error_message,
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if isinstance(self.backend, RealHTTPBackend):
            stats["backend_stats"] = self.backend.get_stats()
        return stats

    def reset_stats(self) -> None:
        """重置统计"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "mode": self.mode.value,
        }
        if isinstance(self.backend, RealHTTPBackend):
            self.backend.reset_stats()


# 便捷函数
def create_adapter(
    mode: str = "mock",
    base_url: str = "http://localhost:8000",
    artifact_dir: Optional[Path] = None,
) -> OpenEmotionAdapter:
    """
    创建适配器实例

    Args:
        mode: 运行模式 ("mock" 或 "real_http")
        base_url: OpenEmotion 服务 URL（real_http 模式）
        artifact_dir: artifact 存储目录

    Returns:
        OpenEmotionAdapter 实例
    """
    adapter_mode = AdapterMode(mode)

    return OpenEmotionAdapter(
        mode=adapter_mode,
        base_url=base_url,
        artifact_dir=artifact_dir,
    )
