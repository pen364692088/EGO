"""
EgoCore Adapters Module

包含 EgoCore 与外部系统之间的适配器。
"""

from .openemotion_adapter import (
    OpenEmotionAdapter,
    OpenEmotionBackend,
    MockBackend,
    RealHTTPBackend,
    EventInput,
    OpenEmotionOutput,
    AdapterMode,
    AdapterError,
    ValidationError,
    ConnectionError,
    TimeoutError,
    create_adapter,
)

__all__ = [
    "OpenEmotionAdapter",
    "OpenEmotionBackend",
    "MockBackend",
    "RealHTTPBackend",
    "EventInput",
    "OpenEmotionOutput",
    "AdapterMode",
    "AdapterError",
    "ValidationError",
    "ConnectionError",
    "TimeoutError",
    "create_adapter",
]
