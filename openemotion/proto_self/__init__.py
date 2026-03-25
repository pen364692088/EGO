"""
Proto-Self Kernel v1

最小可持续主体内核实现。

核心主张：
- 一个统一递归更新器 + 少量高价值状态 + 明确后果回流
- 事件进入 → 内态更新 → 生成倾向 → 经过 EgoCore 裁决 → 结果回流 → 强化/削弱自我不变量

边界约束：
- OpenEmotion 负责 identity / self-model / memory / appraisal / reflection 本体解释权
- EgoCore 负责渠道接入、运行时、工具执行、安全边界、治理、审计
- 不允许双主，不允许边界漂移
"""

from openemotion.proto_self.schemas import (
    KernelEvent,
    KernelOutput,
    ReflectionNote,
    ResponseTendency,
    SCHEMA_VERSION,
)
from openemotion.proto_self.state import (
    CycleSignature,
    CycleStore,
    DriveField,
    EpisodicRecord,
    IdentityInvariants,
    ProtoSelfState,
    SelfModel,
)
from openemotion.proto_self.trace_types import (
    ProtoSelfTracePayload,
    TRACE_SCHEMA_VERSION,
    build_trace_payload,
)

__all__ = [
    # Schemas
    "KernelEvent",
    "KernelOutput",
    "ReflectionNote",
    "ResponseTendency",
    "SCHEMA_VERSION",
    # State
    "ProtoSelfState",
    "IdentityInvariants",
    "SelfModel",
    "DriveField",
    "CycleStore",
    "CycleSignature",
    "EpisodicRecord",
    # Trace
    "ProtoSelfTracePayload",
    "TRACE_SCHEMA_VERSION",
    "build_trace_payload",
]
