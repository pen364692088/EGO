"""
Runtime Metrics Aggregator - Self Observability

自身指标收集（自举）
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import time


@dataclass
class SelfMetricsSnapshot:
    """自身指标快照"""
    received_total: int = 0
    dropped_total: int = 0
    storage_errors_total: int = 0
    query_count: int = 0
    query_latency_sum_ms: int = 0


class SelfMetricsCollector:
    """自身指标收集器"""
    
    def __init__(self):
        self._received = 0
        self._dropped = 0
        self._storage_errors = 0
        self._query_count = 0
        self._query_latency_sum = 0
    
    def record_received(self) -> None:
        """记录接收"""
        self._received += 1
    
    def record_dropped(self) -> None:
        """记录丢弃"""
        self._dropped += 1
    
    def record_storage_error(self) -> None:
        """记录存储错误"""
        self._storage_errors += 1
    
    def record_query(self, latency_ms: int) -> None:
        """记录查询"""
        self._query_count += 1
        self._query_latency_sum += latency_ms
    
    def get_snapshot(self) -> SelfMetricsSnapshot:
        """获取快照"""
        return SelfMetricsSnapshot(
            received_total=self._received,
            dropped_total=self._dropped,
            storage_errors_total=self._storage_errors,
            query_count=self._query_count,
            query_latency_sum_ms=self._query_latency_sum
        )
    
    def get_avg_query_latency(self) -> float:
        """获取平均查询延迟"""
        if self._query_count == 0:
            return 0.0
        return self._query_latency_sum / self._query_count


class SelfLogger:
    """自身日志记录器"""
    
    LEVELS = ["debug", "info", "warning", "error"]
    
    def __init__(self, level: str = "info", sample_rate: float = 0.1):
        self.level = level
        self.sample_rate = sample_rate
        self._logs = []
    
    def _should_log(self, level: str) -> bool:
        """判断是否应该记录"""
        if self.LEVELS.index(level) < self.LEVELS.index(self.level):
            return False
        return True
    
    def _log(self, level: str, message: str, **kwargs) -> None:
        """内部日志方法"""
        if not self._should_log(level):
            return
        
        entry = {
            "timestamp": int(time.time() * 1000),
            "level": level,
            "message": message,
            "extra": kwargs
        }
        self._logs.append(entry)
        # 实际实现中输出到日志系统
        print(f"[METRICS][{level.upper()}] {message}")
    
    def debug(self, message: str, **kwargs) -> None:
        """调试日志"""
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """信息日志"""
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """警告日志"""
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """错误日志"""
        self._log("error", message, **kwargs)
    
    def get_logs(self) -> list:
        """获取日志"""
        return self._logs.copy()


def create_self_metrics() -> SelfMetricsCollector:
    """创建自身指标收集器"""
    return SelfMetricsCollector()


def create_self_logger(level: str = "info", sample_rate: float = 0.1) -> SelfLogger:
    """创建自身日志记录器"""
    return SelfLogger(level=level, sample_rate=sample_rate)
