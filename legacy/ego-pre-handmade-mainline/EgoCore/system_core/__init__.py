"""
EgoCore System Core

核心系统模块，提供基础服务和钩子点。
"""

from system_core.metrics_hook import MetricsHook, get_metrics_hook, record_metric, initialize_metrics

__all__ = [
    'MetricsHook',
    'get_metrics_hook',
    'record_metric',
    'initialize_metrics',
]
