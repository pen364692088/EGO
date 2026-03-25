"""
US-7102 Phase 4: Observability & Replay

Tool metrics collection, aggregation, and replay capabilities.
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolMetric:
    """Single tool execution metric"""
    trace_id: str
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    reason_code: str
    retry_count: int = 0
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    sanitized: bool = False
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for a tool"""
    tool_name: str
    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    total_retries: int = 0
    avg_retries: float = 0.0
    total_input_bytes: int = 0
    total_output_bytes: int = 0
    avg_input_bytes: float = 0.0
    avg_output_bytes: float = 0.0
    sanitization_rate: float = 0.0
    reason_distribution: Dict[str, int] = field(default_factory=dict)
    error_types: Dict[str, int] = field(default_factory=dict)


class ToolMetricsCollector:
    """
    Collects, aggregates, and persists tool execution metrics.
    
    Thread-safe singleton for metrics collection across all tool executions.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        metrics_file: str = "tool_metrics.json",
        max_in_memory: int = 10000,
        flush_interval_seconds: int = 60
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.metrics_file = Path(metrics_file)
        self.max_in_memory = max_in_memory
        self.flush_interval = flush_interval_seconds
        
        self._metrics: List[ToolMetric] = []
        self._metrics_lock = threading.Lock()
        self._last_flush = time.time()
        
        # Register shutdown handler
        import atexit
        atexit.register(self.flush)
        
        # Load existing metrics if file exists
        self._load_metrics()
    
    def record(self, metric: ToolMetric) -> None:
        """Record a tool execution metric"""
        with self._metrics_lock:
            self._metrics.append(metric)
            
            # Flush if needed
            if len(self._metrics) >= self.max_in_memory:
                self._flush_unsafe()
            elif time.time() - self._last_flush >= self.flush_interval:
                self._flush_unsafe()
    
    def record_execution(
        self,
        trace_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool,
        reason_code: str,
        retry_count: int = 0,
        input_data: Any = None,
        output_data: Any = None,
        sanitized: bool = False,
        error_message: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Convenience method to record from execution result"""
        metric = ToolMetric(
            trace_id=trace_id,
            tool_name=tool_name,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            success=success,
            reason_code=reason_code,
            retry_count=retry_count,
            input_size_bytes=self._estimate_size(input_data),
            output_size_bytes=self._estimate_size(output_data),
            sanitized=sanitized,
            error_message=error_message,
            metadata=metadata or {}
        )
        self.record(metric)
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate size of data in bytes"""
        if data is None:
            return 0
        try:
            return len(json.dumps(data))
        except:
            return 0
    
    def aggregate(self, tool_name: str = None) -> Dict[str, AggregatedMetrics]:
        """Aggregate metrics by tool name"""
        with self._metrics_lock:
            metrics_to_aggregate = list(self._metrics)
        
        # Group by tool name
        by_tool: Dict[str, List[ToolMetric]] = defaultdict(list)
        for m in metrics_to_aggregate:
            if tool_name is None or m.tool_name == tool_name:
                by_tool[m.tool_name].append(m)
        
        result = {}
        for tool, metrics in by_tool.items():
            result[tool] = self._aggregate_tool_metrics(tool, metrics)
        
        return result
    
    def _aggregate_tool_metrics(self, tool_name: str, metrics: List[ToolMetric]) -> AggregatedMetrics:
        """Aggregate metrics for a single tool"""
        if not metrics:
            return AggregatedMetrics(tool_name=tool_name)
        
        durations = sorted([m.duration_ms for m in metrics])
        successes = sum(1 for m in metrics if m.success)
        failures = len(metrics) - successes
        total_retries = sum(m.retry_count for m in metrics)
        sanitized_count = sum(1 for m in metrics if m.sanitized)
        
        # Reason distribution
        reason_dist: Dict[str, int] = defaultdict(int)
        for m in metrics:
            reason_dist[m.reason_code] += 1
        
        # Error types
        error_types: Dict[str, int] = defaultdict(int)
        for m in metrics:
            if m.error_message:
                error_type = m.error_message.split(':')[0][:50]
                error_types[error_type] += 1
        
        return AggregatedMetrics(
            tool_name=tool_name,
            total_executions=len(metrics),
            successful=successes,
            failed=failures,
            success_rate=successes / len(metrics) if metrics else 0,
            avg_duration_ms=sum(durations) / len(durations) if durations else 0,
            p50_duration_ms=self._percentile(durations, 50),
            p95_duration_ms=self._percentile(durations, 95),
            p99_duration_ms=self._percentile(durations, 99),
            total_retries=total_retries,
            avg_retries=total_retries / len(metrics) if metrics else 0,
            total_input_bytes=sum(m.input_size_bytes for m in metrics),
            total_output_bytes=sum(m.output_size_bytes for m in metrics),
            avg_input_bytes=sum(m.input_size_bytes for m in metrics) / len(metrics) if metrics else 0,
            avg_output_bytes=sum(m.output_size_bytes for m in metrics) / len(metrics) if metrics else 0,
            sanitization_rate=sanitized_count / len(metrics) if metrics else 0,
            reason_distribution=dict(reason_dist),
            error_types=dict(error_types)
        )
    
    def _percentile(self, sorted_values: List[float], p: float) -> float:
        """Calculate percentile from sorted values"""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics across all tools"""
        aggregated = self.aggregate()
        
        if not aggregated:
            return {
                "total_tools": 0,
                "total_executions": 0,
                "overall_success_rate": 0,
                "tools": {}
            }
        
        total_executions = sum(a.total_executions for a in aggregated.values())
        total_successes = sum(a.successful for a in aggregated.values())
        
        return {
            "total_tools": len(aggregated),
            "total_executions": total_executions,
            "overall_success_rate": total_successes / total_executions if total_executions else 0,
            "tools": {name: asdict(metrics) for name, metrics in aggregated.items()}
        }
    
    def flush(self) -> None:
        """Flush metrics to disk"""
        with self._metrics_lock:
            self._flush_unsafe()
    
    def _flush_unsafe(self) -> None:
        """Flush without lock (caller must hold lock)"""
        if not self._metrics:
            return
        
        # Load existing
        existing = self._load_from_file()
        
        # Append new metrics
        existing.extend([asdict(m) for m in self._metrics])
        
        # Write to file
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(existing, f, indent=2)
            self._metrics.clear()
            self._last_flush = time.time()
            logger.debug(f"Flushed {len(existing)} metrics to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
    
    def _load_metrics(self) -> None:
        """Load existing metrics from file"""
        existing = self._load_from_file()
        # Only load recent ones to memory
        recent = existing[-self.max_in_memory:]
        with self._metrics_lock:
            self._metrics = [ToolMetric(**m) for m in recent]
    
    def _load_from_file(self) -> List[Dict]:
        """Load metrics from file"""
        if not self.metrics_file.exists():
            return []
        
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")
            return []
    
    def replay(
        self,
        tool_name: str = None,
        start_time: str = None,
        end_time: str = None,
        success_only: bool = False,
        failure_only: bool = False,
        limit: int = None
    ) -> List[ToolMetric]:
        """
        Replay/query historical metrics.
        
        Args:
            tool_name: Filter by tool name
            start_time: ISO timestamp start
            end_time: ISO timestamp end
            success_only: Only successful executions
            failure_only: Only failed executions
            limit: Max number of results
        
        Returns:
            List of matching metrics
        """
        with self._metrics_lock:
            metrics = list(self._metrics)
        
        # Apply filters
        if tool_name:
            metrics = [m for m in metrics if m.tool_name == tool_name]
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        if success_only:
            metrics = [m for m in metrics if m.success]
        
        if failure_only:
            metrics = [m for m in metrics if not m.success]
        
        if limit:
            metrics = metrics[:limit]
        
        return metrics
    
    def replay_as_trace(self, trace_id: str) -> Optional[ToolMetric]:
        """Get a specific trace by ID"""
        with self._metrics_lock:
            for m in self._metrics:
                if m.trace_id == trace_id:
                    return m
        return None
    
    def clear(self) -> None:
        """Clear all metrics (use with caution)"""
        with self._metrics_lock:
            self._metrics.clear()
        
        # Also clear file
        if self.metrics_file.exists():
            try:
                os.remove(self.metrics_file)
            except Exception as e:
                logger.warning(f"Failed to remove metrics file: {e}")


# Global singleton
_metrics_collector: Optional[ToolMetricsCollector] = None


def get_metrics_collector(metrics_file: str = None) -> ToolMetricsCollector:
    """Get or create the global metrics collector"""
    global _metrics_collector
    
    if _metrics_collector is None:
        kwargs = {}
        if metrics_file:
            kwargs['metrics_file'] = metrics_file
        _metrics_collector = ToolMetricsCollector(**kwargs)
    
    return _metrics_collector
