"""
Subject System v1 canonical facade.

This package normalizes existing proto-self v2 outputs into the bounded
host-consumable shape for the Subject System v1 governed-proactivity lane.
It does not introduce a second execution kernel.
"""

from openemotion.subject_system_v1.kernel import normalize_proto_self_result
from openemotion.subject_system_v1.schemas import (
    RESULT_SCHEMA_VERSION,
    SubjectIdentityInvariants,
    SubjectSystemV1Result,
)
from openemotion.subject_system_v1.state import (
    STATE_SCHEMA_VERSION,
    SubjectSystemV1State,
)

__all__ = [
    "RESULT_SCHEMA_VERSION",
    "STATE_SCHEMA_VERSION",
    "SubjectIdentityInvariants",
    "SubjectSystemV1Result",
    "SubjectSystemV1State",
    "normalize_proto_self_result",
]
