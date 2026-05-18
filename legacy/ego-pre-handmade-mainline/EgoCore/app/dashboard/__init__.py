"""Read-only Growth Dashboard helpers for Telegram real-mainline observation."""

from app.dashboard.chat_service import DashboardChatService
from app.dashboard.index_builder import build_dashboard_indexes
from app.dashboard.server import run_dashboard_server
from app.dashboard.types import (
    ContinuityObservationRecord,
    FailureIndexRecord,
    GrowthSignalRecord,
    RunIndexRecord,
)

__all__ = [
    "RunIndexRecord",
    "ContinuityObservationRecord",
    "GrowthSignalRecord",
    "FailureIndexRecord",
    "DashboardChatService",
    "build_dashboard_indexes",
    "run_dashboard_server",
]
