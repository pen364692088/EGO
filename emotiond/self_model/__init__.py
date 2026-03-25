"""
MVP-13: Extended Self-Model Infrastructure

This package provides:
- Legacy self-model API (ValueWeights, SelfModel, SelfModelV0, etc.)
- MVP13 extended schema (SelfModelState, IdentityCore, etc.)
- Persistence layer (SelfModelPersistence)
- Update rules (SelfModelUpdater)
"""

# Legacy imports (for backward compatibility)
from .legacy import (
    ValueWeights,
    CapabilityBelief,
    CapabilityBeliefs,
    Goal,
    CurrentGoals,
    EvidenceEntry,
    UpdateLog,
    SelfModel,
    get_self_model,
    reset_self_model,
    get_self_model_v0,
    reset_self_model_v0,
    apply_self_model_to_decision,
    BodilySnapshot,
    RelationalSnapshot,
    CognitiveSnapshot,
    IdentitySnapshot,
    SelfModelV0,
    build_self_model_v0,
    render_self_report,
    render_three_layer_state,
    render_self_report_v2,
    render_three_layer_text,
)

# MVP13 new imports
from .schema import (
    SelfModelState,
    IdentityCore,
    StableConstraints,
    BehavioralTendencies,
    ActiveTension,
    ActiveTensions,
    TensionType,
    LongHorizonOrientation,
    LongHorizonOrientations,
    CapabilityModel,
    ContinuityTrace,
    ContinuityEntry,
    RevisionHistory,
    RevisionEntry,
)
from .persistence import SelfModelPersistence, get_persistence, reset_persistence
from .updates import (
    SelfModelUpdater,
    UpdateRuleError,
    IdentityInvariantViolation,
)
from .integration import (
    SelfModelManager,
    get_self_model_manager,
    reset_self_model_manager,
)

__all__ = [
    # Legacy API
    "ValueWeights",
    "CapabilityBelief",
    "CapabilityBeliefs",
    "Goal",
    "CurrentGoals",
    "EvidenceEntry",
    "UpdateLog",
    "SelfModel",
    "get_self_model",
    "reset_self_model",
    "get_self_model_v0",
    "reset_self_model_v0",
    "apply_self_model_to_decision",
    "BodilySnapshot",
    "RelationalSnapshot",
    "CognitiveSnapshot",
    "IdentitySnapshot",
    "SelfModelV0",
    "build_self_model_v0",
    "render_self_report",
    "render_three_layer_state",
    "render_self_report_v2",
    "render_three_layer_text",
    # MVP13 API
    "SelfModelState",
    "IdentityCore",
    "StableConstraints",
    "BehavioralTendencies",
    "ActiveTension",
    "ActiveTensions",
    "TensionType",
    "LongHorizonOrientation",
    "LongHorizonOrientations",
    "CapabilityModel",
    "ContinuityTrace",
    "ContinuityEntry",
    "RevisionHistory",
    "RevisionEntry",
    "SelfModelPersistence",
    "get_persistence",
    "reset_persistence",
    "SelfModelUpdater",
    "UpdateRuleError",
    "IdentityInvariantViolation",
    # Integration
    "SelfModelManager",
    "get_self_model_manager",
    "reset_self_model_manager",
]
