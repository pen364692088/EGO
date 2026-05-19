from __future__ import annotations

import os
from pathlib import Path


def get_repo_root() -> Path:
    override = os.environ.get("EGO_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def get_egocore_root() -> Path:
    return get_repo_root() / "EgoCore"
