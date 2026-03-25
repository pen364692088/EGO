"""
OpenEmotion Package

内在主体核心模块。
"""

__version__ = "1.0.0"

# 导出正式接口 contracts
from openemotion.contracts.event_v1 import (
    OpenEmotionEventV1,
    EventSource,
    EventType,
    EVENT_V1_VERSION,
    EVENT_V1_FROZEN,
)
from openemotion.contracts.result_v1 import (
    OpenEmotionResultV1,
    ResultType,
    RESULT_V1_VERSION,
    RESULT_V1_FROZEN,
)
