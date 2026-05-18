"""
OpenEmotion Identity Module

Reference-only identity authoring/support surfaces.

This package is intentionally not the live runtime identity authority on the
current formal mainline.
"""

from .identity_invariants import (
    AUTHORITY_STATUS as IDENTITY_INVARIANTS_AUTHORITY_STATUS,
    FORMAL_MAINLINE_ENABLED as IDENTITY_INVARIANTS_FORMAL_MAINLINE_ENABLED,
    LIVE_RUNTIME_AUTHORITY as IDENTITY_INVARIANTS_LIVE_RUNTIME_AUTHORITY,
    REFERENCE_ONLY_REASON as IDENTITY_INVARIANTS_REFERENCE_ONLY_REASON,
    IdentityInvariants,
    NonNegotiableCommitment,
    ForbiddenZone,
    BindingLevel,
    ChangeTrigger,
    create_default_identity,
)

from .long_term_self_summary import (
    AUTHORITY_STATUS as LONG_TERM_SELF_SUMMARY_AUTHORITY_STATUS,
    FORMAL_MAINLINE_ENABLED as LONG_TERM_SELF_SUMMARY_FORMAL_MAINLINE_ENABLED,
    LIVE_RUNTIME_AUTHORITY as LONG_TERM_SELF_SUMMARY_LIVE_RUNTIME_AUTHORITY,
    REFERENCE_ONLY_REASON as LONG_TERM_SELF_SUMMARY_REFERENCE_ONLY_REASON,
    LongTermSelfSummary,
    KeyEvent,
    StableConclusion,
    OpenQuestion,
    RecoveryHints,
    generate_summary,
)

PACKAGE_AUTHORITY_STATUS = "reference_only"
PACKAGE_FORMAL_MAINLINE_ENABLED = False
PACKAGE_LIVE_RUNTIME_AUTHORITY = "openemotion.proto_self.state.IdentityInvariants"

__all__ = [
    "PACKAGE_AUTHORITY_STATUS",
    "PACKAGE_FORMAL_MAINLINE_ENABLED",
    "PACKAGE_LIVE_RUNTIME_AUTHORITY",

    # Identity Invariants
    "IDENTITY_INVARIANTS_AUTHORITY_STATUS",
    "IDENTITY_INVARIANTS_FORMAL_MAINLINE_ENABLED",
    "IDENTITY_INVARIANTS_LIVE_RUNTIME_AUTHORITY",
    "IDENTITY_INVARIANTS_REFERENCE_ONLY_REASON",
    "IdentityInvariants",
    "NonNegotiableCommitment",
    "ForbiddenZone",
    "BindingLevel",
    "ChangeTrigger",
    "create_default_identity",

    # Long-Term Self Summary
    "LONG_TERM_SELF_SUMMARY_AUTHORITY_STATUS",
    "LONG_TERM_SELF_SUMMARY_FORMAL_MAINLINE_ENABLED",
    "LONG_TERM_SELF_SUMMARY_LIVE_RUNTIME_AUTHORITY",
    "LONG_TERM_SELF_SUMMARY_REFERENCE_ONLY_REASON",
    "LongTermSelfSummary",
    "KeyEvent",
    "StableConclusion",
    "OpenQuestion",
    "RecoveryHints",
    "generate_summary",
]
