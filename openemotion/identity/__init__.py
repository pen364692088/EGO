"""
OpenEmotion Identity Module

身份不变量和长期摘要的正式本体模块。
"""

from .identity_invariants import (
    IdentityInvariants,
    NonNegotiableCommitment,
    ForbiddenZone,
    BindingLevel,
    ChangeTrigger,
    create_default_identity,
)

from .long_term_self_summary import (
    LongTermSelfSummary,
    KeyEvent,
    StableConclusion,
    OpenQuestion,
    RecoveryHints,
    generate_summary,
)

__all__ = [
    # Identity Invariants
    "IdentityInvariants",
    "NonNegotiableCommitment",
    "ForbiddenZone",
    "BindingLevel",
    "ChangeTrigger",
    "create_default_identity",

    # Long-Term Self Summary
    "LongTermSelfSummary",
    "KeyEvent",
    "StableConclusion",
    "OpenQuestion",
    "RecoveryHints",
    "generate_summary",
]
