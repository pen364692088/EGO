"""
Proto-Self Kernel v2

Bounded vertical slice implementation:
- keeps V1 as current default runtime mainline
- adds explicit `proto_self.v2` schema/kernel/trace path
- preserves OpenEmotion as semantic authority
"""

from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import (
    OUTPUT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    KernelOutputV2,
    UpdateEventV2,
    UpdatePacketV2,
    is_proto_self_v2_payload,
    serialize_kernel_output_v2,
    update_packet_from_payload,
)
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE
from openemotion.proto_self_v2.state import ProtoSelfStateV2
from openemotion.proto_self_v2.developmental import DevelopmentalShadowState, run_developmental_cycle
from openemotion.proto_self_v2.trace_types import (
    TRACE_SCHEMA_VERSION,
    ProtoSelfTracePayloadV2,
    build_trace_payload_v2,
)

__all__ = [
    "SCHEMA_VERSION",
    "OUTPUT_SCHEMA_VERSION",
    "TRACE_SCHEMA_VERSION",
    "SEED_SUBJECT_PROFILE",
    "UpdateEventV2",
    "UpdatePacketV2",
    "KernelOutputV2",
    "ProtoSelfStateV2",
    "DevelopmentalShadowState",
    "ProtoSelfTracePayloadV2",
    "is_proto_self_v2_payload",
    "update_packet_from_payload",
    "serialize_kernel_output_v2",
    "build_trace_payload_v2",
    "run_developmental_cycle",
    "process_update_packet",
]
