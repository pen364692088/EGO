"""
Admission-grade developmental writeback adapter.

The host does not invent developmental state directly. It triggers a projection
sync from authoritative real-channel sample/ledger artifacts after a finalized
sample exists on disk.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _resolve_state_path(default_path: Path) -> Path:
    return Path(os.environ.get("EGO_DEVELOPMENTAL_STATE_PATH") or default_path)


def _resolve_observation_dir(default_dir: Path) -> Path:
    return Path(os.environ.get("EGO_DEVELOPMENTAL_OBSERVATION_DIR") or default_dir)


def sync_real_developmental_projection(
    *,
    sample_artifacts_dir: Path,
) -> Optional[Dict[str, Any]]:
    try:
        from emotiond.developmental import (
            DEFAULT_OBSERVATION_DIR,
            DEFAULT_STATE_PATH,
            get_developmental_manager,
            reset_developmental_manager,
        )
    except Exception as exc:
        logger.warning("developmental.writeback_import_failed error=%s", exc)
        return None

    state_path = _resolve_state_path(DEFAULT_STATE_PATH)
    observation_dir = _resolve_observation_dir(DEFAULT_OBSERVATION_DIR)

    try:
        reset_developmental_manager(state_path=state_path)
        manager = get_developmental_manager(state_path=state_path)
        return manager.sync_real_projection_from_sample_artifacts(
            sample_artifacts_dir=sample_artifacts_dir,
            observation_dir=observation_dir,
        )
    except Exception as exc:
        logger.warning("developmental.writeback_sync_failed error=%s", exc)
        return None


def record_developmental_projection_from_finalized_sample(
    *,
    sample: Any,
    sample_artifacts_dir: Path,
) -> Optional[Dict[str, Any]]:
    if sample is None:
        return None
    if getattr(sample, "channel", None) != "telegram":
        return None
    if getattr(sample, "source_type", None) != "real_channel":
        return None
    return sync_real_developmental_projection(sample_artifacts_dir=Path(sample_artifacts_dir))
