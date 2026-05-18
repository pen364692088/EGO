"""Core modules for OpenEmotion MVP-7."""
from .provenance import (
    Provenance,
    Source,
    sign_payload,
    verify_signature,
    sign_artifact,
    verify_artifact,
    is_internal_source,
    validate_provenance_for_write,
)
from .drive_homeostasis import (
    DriveType,
    HomeostasisDrive,
    DriveState,
    get_drive,
    reset_drive,
)
from .self_model import (
    Identity,
    CapabilityBoundary,
    OwnershipBoundary,
    SelfModel,
    BoundaryType,
    render_self_report,
    validate_self_report,
)

__all__ = [
    # Provenance
    "Provenance",
    "Source",
    "sign_payload",
    "verify_signature",
    "sign_artifact",
    "verify_artifact",
    "is_internal_source",
    "validate_provenance_for_write",
    # Drive
    "DriveType",
    "HomeostasisDrive",
    "DriveState",
    "get_drive",
    "reset_drive",
    # Self-Model
    "Identity",
    "CapabilityBoundary",
    "OwnershipBoundary",
    "SelfModel",
    "BoundaryType",
    "render_self_report",
    "validate_self_report",
]
from .episodic_memory import (
    Episode,
    EpisodeStore,
)
__all__.extend(["Episode", "EpisodeStore"])
from .offline_rollouts import (
    RolloutEngine,
    RolloutBranch,
    RolloutCandidate,
)
from .dmn_tick import (
    DMNTick,
    ProactiveGate,
    TickAction,
)
__all__.extend([
    "RolloutEngine",
    "RolloutBranch",
    "RolloutCandidate",
    "DMNTick",
    "ProactiveGate",
    "TickAction",
])
