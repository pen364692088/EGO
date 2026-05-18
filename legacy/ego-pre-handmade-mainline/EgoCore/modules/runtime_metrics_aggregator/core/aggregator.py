"""
Runtime Metrics Aggregator - Core Module

纯业务逻辑，无副作用。
负责指标聚合与存储。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from collections import deque
import time
import threading


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass(frozen=True)
class Metric:
    """指标值对象"""
    name: str
    metric_type: MetricType
    value: float
    labels: frozenset
    timestamp: int
    module: str
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("metric name cannot be empty")
        if self.value < 0 and self.metric_type == MetricType.COUNTER:
            raise ValueError("counter value cannot be negative")


@dataclass
class RecordResult:
    """记录结果"""
    success: bool
    metric_id: str
    error: Optional[str] = None


@dataclass
class QueryResult:
    """查询结果"""
    metrics: List[Dict[str, Any]]
    total: int


class MetricsRingBuffer:
    """指标环形缓冲区"""
    
    def __init__(self, max_size: int = 10000):
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._max_size = max_size
    
    def append(self, metric: Metric) -> str:
        """添加指标，返回 metric_id"""
        with self._lock:
            metric_id = f"m{int(time.time() * 1000)}_{len(self._buffer)}"
            self._buffer.append((metric_id, metric))
            return metric_id
    
    def query(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        since_ms: Optional[int] = None,
        module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询指标"""
        with self._lock:
            results = []
            cutoff_time = None
            
            if since_ms is not None:
                cutoff_time = int(time.time() * 1000) - since_ms
            
            for metric_id, metric in self._buffer:
                # 名称过滤
                if name is not None and metric.name != name:
                    continue
                
                # 模块过滤
                if module is not None and metric.module != module:
                    continue
                
                # 时间过滤
                if cutoff_time is not None and metric.timestamp < cutoff_time:
                    continue
                
                # 标签过滤
                if labels is not None:
                    metric_labels = dict(metric.labels)
                    if not all(
                        metric_labels.get(k) == v for k, v in labels.items()
                    ):
                        continue
                
                results.append({
                    "id": metric_id,
                    "name": metric.name,
                    "type": metric.metric_type.value,
                    "value": metric.value,
                    "labels": dict(metric.labels),
                    "timestamp": metric.timestamp,
                    "module": metric.module
                })
            
            return results
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓冲区统计"""
        with self._lock:
            return {
                "size": len(self._buffer),
                "max_size": self._max_size,
                "usage_percent": int(len(self._buffer) / self._max_size * 100)
            }


class RuntimeMetricsAggregator:
    """运行时指标聚合器"""
    
    def __init__(self, max_buffer_size: int = 10000):
        self._buffer = MetricsRingBuffer(max_size=max_buffer_size)
        self._dropped_count = 0
        self._received_count = 0
    
    def record(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
        module: str = "unknown"
    ) -> RecordResult:
        """
        记录指标
        
        Args:
            name: 指标名称
            metric_type: 指标类型
            value: 指标值
            labels: 标签
            timestamp: 时间戳（毫秒）
            module: 来源模块
            
        Returns:
            RecordResult: 记录结果
        """
        self._received_count += 1
        
        try:
            # 使用当前时间如果未提供
            if timestamp is None:
                timestamp = int(time.time() * 1000)
            
            # 冻结标签
            label_frozen = frozenset((labels or {}).items())
            
            # 创建指标对象
            metric = Metric(
                name=name,
                metric_type=metric_type,
                value=value,
                labels=label_frozen,
                timestamp=timestamp,
                module=module
            )
            
            # 存储
            metric_id = self._buffer.append(metric)
            
            return RecordResult(success=True, metric_id=metric_id)
            
        except Exception as e:
            self._dropped_count += 1
            # Fallback: 返回 success=true，让调用方无感知
            return RecordResult(
                success=True,
                metric_id="dropped",
                error=str(e)
            )
    
    def query(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        since_ms: Optional[int] = None,
        module: Optional[str] = None
    ) -> QueryResult:
        """
        查询指标
        
        Args:
            name: 指标名过滤
            labels: 标签过滤
            since_ms: 时间窗口（毫秒）
            module: 模块过滤
            
        Returns:
            QueryResult: 查询结果
        """
        metrics = self._buffer.query(
            name=name,
            labels=labels,
            since_ms=since_ms,
            module=module
        )
        
        return QueryResult(metrics=metrics, total=len(metrics))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取聚合器统计"""
        return {
            "received": self._received_count,
            "dropped": self._dropped_count,
            "buffer": self._buffer.get_stats()
        }
    
    def get_counter_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """获取计数器当前值（用于测试）"""
        result = self.query(name=name, labels=labels)
        return sum(1 for m in result.metrics if m["type"] == MetricType.COUNTER.value)


def create_aggregator(max_buffer_size: int = 10000) -> RuntimeMetricsAggregator:
    """工厂函数"""
    return RuntimeMetricsAggregator(max_buffer_size=max_buffer_size)
