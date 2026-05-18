"""
OpenEmotion Trace Writer

每次真实请求写入完整 artifacts：
- raw_ingress_event.json
- normalized_event.json
- openemotion_request.json
- openemotion_response.json
- runtime_decision.json
- outbound_message.json
- external_result_event.json (可选)
- trace_index.json
"""

import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class TraceContext:
    """Trace context for a single request"""
    trace_id: str
    event_id: str
    timestamp: str
    source: str
    actor_id: str
    artifact_dir: Path


class TraceWriter:
    """
    Writes complete artifacts for each request.
    
    Artifacts per request:
    - raw_ingress_event.json    - 原始入口事件
    - normalized_event.json     - 标准化后的事件
    - openemotion_request.json  - 发送给 OpenEmotion 的请求
    - openemotion_response.json - OpenEmotion 返回的响应
    - runtime_decision.json     - 运行时决策记录
    - outbound_message.json     - 外发消息记录
    - external_result_event.json - 执行结果回流 (可选)
    - trace_index.json          - 索引文件
    """
    
    def __init__(self, artifact_root: Path):
        self.artifact_root = artifact_root
        self.artifact_root.mkdir(parents=True, exist_ok=True)
    
    def create_trace_context(
        self,
        source: str,
        actor_id: str,
        raw_event: Dict[str, Any],
    ) -> TraceContext:
        """Create a new trace context"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate trace_id from timestamp + source + actor
        trace_hash = hashlib.sha256(
            f"{timestamp}:{source}:{actor_id}".encode()
        ).hexdigest()[:16]
        trace_id = f"trace_{trace_hash}"
        
        # Generate event_id
        event_hash = hashlib.sha256(
            f"{timestamp}:{json.dumps(raw_event, sort_keys=True)}".encode()
        ).hexdigest()[:8]
        event_id = f"evt_{event_hash}"
        
        # Create artifact directory
        artifact_dir = self.artifact_root / trace_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        ctx = TraceContext(
            trace_id=trace_id,
            event_id=event_id,
            timestamp=timestamp,
            source=source,
            actor_id=actor_id,
            artifact_dir=artifact_dir,
        )
        
        # Write raw ingress event
        self._write_artifact(ctx, "raw_ingress_event", raw_event)
        
        return ctx
    
    def write_normalized_event(
        self,
        ctx: TraceContext,
        normalized: Dict[str, Any],
    ) -> None:
        """Write normalized event"""
        self._write_artifact(ctx, "normalized_event", normalized)
    
    def write_openemotion_request(
        self,
        ctx: TraceContext,
        request: Dict[str, Any],
    ) -> None:
        """Write OpenEmotion request"""
        self._write_artifact(ctx, "openemotion_request", request)
    
    def write_openemotion_response(
        self,
        ctx: TraceContext,
        response: Dict[str, Any],
    ) -> None:
        """Write OpenEmotion response"""
        self._write_artifact(ctx, "openemotion_response", response)
    
    def write_runtime_decision(
        self,
        ctx: TraceContext,
        decision: Dict[str, Any],
    ) -> None:
        """Write runtime decision"""
        self._write_artifact(ctx, "runtime_decision", decision)
    
    def write_outbound_message(
        self,
        ctx: TraceContext,
        message: Dict[str, Any],
    ) -> None:
        """Write outbound message"""
        self._write_artifact(ctx, "outbound_message", message)
    
    def write_external_result(
        self,
        ctx: TraceContext,
        result: Dict[str, Any],
    ) -> None:
        """Write external result (optional)"""
        self._write_artifact(ctx, "external_result_event", result)
    
    def finalize_trace(
        self,
        ctx: TraceContext,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Finalize trace and write index"""
        index = {
            "trace_id": ctx.trace_id,
            "event_id": ctx.event_id,
            "timestamp": ctx.timestamp,
            "source": ctx.source,
            "actor_id": ctx.actor_id,
            "status": status,
            "artifacts": self._list_artifacts(ctx),
            "metadata": metadata or {},
        }
        
        self._write_artifact(ctx, "trace_index", index)
        
        # Also append to master index
        self._append_to_master_index(index)
        
        return index
    
    def _write_artifact(
        self,
        ctx: TraceContext,
        name: str,
        data: Dict[str, Any],
    ) -> None:
        """Write an artifact file"""
        path = ctx.artifact_dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
    
    def _list_artifacts(self, ctx: TraceContext) -> list:
        """List all artifacts in trace directory"""
        artifacts = []
        for f in ctx.artifact_dir.glob("*.json"):
            artifacts.append(f.name)
        return sorted(artifacts)
    
    def _append_to_master_index(self, index: Dict[str, Any]) -> None:
        """Append to master trace index"""
        master_path = self.artifact_root / "trace_index.jsonl"
        with open(master_path, "a") as f:
            f.write(json.dumps(index, default=str) + "\n")


# Singleton instance
_trace_writer: Optional[TraceWriter] = None


def get_trace_writer(artifact_root: Optional[Path] = None) -> TraceWriter:
    """Get the singleton TraceWriter instance"""
    global _trace_writer
    if _trace_writer is None:
        if artifact_root is None:
            artifact_root = Path("artifacts/traces")
        _trace_writer = TraceWriter(artifact_root)
    return _trace_writer
