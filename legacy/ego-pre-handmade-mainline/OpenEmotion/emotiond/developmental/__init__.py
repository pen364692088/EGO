"""
MVP16: Open Developmental Self

Long-horizon developmental continuity with governed growth.

WP11 / MVP16 status:
- reference-only compatibility surface
- not the formal owner path
- not current-mainline closeout proof
"""
from pathlib import Path
from typing import Optional

from .schema import (
    DevelopmentalState,
    DevelopmentalEpisode,
    DevelopmentalWritebackEvent,
    TransitionRecord,
    GrowthMetric,
    DevelopmentalTrajectory,
)
from .manager import (
    DevelopmentalManager,
    DEFAULT_OBSERVATION_DIR,
    DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR,
    get_developmental_manager,
    reset_developmental_manager,
    DEFAULT_STATE_PATH,
)

__all__ = [
    "DevelopmentalState",
    "DevelopmentalEpisode",
    "DevelopmentalWritebackEvent",
    "TransitionRecord",
    "GrowthMetric",
    "DevelopmentalTrajectory",
    "DevelopmentalManager",
    "get_developmental_manager",
    "reset_developmental_manager",
    "DEFAULT_STATE_PATH",
    "DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR",
    "DEFAULT_OBSERVATION_DIR",
]
