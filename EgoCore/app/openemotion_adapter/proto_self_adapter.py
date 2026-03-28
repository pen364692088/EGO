"""
Proto-Self Kernel Adapter for EgoCore

宿主侧最薄接线层：只做 normalize / load state / invoke kernel / save mirror / write trace。

设计约束：
- 只做事件标准化、状态加载、kernel 调用、状态镜像、trace 写入
- 不允许在 adapter 里发明主体语义
- 不允许在 EgoCore 里追加长期 self-model 更新逻辑
- 所有主体本体语义必须留在 OpenEmotion
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# OpenEmotion imports
from openemotion.proto_self import (
    KernelEvent,
    ProtoSelfState,
    SCHEMA_VERSION as V1_SCHEMA_VERSION,
    kernel_event_from_payload,
    serialize_kernel_output,
)
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.boundary import assert_no_direct_execution
from openemotion.proto_self_v2 import (
    SCHEMA_VERSION as V2_SCHEMA_VERSION,
    UpdatePacketV2,
    is_proto_self_v2_payload,
    process_update_packet,
    serialize_kernel_output_v2,
    update_packet_from_payload,
)
from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore


class ProtoSelfAdapter:
    """
    Proto-Self Kernel 适配器。

    职责：
    - 事件标准化：把 EgoCore 事件转换为 KernelEvent
    - 状态加载：从 mirror 文件加载 ProtoSelfState
    - kernel 调用：调用 process_event
    - 状态镜像：保存状态镜像
    - trace 写入：桥接到 EgoCore trace 系统
    """

    def __init__(
        self,
        mirror_dir: Optional[Path] = None,
        state_store: Optional[ProtoSelfStateStore] = None,
        trace_bridge: Optional[Any] = None,
    ):
        self.mirror_dir = mirror_dir or Path("artifacts/proto_self_mirror")
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = state_store or ProtoSelfStateStore(legacy_mirror_dir=self.mirror_dir)
        self.trace_bridge = trace_bridge

    def handle_event(self, egocore_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理 EgoCore 事件的主入口。

        流程：
        1. 标准化事件
        2. 加载状态
        3. 调用 kernel
        4. 保存镜像
        5. 写 trace
        6. 返回结果
        """
        event_id = egocore_event.get("event_id", "unknown")
        logger.info(f"[PSK-ADAPTER-01] handle_event called event_id={event_id}")

        # 1. 标准化事件
        logger.info(f"[PSK-ADAPTER-02] Normalizing event...")
        proto_self_input = normalize_to_proto_self_input(egocore_event)
        event_context = _extract_host_state_context(proto_self_input)

        # 2. 加载状态
        logger.info(f"[PSK-ADAPTER-03] Loading state via host store rooted at {self.state_store.root_dir}")
        state = self.load_latest_state(event_context=event_context)
        logger.info(f"[PSK-ADAPTER-04] State loaded, cycles={len(state.cycle_store.signatures) if hasattr(state, 'cycle_store') else 'N/A'}")

        # 3. 调用 kernel
        logger.info(f"[PSK-ADAPTER-05] Calling kernel process_event...")
        if isinstance(proto_self_input, UpdatePacketV2):
            result = process_update_packet(state, proto_self_input)
        else:
            result = process_event(state, proto_self_input)
        logger.info(f"[PSK-ADAPTER-06] Kernel returned, has_policy_hint={result.policy_hint is not None}")

        # 4. 边界检查
        assert_no_direct_execution(
            serialize_kernel_output_v2(result)
            if isinstance(proto_self_input, UpdatePacketV2)
            else result.to_dict()
        )

        # 5. 保存镜像
        mirror_path = self.mirror_dir / "state.json"
        logger.info(f"[PSK-ADAPTER-07] Saving mirror to {mirror_path}")
        self.save_mirror(state, event_context=event_context)
        logger.info(f"[PSK-ADAPTER-08] Mirror saved, exists={mirror_path.exists()}")

        session_id = event_context.get("session_id")
        if session_id:
            self.state_store.record_event_binding(
                session_id=session_id,
                thread_id=event_context.get("thread_id"),
                source=_input_source(proto_self_input),
                event_id=_input_event_id(proto_self_input),
                turn_id=event_context.get("turn_id"),
                event_type=_input_event_type(proto_self_input),
                context=event_context,
            )

        # 6. 写 trace
        if self.trace_bridge:
            logger.info(f"[PSK-ADAPTER-09] Writing trace via bridge...")
            self.trace_bridge.write(result.trace_payload)
            logger.info(f"[PSK-ADAPTER-10] Trace written")
        else:
            logger.warning(f"[PSK-ADAPTER-09] No trace_bridge available!")

        # 7. 返回结果
        logger.info(f"[PSK-ADAPTER-11] Returning result")
        if isinstance(proto_self_input, UpdatePacketV2):
            return serialize_kernel_output_v2(result)
        return serialize_kernel_output(result)

    def load_latest_state(self, *, event_context: Optional[Dict[str, Any]] = None) -> ProtoSelfState:
        """加载最新状态镜像。"""
        return self.state_store.load_state(event_context)

    def save_mirror(self, state: ProtoSelfState, *, event_context: Optional[Dict[str, Any]] = None) -> None:
        """保存状态镜像。"""
        self.state_store.save_state(state, event_context)


