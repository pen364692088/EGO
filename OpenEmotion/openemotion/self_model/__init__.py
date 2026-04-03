"""
OpenEmotion Self-Model Module

自我模型的正式本体模块。
"""

from .model import (
    Capability,
    CapabilityLevel,
    FORMAL_OWNER_SCHEMA_VERSION,
    Goal,
    GoalStatus,
    Limitation,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    Priority,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    SelfModel,
    StandingCommitment,
    create_default_self_model,
)
from .replay import SelfModelReplay, SelfModelReplayResult
from .store import SelfModelRevisionRecord, SelfModelStore

__all__ = [
    "SelfModel",
    "Capability",
    "Limitation",
    "Goal",
    "StandingCommitment",
    "CapabilityLevel",
    "GoalStatus",
    "Priority",
    "FORMAL_OWNER_SCHEMA_VERSION",
    "PHASE1_AUTHORITATIVE_FIELDS",
    "PHASE1_ALLOWED_PROOF_LEVERS",
    "PHASE1_LEGACY_REFERENCE_ONLY_FIELDS",
    "RUNTIME_LOCAL_PROJECTION_FIELD",
    "RUNTIME_LOCAL_PROJECTION_SEMANTICS",
    "SelfModelStore",
    "SelfModelRevisionRecord",
    "SelfModelReplay",
    "SelfModelReplayResult",
    "create_default_self_model",
]
