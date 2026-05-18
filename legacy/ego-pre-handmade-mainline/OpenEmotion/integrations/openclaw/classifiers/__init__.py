"""Compatibility exports for legacy OpenClaw classifiers."""

from .user_affect import (
    UserAffect,
    UserAffectClassifier,
    classify_user_affect,
    get_affect_for_emotiond,
)

__all__ = [
    "UserAffect",
    "UserAffectClassifier",
    "classify_user_affect",
    "get_affect_for_emotiond",
]
