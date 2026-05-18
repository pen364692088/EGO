"""
Cycle Core - 循环主体核

版本: v1.0.0
"""

from openemotion.cycle_core.state import (
    LatentSelfState,
    IdentityAnchors,
    GoalActivation,
    ConstraintActivation,
    AffectiveTension,
    ObjectStance,
    RelationBias,
    StabilityMetrics,
    STATE_V1_VERSION,
)
from openemotion.cycle_core.kernel import (
    CycleCoreKernel,
    CycleTrace,
    KERNEL_V1_VERSION,
)
from openemotion.cycle_core.memory_gate import (
    MemoryGate,
    MemoryGateResult,
    MemoryWriteDecision,
    MEMORY_GATE_V1_VERSION,
)
from openemotion.cycle_core.readout import (
    ReadoutDecoder,
    ReadoutResult,
    ResponseTendency,
    PolicyHint,
    READOUT_V1_VERSION,
)

__all__ = [
    # State
    "LatentSelfState",
    "IdentityAnchors",
    "GoalActivation",
    "ConstraintActivation",
    "AffectiveTension",
    "ObjectStance",
    "RelationBias",
    "StabilityMetrics",
    "STATE_V1_VERSION",
    # Kernel
    "CycleCoreKernel",
    "CycleTrace",
    "KERNEL_V1_VERSION",
    # Memory Gate
    "MemoryGate",
    "MemoryGateResult",
    "MemoryWriteDecision",
    "MEMORY_GATE_V1_VERSION",
    # Readout
    "ReadoutDecoder",
    "ReadoutResult",
    "ResponseTendency",
    "PolicyHint",
    "READOUT_V1_VERSION",
]

CYCLE_CORE_V1_VERSION = "1.0.0"
