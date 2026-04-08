"""
OpenEmotion Adapter for EgoCore

宿主侧适配层：把 OpenEmotion 内核安全接进 EgoCore 主链。

设计约束：
- 只做 normalize / load state / invoke kernel / save mirror / write trace
- 不允许在 adapter 里发明主体语义
- 不允许在 EgoCore 里追加长期 self-model 更新逻辑
- 所有主体本体语义必须留在 OpenEmotion
"""

from app.openemotion_adapter.proto_self_adapter import (
    ProtoSelfAdapter,
    normalize_to_kernel_event,
    normalize_to_proto_self_input,
)
from app.openemotion_adapter.proto_self_contract_validator import validate_proto_self_v2_payload
from app.openemotion_adapter.developmental_writeback import (
    record_developmental_projection_from_finalized_sample,
    sync_real_developmental_projection,
)
from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore
from app.openemotion_adapter.proto_self_trace_bridge import ProtoSelfTraceBridge

__all__ = [
    "ProtoSelfAdapter",
    "ProtoSelfStateStore",
    "ProtoSelfTraceBridge",
    "record_developmental_projection_from_finalized_sample",
    "normalize_to_kernel_event",
    "normalize_to_proto_self_input",
    "sync_real_developmental_projection",
    "validate_proto_self_v2_payload",
]