def normalize_to_kernel_event(egocore_event: Dict[str, Any]) -> KernelEvent:
    """
    把 EgoCore 事件标准化为 KernelEvent。

    这是 adapter 的核心职责：确保事件格式一致。
    """
    payload = dict(egocore_event)
    payload.setdefault("schema_version", V1_SCHEMA_VERSION)
    payload.setdefault("timestamp", datetime.now().isoformat())
    payload.setdefault("actor", "unknown")
    payload.setdefault("source", "unknown")
    payload.setdefault("event_type", "unknown")
    return kernel_event_from_payload(payload)


def normalize_to_proto_self_input(egocore_event: Dict[str, Any]) -> KernelEvent | UpdatePacketV2:
    payload = dict(egocore_event)
    payload.setdefault("timestamp", datetime.now().isoformat())
    if is_proto_self_v2_payload(payload):
        return update_packet_from_payload(payload)
    payload.setdefault("schema_version", V1_SCHEMA_VERSION)
    payload.setdefault("actor", "unknown")
    payload.setdefault("source", "unknown")
    payload.setdefault("event_type", "unknown")
    return kernel_event_from_payload(payload)


def _extract_host_state_context(proto_self_input: KernelEvent | UpdatePacketV2) -> Dict[str, Any]:
    if isinstance(proto_self_input, UpdatePacketV2):
        conversation_context = proto_self_input.conversation_summary or {}
        runtime_summary = proto_self_input.runtime_summary or {}
        source = proto_self_input.event.source
        event_type = proto_self_input.event.event_type
    else:
        conversation_context = proto_self_input.conversation_context or {}
        runtime_summary = proto_self_input.runtime_summary or {}
        source = proto_self_input.source
        event_type = proto_self_input.event_type
    return {
        "session_id": conversation_context.get("session_id"),
        "thread_id": conversation_context.get("thread_id") or conversation_context.get("conversation_id"),
        "turn_id": conversation_context.get("turn_id"),
        "source": source,
        "event_type": event_type,
        "state_scope": runtime_summary.get("state_scope"),
        "experiment_id": runtime_summary.get("experiment_id"),
    }


def _input_event_id(proto_self_input: KernelEvent | UpdatePacketV2) -> str:
    return proto_self_input.event_id


def _input_source(proto_self_input: KernelEvent | UpdatePacketV2) -> str:
    if isinstance(proto_self_input, UpdatePacketV2):
        return proto_self_input.event.source or "unknown"
    return proto_self_input.source or "unknown"


def _input_event_type(proto_self_input: KernelEvent | UpdatePacketV2) -> str:
    if isinstance(proto_self_input, UpdatePacketV2):
        return proto_self_input.event.event_type or "unknown"
    return proto_self_input.event_type or "unknown"
