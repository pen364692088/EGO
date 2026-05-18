"""
Runtime Metrics Aggregator - Integration Tests

E2E 场景测试
"""

import pytest
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "modules" / "runtime_metrics_aggregator"))

from adapter.metrics_adapter import create_adapter


class TestE2EScenarios:
    """端到端场景测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_success_path(self):
        """E2E: 正常路径"""
        result = self.adapter.record_with_fallback(
            metric_name="session_created_total",
            metric_type="counter",
            value=1.0,
            labels={"source": "telegram", "status": "success"},
            module="session_manager"
        )
        
        assert result["success"] is True
        assert result["metric_id"] != "dropped"
        
        # 验证可查询
        query = self.adapter.query_metrics(name="session_created_total")
        assert query["total"] == 1
        assert query["metrics"][0]["name"] == "session_created_total"
    
    def test_empty_input(self):
        """E2E: 空输入处理"""
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        # fallback 返回 dropped
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_invalid_input(self):
        """E2E: 非法输入"""
        result = self.adapter.record_with_fallback(
            metric_name="Invalid-Name",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_query_by_labels(self):
        """E2E: 按标签查询"""
        # 记录不同标签的指标
        self.adapter.record_with_fallback(
            metric_name="requests_total",
            metric_type="counter",
            value=1.0,
            labels={"source": "telegram"},
            module="api"
        )
        self.adapter.record_with_fallback(
            metric_name="requests_total",
            metric_type="counter",
            value=1.0,
            labels={"source": "discord"},
            module="api"
        )
        
        # 按标签过滤
        query = self.adapter.query_metrics(
            name="requests_total",
            labels={"source": "telegram"}
        )
        
        assert query["total"] == 1
        assert query["metrics"][0]["labels"]["source"] == "telegram"
    
    def test_query_by_module(self):
        """E2E: 按模块查询"""
        self.adapter.record_with_fallback(
            metric_name="events",
            metric_type="counter",
            value=1.0,
            module="module_a"
        )
        self.adapter.record_with_fallback(
            metric_name="events",
            metric_type="counter",
            value=1.0,
            module="module_b"
        )
        
        query = self.adapter.query_metrics(module="module_a")
        assert query["total"] == 1
        assert query["metrics"][0]["module"] == "module_a"
    
    def test_query_by_time_window(self):
        """E2E: 按时间窗口查询"""
        # 记录指标
        self.adapter.record_with_fallback(
            metric_name="recent_event",
            metric_type="counter",
            value=1.0,
            timestamp=int(time.time() * 1000),
            module="test"
        )
        
        # 查询最近 1 小时
        query = self.adapter.query_metrics(
            name="recent_event",
            since_ms=3600000
        )
        
        assert query["total"] == 1
    
    def test_buffer_capacity(self):
        """E2E: 缓冲区容量"""
        # 创建小缓冲区适配器
        small_adapter = create_adapter(max_buffer_size=5)
        
        # 记录超过容量的指标
        for i in range(10):
            small_adapter.record_with_fallback(
                metric_name=f"metric_{i}",
                metric_type="counter",
                value=float(i),
                module="test"
            )
        
        # 查询所有指标
        query = small_adapter.query_metrics()
        
        # 应该只保留最近的 5 个
        assert query["total"] == 5


class TestConcurrentSafety:
    """并发安全测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_concurrent_record(self):
        """测试并发记录"""
        import threading
        
        results = []
        errors = []
        
        def record_metric(i):
            try:
                result = self.adapter.record_with_fallback(
                    metric_name="concurrent_test",
                    metric_type="counter",
                    value=1.0,
                    module="test"
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 启动多个线程
        threads = []
        for i in range(20):
            t = threading.Thread(target=record_metric, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待完成
        for t in threads:
            t.join()
        
        # 验证
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 20
        
        # 验证所有指标都被记录
        query = self.adapter.query_metrics(name="concurrent_test")
        assert query["total"] == 20


class TestMetricTypes:
    """指标类型测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_counter(self):
        """测试 counter 类型"""
        result = self.adapter.record_with_fallback(
            metric_name="test_counter",
            metric_type="counter",
            value=5.0,
            module="test"
        )
        
        assert result["success"] is True
        
        query = self.adapter.query_metrics(name="test_counter")
        assert query["metrics"][0]["type"] == "counter"
    
    def test_gauge(self):
        """测试 gauge 类型"""
        result = self.adapter.record_with_fallback(
            metric_name="test_gauge",
            metric_type="gauge",
            value=42.5,
            module="test"
        )
        
        assert result["success"] is True
        
        query = self.adapter.query_metrics(name="test_gauge")
        assert query["metrics"][0]["type"] == "gauge"
    
    def test_histogram(self):
        """测试 histogram 类型"""
        result = self.adapter.record_with_fallback(
            metric_name="test_histogram",
            metric_type="histogram",
            value=100.0,
            module="test"
        )
        
        assert result["success"] is True
        
        query = self.adapter.query_metrics(name="test_histogram")
        assert query["metrics"][0]["type"] == "histogram"
    
    def test_timer(self):
        """测试 timer 类型"""
        result = self.adapter.record_with_fallback(
            metric_name="test_timer",
            metric_type="timer",
            value=50.0,
            module="test"
        )
        
        assert result["success"] is True
        
        query = self.adapter.query_metrics(name="test_timer")
        assert query["metrics"][0]["type"] == "timer"
