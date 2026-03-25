"""
US-7102 Phase 4: Observability & Replay Tests

Test metrics collection, aggregation, and replay capabilities.
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

from emotiond.tool_metrics import (
    ToolMetricsCollector, ToolMetric, AggregatedMetrics,
    get_metrics_collector
)
from emotiond.tool_executor import (
    ToolExecutor, ExecutionConfig, ExecutionReasonCode, RetryPolicy
)
from emotiond.tool_registry import IOSchema


class TestToolMetric:
    """Test ToolMetric dataclass"""
    
    def test_create_metric(self):
        metric = ToolMetric(
            trace_id="test-1",
            tool_name="test_tool",
            timestamp="2026-03-02T10:00:00",
            duration_ms=100.5,
            success=True,
            reason_code="exec_success"
        )
        
        assert metric.trace_id == "test-1"
        assert metric.tool_name == "test_tool"
        assert metric.success is True
        assert metric.retry_count == 0
    
    def test_metric_with_metadata(self):
        metric = ToolMetric(
            trace_id="test-2",
            tool_name="test_tool",
            timestamp="2026-03-02T10:00:00",
            duration_ms=50.0,
            success=False,
            reason_code="input_schema_invalid",
            error_message="Missing required field",
            metadata={"user_id": "user-A"}
        )
        
        assert metric.success is False
        assert metric.error_message == "Missing required field"
        assert metric.metadata["user_id"] == "user-A"


class TestToolMetricsCollector:
    """Test metrics collection"""
    
    def test_singleton(self):
        """Should return same instance"""
        c1 = ToolMetricsCollector(metrics_file="/tmp/test_metrics_1.json")
        c2 = ToolMetricsCollector(metrics_file="/tmp/test_metrics_1.json")
        
        assert c1 is c2
    
    def test_record_metric(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            # Create new collector with temp file
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            
            metric = ToolMetric(
                trace_id="test-1",
                tool_name="test_tool",
                timestamp=datetime.utcnow().isoformat(),
                duration_ms=100.0,
                success=True,
                reason_code="exec_success"
            )
            
            collector.record(metric)
            
            # Check in-memory
            assert len(collector._metrics) == 1
            assert collector._metrics[0].trace_id == "test-1"
            
        finally:
            os.unlink(metrics_file)
    
    def test_aggregate_metrics(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            # Add multiple metrics
            for i in range(10):
                metric = ToolMetric(
                    trace_id=f"test-{i}",
                    tool_name="test_tool",
                    timestamp=datetime.utcnow().isoformat(),
                    duration_ms=100.0 + i * 10,
                    success=i % 2 == 0,
                    reason_code="exec_success" if i % 2 == 0 else "tool_result_invalid",
                    retry_count=i if i % 2 == 1 else 0
                )
                collector.record(metric)
            
            aggregated = collector.aggregate()
            
            assert "test_tool" in aggregated
            agg = aggregated["test_tool"]
            assert agg.total_executions == 10
            assert agg.successful == 5
            assert agg.failed == 5
            assert agg.success_rate == 0.5
            assert agg.avg_duration_ms > 0
            
        finally:
            os.unlink(metrics_file)
    
    def test_percentile_calculation(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            # Add metrics with known durations
            for i in range(100):
                metric = ToolMetric(
                    trace_id=f"test-{i}",
                    tool_name="test_tool",
                    timestamp=datetime.utcnow().isoformat(),
                    duration_ms=float(i + 1),  # 1-100 ms
                    success=True,
                    reason_code="exec_success"
                )
                collector.record(metric)
            
            aggregated = collector.aggregate()
            agg = aggregated["test_tool"]
            
            # P50 should be around 50
            assert 45 <= agg.p50_duration_ms <= 55
            # P95 should be around 95
            assert 90 <= agg.p95_duration_ms <= 100
            # P99 should be around 99
            assert 95 <= agg.p99_duration_ms <= 100
            
        finally:
            os.unlink(metrics_file)
    
    def test_flush_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            metric = ToolMetric(
                trace_id="test-flush",
                tool_name="test_tool",
                timestamp=datetime.utcnow().isoformat(),
                duration_ms=100.0,
                success=True,
                reason_code="exec_success"
            )
            collector.record(metric)
            
            # Force flush
            collector.flush()
            
            # Check file exists and has content
            assert os.path.exists(metrics_file)
            with open(metrics_file) as f:
                data = json.load(f)
            
            assert len(data) >= 1
            assert data[0]["trace_id"] == "test-flush"
            
        finally:
            if os.path.exists(metrics_file):
                os.unlink(metrics_file)
    
    def test_replay_by_tool_name(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            # Add metrics for different tools
            for tool in ["tool_a", "tool_b"]:
                for i in range(5):
                    metric = ToolMetric(
                        trace_id=f"{tool}-{i}",
                        tool_name=tool,
                        timestamp=datetime.utcnow().isoformat(),
                        duration_ms=100.0,
                        success=True,
                        reason_code="exec_success"
                    )
                    collector.record(metric)
            
            # Replay only tool_a
            results = collector.replay(tool_name="tool_a")
            
            assert len(results) == 5
            assert all(m.tool_name == "tool_a" for m in results)
            
        finally:
            os.unlink(metrics_file)
    
    def test_replay_by_success_filter(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            # Add mixed success/failure
            for i in range(10):
                metric = ToolMetric(
                    trace_id=f"test-{i}",
                    tool_name="test_tool",
                    timestamp=datetime.utcnow().isoformat(),
                    duration_ms=100.0,
                    success=i % 2 == 0,
                    reason_code="exec_success" if i % 2 == 0 else "tool_error"
                )
                collector.record(metric)
            
            # Replay only failures
            failures = collector.replay(failure_only=True)
            
            assert len(failures) == 5
            assert all(not m.success for m in failures)
            
        finally:
            os.unlink(metrics_file)
    
    def test_replay_by_trace_id(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            for i in range(5):
                metric = ToolMetric(
                    trace_id=f"trace-{i}",
                    tool_name="test_tool",
                    timestamp=datetime.utcnow().isoformat(),
                    duration_ms=100.0,
                    success=True,
                    reason_code="exec_success"
                )
                collector.record(metric)
            
            # Get specific trace
            result = collector.replay_as_trace("trace-3")
            
            assert result is not None
            assert result.trace_id == "trace-3"
            
            # Non-existent trace
            result = collector.replay_as_trace("trace-999")
            assert result is None
            
        finally:
            os.unlink(metrics_file)


class TestExecutorIntegration:
    """Test ToolExecutor integration with metrics"""
    
    def test_executor_records_metrics(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            executor = ToolExecutor(metrics_collector=collector)
            
            result = executor.execute(
                tool_name="test_tool",
                tool_impl=lambda i, c: {"status": "ok"},
                inputs={},
                io_schema=IOSchema(inputs={}, outputs={"status": "string"}),
                trace_id="test-metrics-1"
            )
            
            assert result.success is True
            
            # Check metrics were recorded
            assert len(collector._metrics) == 1
            metric = collector._metrics[0]
            assert metric.tool_name == "test_tool"
            assert metric.success is True
            assert metric.trace_id == "test-metrics-1"
            
        finally:
            os.unlink(metrics_file)
    
    def test_executor_records_failed_metrics(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            collector = ToolMetricsCollector.__new__(ToolMetricsCollector)
            collector._initialized = False
            collector.__init__(metrics_file=metrics_file)
            collector._metrics.clear()
            
            executor = ToolExecutor(
                metrics_collector=collector,
                retry_policy=RetryPolicy(max_retries=0)
            )
            
            result = executor.execute(
                tool_name="failing_tool",
                tool_impl=lambda i, c: (_ for _ in ()).throw(RuntimeError("Tool failed")),
                inputs={},
                io_schema=IOSchema(inputs={}, outputs={}),
                trace_id="test-metrics-fail"
            )
            
            assert result.success is False
            
            # Check metrics recorded failure
            metric = collector._metrics[0]
            assert metric.success is False
            assert metric.tool_name == "failing_tool"
            assert "failed" in metric.error_message.lower() or "error" in metric.error_message.lower()
            
        finally:
            os.unlink(metrics_file)
    
    def test_aggregated_summary(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            metrics_file = f.name
        
        try:
            # Reset singleton
            ToolMetricsCollector._instance = None
            collector = ToolMetricsCollector(metrics_file=metrics_file)
            collector._metrics.clear()
            
            executor = ToolExecutor(metrics_collector=collector)
            
            # Execute multiple times
            for i in range(20):
                executor.execute(
                    tool_name=f"tool_{i % 3}",
                    tool_impl=lambda inp, ctx: {"result": str(inp.get("x", "default"))},
                    inputs={"x": i} if i % 2 == 0 else {},
                    io_schema=IOSchema(inputs={}, outputs={"result": "string"}),
                    trace_id=f"test-{i}"
                )
            
            summary = collector.get_summary()
            
            assert summary["total_executions"] == 20
            assert summary["total_tools"] == 3
            assert summary["overall_success_rate"] == 1.0
            
        finally:
            ToolMetricsCollector._instance = None
            if os.path.exists(metrics_file):
                os.unlink(metrics_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
