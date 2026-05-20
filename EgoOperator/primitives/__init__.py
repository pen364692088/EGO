"""
Candidate-local primitives for EgoOperator.

These modules intentionally do not import EgoCore, OpenEmotion, or
ego_desktop_lab. They extract contracts and operator-facing behavior only.
"""

from .subject_context import SubjectContextSnapshot, build_minimal_subject_context
from .initiative import (
    InitiativeProposal,
    apply_quiet_mode_to_budget,
    build_initiative_proposal,
    derive_quiet_mode,
    validate_initiative_proposal,
)

__all__ = [
    "InitiativeProposal",
    "apply_quiet_mode_to_budget",
    "SubjectContextSnapshot",
    "build_initiative_proposal",
    "build_minimal_subject_context",
    "derive_quiet_mode",
    "validate_initiative_proposal",
]
