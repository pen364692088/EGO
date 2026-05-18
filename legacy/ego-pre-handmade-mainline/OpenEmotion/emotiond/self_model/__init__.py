"""
MVP-13: Extended Self-Model Infrastructure

This package provides:
- MVP13 extended schema (SelfModelState, IdentityCore, etc.)
- Persistence layer (SelfModelPersistence)
- Update rules (SelfModelUpdater)

Legacy self-model compatibility remains available via
``emotiond.self_model.legacy``.
"""

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
    "SelfModelManager",
    "get_self_model_manager",
    "reset_self_model_manager",
]
