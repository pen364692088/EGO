"""
Event Mirror v2 - 完整契约 + Trace Writer

镜像 Telegram 事件到 OpenEmotion，并生成完整 artifacts。
"""

import logging
import time
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.integrations.openemotion.client import (
    OpenEmotionClient,
    get_openemotion_client,
)

from egocore.contracts.openemotion_event_v1 import (
    OpenEmotionEventV1,
    Actor,
    ActorType,
    EventType,
    UserIntent,
    IntentType,
    SafetyContext,
    ConversationContext,
    RiskLevel,
)
from egocore.contracts.openemotion_result_v1 import (
    OpenEmotionResultV1,
)
from egocore.artifacts.openemotion_trace_writer import (
    TraceWriter,
    TraceContext,
    get_trace_writer,
)


logger = logging.getLogger(__name__)


@dataclass
class MirrorResultV2:
    """结果对象 v2"""
    success: bool
    trace_id: str
    event_id: str
    latency_ms: float
    result: Optional[OpenEmotionResultV1] = None
    error: Optional[str] = None
    artifact_dir: Optional[str] = None


class EventMirrorV2:
    """
    事件镜像 v2 - 完整契约 + Artifacts
    
    功能：
    1. 生成完整 oe.event.v1 契约
    2. 发送到 OpenEmotion
    3. 解析 oe.result.v1 响应
    4. 写入完整 artifacts
    """
    
    def __init__(
        self,
        client: Optional[OpenEmotionClient] = None,
        trace_writer: Optional[TraceWriter] = None,
        enabled: bool = True,
        artifact_root: Optional[Path] = None,
    ):
        self.client = client or get_openemotion_client()
        self.trace_writer = trace_writer or get_trace_writer(artifact_root)
        self.enabled = enabled
        self._stats = {
            "total_mirrored": 0,
            "successful": 0,
            "failed": 0,
        }
    
    def mirror_user_message(
        self,
        user_id: str,
        message_text: str,
        chat_id: Optional[str] = None,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        intent_type: IntentType = IntentType.CHAT,
    ) -> MirrorResultV2:
        """
        镜像用户消息到 OpenEmotion
        
        生成完整 artifacts:
        - raw_ingress_event.json
        - normalized_event.json
        - openemotion_request.json
        - openemotion_response.json
        - trace_index.json
        """
        if not self.enabled:
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=0,
                error="Event mirror disabled"
            )
        
        start_time = time.time()
        
        try:
            # Step 1: 创建 raw ingress event
            raw_event = {
                "source": "telegram",
                "user_id": user_id,
                "message_text": message_text,
                "chat_id": chat_id,
                "username": username,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Step 2: 创建 trace context
            ctx = self.trace_writer.create_trace_context(
                source="telegram",
                actor_id=user_id,
                raw_event=raw_event,
            )
            
            # Step 3: 创建 normalized event (oe.event.v1)
            event = OpenEmotionEventV1.create_user_message(
                event_id=ctx.event_id,
                user_id=user_id,
                message_text=message_text,
                source="egocore_telegram",
                intent_type=intent_type,
                session_id=session_id,
                conversation_id=conversation_id or chat_id,
            )
            
            # 添加额外元数据
            event.metadata.update({
                "chat_id": chat_id,
                "username": username,
            })
            
            # Step 4: 写入 normalized event
            self.trace_writer.write_normalized_event(ctx, event.to_dict())
            
            # Step 5: 写入 OpenEmotion request
            self.trace_writer.write_openemotion_request(ctx, event.to_dict())
            
            # Step 6: 发送到 OpenEmotion
            success, fallback = self.client.send_event(event.to_dict())
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Step 7: 处理响应
            result = None
            if success:
                # 尝试从 fallback 或构建 result
                result = OpenEmotionResultV1.from_emotiond_response(
                    event_id=ctx.event_id,
                    response={"status": "processed", "latency_ms": latency_ms},
                )
                self.trace_writer.write_openemotion_response(ctx, result.to_dict())
            
            # Step 8: 写入 runtime decision
            decision = {
                "event_id": ctx.event_id,
                "action": "mirror_to_openemotion",
                "success": success,
                "latency_ms": latency_ms,
            }
            self.trace_writer.write_runtime_decision(ctx, decision)
            
            # Step 9: 完成 trace
            index = self.trace_writer.finalize_trace(
                ctx,
                status="completed" if success else "failed",
                metadata={"latency_ms": latency_ms},
            )
            
            # 更新统计
            self._stats["total_mirrored"] += 1
            if success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
            
            logger.info(
                f"Event mirrored: trace={ctx.trace_id}, event={ctx.event_id}, "
                f"user={user_id}, latency={latency_ms:.1f}ms, success={success}"
            )
            
            return MirrorResultV2(
                success=success,
                trace_id=ctx.trace_id,
                event_id=ctx.event_id,
                latency_ms=latency_ms,
                result=result,
                error=fallback.message if fallback else None,
                artifact_dir=str(ctx.artifact_dir),
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["total_mirrored"] += 1
            self._stats["failed"] += 1
            
            logger.error(f"Event mirror failed: {e}")
            
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def mirror_assistant_reply(
        self,
        reply_text: str,
        user_id: str,
        intent: str = "inform",
        trace_id: Optional[str] = None,
    ) -> MirrorResultV2:
        """
        镜像助手回复到 OpenEmotion
        """
        if not self.enabled:
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=0,
                error="Event mirror disabled"
            )
        
        start_time = time.time()
        
        try:
            # 创建 raw event
            raw_event = {
                "type": "assistant_reply",
                "user_id": user_id,
                "reply_text": reply_text,
                "intent": intent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # 创建 trace context
            ctx = self.trace_writer.create_trace_context(
                source="egocore",
                actor_id="assistant",
                raw_event=raw_event,
            )
            
            # 创建 event
            event = OpenEmotionEventV1.create_assistant_reply(
                event_id=ctx.event_id,
                user_id=user_id,
                reply_text=reply_text,
                intent=intent,
            )
            
            # 写入 artifacts
            self.trace_writer.write_normalized_event(ctx, event.to_dict())
            self.trace_writer.write_openemotion_request(ctx, event.to_dict())
            
            # 发送
            success, fallback = self.client.send_event(event.to_dict())
            
            latency_ms = (time.time() - start_time) * 1000
            
            # 完成trace
            self.trace_writer.finalize_trace(
                ctx,
                status="completed" if success else "failed",
            )
            
            self._stats["total_mirrored"] += 1
            if success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
            
            return MirrorResultV2(
                success=success,
                trace_id=ctx.trace_id,
                event_id=ctx.event_id,
                latency_ms=latency_ms,
                error=fallback.message if fallback else None,
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["total_mirrored"] += 1
            self._stats["failed"] += 1
            
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def mirror_external_result(
        self,
        task_id: str,
        action: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> MirrorResultV2:
        """
        镜像外部执行结果到 OpenEmotion
        """
        if not self.enabled:
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=0,
                error="Event mirror disabled"
            )
        
        start_time = time.time()
        
        try:
            # 创建 raw event
            raw_event = {
                "type": "external_result",
                "task_id": task_id,
                "action": action,
                "status": status,
                "output": output,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # 创建 trace context
            ctx = self.trace_writer.create_trace_context(
                source="egocore_task",
                actor_id="egocore_runtime",
                raw_event=raw_event,
            )
            
            # 创建 event
            event = OpenEmotionEventV1.create_external_result(
                event_id=ctx.event_id,
                task_id=task_id,
                action=action,
                status=status,
                output=output,
                error=error,
            )
            
            # 写入 artifacts
            self.trace_writer.write_normalized_event(ctx, event.to_dict())
            self.trace_writer.write_openemotion_request(ctx, event.to_dict())
            self.trace_writer.write_external_result(ctx, raw_event)
            
            # 发送
            success, fallback = self.client.send_event(event.to_dict())
            
            latency_ms = (time.time() - start_time) * 1000
            
            # 完成 trace
            self.trace_writer.finalize_trace(
                ctx,
                status="completed" if success else "failed",
            )
            
            self._stats["total_mirrored"] += 1
            if success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
            
            return MirrorResultV2(
                success=success,
                trace_id=ctx.trace_id,
                event_id=ctx.event_id,
                latency_ms=latency_ms,
                error=fallback.message if fallback else None,
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["total_mirrored"] += 1
            self._stats["failed"] += 1
            
            return MirrorResultV2(
                success=False,
                trace_id="",
                event_id="",
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()


# Singleton instance
_mirror_v2: Optional[EventMirrorV2] = None


def get_event_mirror_v2(artifact_root: Optional[Path] = None) -> EventMirrorV2:
    """Get the singleton EventMirrorV2 instance"""
    global _mirror_v2
    if _mirror_v2 is None:
        if artifact_root is None:
            artifact_root = Path("artifacts/traces")
        _mirror_v2 = EventMirrorV2(artifact_root=artifact_root)
    return _mirror_v2
