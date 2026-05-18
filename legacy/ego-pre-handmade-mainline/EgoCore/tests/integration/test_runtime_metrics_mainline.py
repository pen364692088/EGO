"""
Runtime Metrics Aggregator - Mainline Integration Tests

验证正式接入后的主链行为一致性
"""

import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from system_core import MetricsHook, get_metrics_hook, record_metric, initialize_metrics


class TestFlagOffConsistency:
    """Flag OFF 时主链行为一致性测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "false"
        self.hook = MetricsHook()
        self.hook.initialize()
    
    def test_record_returns_dropped_when_disabled(self):
        """禁用时记录返回 dropped，不影响主链"""
        result = self.hook.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_query_returns_empty_when_disabled(self):
        """禁用时查询返回空，不影响主链"""
        result = self.hook.query()
        
        assert result["metrics"] == []
        assert result["total"] == 0
    
    def test_no_exception_on_any_input(self):
        """任何输入都不抛异常"""
        # 无效输入
        result1 = self.hook.record("", "counter", 1.0, module="test")
        assert result1["success"] is True
        
        # None 输入
        result2 = self.hook.record("test", "counter", None, module="test")
        assert result2["success"] is True
    
    def test_stats_show_disabled(self):
        """状态显示 disabled"""
        stats = self.hook.get_stats()
        
        assert stats["initialized"] is True
        assert stats["enabled"] is False


class TestFlagOnNormalPath:
    """Flag ON 时正常路径测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        os.environ["runtime_metrics_shadow"] = "true"
        self.hook = MetricsHook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_record_stores_metric(self):
        """启用时记录存储指标"""
        result = self.hook.record(
            metric_name="test_counter",
            metric_type="counter",
            value=1.0,
            labels={"source": "test"},
            module="test_module"
        )
        
        assert result["success"] is True
        assert result["metric_id"] != "dropped"
    
    def test_query_returns_stored_metrics(self):
        """查询返回存储的指标"""
        self.hook.record("test_gauge", "gauge", 42.0, module="test")
        
        result = self.hook.query(name="test_gauge")
        
        assert result["total"] >= 1
    
    def test_shadow_mode_is_default(self):
        """默认 shadow 模式"""
        assert self.hook.is_shadow_mode() is True


class TestExceptionIsolation:
    """异常隔离测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = MetricsHook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_invalid_metric_name_no_exception(self):
        """无效指标名不抛异常"""
        result = self.hook.record(
            metric_name="INVALID-NAME!",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        # 应该 fallback 或 dropped，但不抛异常
        assert result["success"] is True
    
    def test_none_labels_no_exception(self):
        """None labels 不抛异常"""
        result = self.hook.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            labels=None,
            module="test"
        )
        
        assert result["success"] is True
    
    def test_extreme_value_no_exception(self):
        """极端值不抛异常"""
        result = self.hook.record(
            metric_name="test",
            metric_type="counter",
            value=float('inf'),
            module="test"
        )
        
        assert result["success"] is True


class TestTimeoutCircuitBreaker:
    """Timeout / Circuit Breaker 测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = MetricsHook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_timeout_guard_exists(self):
        """超时保护存在"""
        from runtime_metrics_aggregator.protection.timeout_guard import get_timeout_guard
        guard = get_timeout_guard()
        assert guard is not None
    
    def test_circuit_breaker_exists(self):
        """熔断器存在"""
        from runtime_metrics_aggregator.protection.circuit_breaker import get_circuit_breaker
        breaker = get_circuit_breaker()
        assert breaker is not None
    
    def test_circuit_breaker_can_execute(self):
        """熔断器可执行"""
        from runtime_metrics_aggregator.protection.circuit_breaker import get_circuit_breaker
        breaker = get_circuit_breaker()
        assert breaker.can_execute() is True


class TestRollback:
    """Rollback 测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = MetricsHook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_disable_works(self):
        """禁用有效"""
        self.hook.disable()
        
        assert self.hook.is_enabled() is False
    
    def test_fast_disable_works(self):
        """快速禁用有效"""
        result = self.hook.fast_disable("测试快速禁用")
        
        assert result["action"] == "fast_disable"
        assert result["current_state"] == "disabled"
        assert self.hook.is_enabled() is False
    
    def test_rollback_works(self):
        """回滚有效"""
        result = self.hook.rollback()
        
        assert "success" in result
        assert self.hook.is_enabled() is False


class TestPerformanceNoDegradation:
    """性能无退化测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = MetricsHook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_record_is_fast(self):
        """记录操作足够快（< 50ms）"""
        import time
        
        start = time.time()
        for _ in range(100):
            self.hook.record("perf_test", "counter", 1.0, module="perf")
        elapsed = time.time() - start
        
        # 100 次操作应 < 5 秒（平均每次 < 50ms）
        assert elapsed < 5.0, f"性能退化：100 次记录耗时 {elapsed}s"
    
    def test_query_is_reasonable(self):
        """查询操作合理"""
        import time
        
        # 先存储一些数据
        for i in range(50):
            self.hook.record(f"metric_{i}", "counter", 1.0, module="perf")
        
        start = time.time()
        result = self.hook.query()
        elapsed = time.time() - start
        
        # 查询应 < 1 秒
        assert elapsed < 1.0, f"查询耗时过长：{elapsed}s"
        assert result["total"] >= 50
