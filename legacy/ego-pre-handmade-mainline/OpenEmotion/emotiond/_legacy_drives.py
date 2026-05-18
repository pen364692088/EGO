"""
Shared loader for the legacy MVP10 drives module.

Legacy MVP10 modules still depend on the exact enum/class identity from
``emotiond/drives.py``. Load that file once here and re-export its symbols so
compatibility callers do not each create their own module instance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


_LEGACY_PATH = Path(__file__).resolve().with_name("drives.py")
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "emotiond_legacy_drives_module",
    _LEGACY_PATH,
)
if _LEGACY_SPEC is None or _LEGACY_SPEC.loader is None:
    raise ImportError(f"Could not load legacy drives module from {_LEGACY_PATH}")

_LEGACY_MODULE = importlib.util.module_from_spec(_LEGACY_SPEC)
_LEGACY_SPEC.loader.exec_module(_LEGACY_MODULE)

DriveType = _LEGACY_MODULE.DriveType
DriveLevel = _LEGACY_MODULE.DriveLevel
DriveCandidate = _LEGACY_MODULE.DriveCandidate
Drives = _LEGACY_MODULE.Drives
drives_from_valence = _LEGACY_MODULE.drives_from_valence

__all__ = [
    "DriveType",
    "DriveLevel",
    "DriveCandidate",
    "Drives",
    "drives_from_valence",
]
