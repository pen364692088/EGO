"""Compatibility bridge for legacy OpenClaw user affect classifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_LEGACY_PATH = (
    Path(__file__).resolve().parents[3]
    / "legacy"
    / "openclaw"
    / "classifiers"
    / "user_affect.py"
)

_SPEC = importlib.util.spec_from_file_location(
    "legacy_openclaw_user_affect",
    _LEGACY_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Could not load legacy user_affect module from {_LEGACY_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

UserAffect = _MODULE.UserAffect
UserAffectClassifier = _MODULE.UserAffectClassifier
classify_user_affect = _MODULE.classify_user_affect
get_affect_for_emotiond = _MODULE.get_affect_for_emotiond

__all__ = [
    "UserAffect",
    "UserAffectClassifier",
    "classify_user_affect",
    "get_affect_for_emotiond",
]
