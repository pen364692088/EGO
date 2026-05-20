"""
Candidate-local primitives for EgoOperator.

These modules intentionally do not import EgoCore, OpenEmotion, or
ego_desktop_lab. They extract contracts and operator-facing behavior only.
"""

from .subject_context import SubjectContextSnapshot, build_minimal_subject_context
from .initiative import InitiativeProposal, build_initiative_proposal, validate_initiative_proposal

__all__ = [
    "InitiativeProposal",
    "SubjectContextSnapshot",
    "build_initiative_proposal",
    "build_minimal_subject_context",
    "validate_initiative_proposal",
]
