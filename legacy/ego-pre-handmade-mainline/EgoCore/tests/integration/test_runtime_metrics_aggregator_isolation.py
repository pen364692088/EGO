"""
Runtime Metrics Aggregator - Isolation Tests

异常隔离测试
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "modules" / "runtime_metrics_aggregator"))

from adapter.metrics_adapter import create_adapter
from protection.circuit_breaker import MetricsCircuitBreaker, CircuitState


class TestExceptionIsolation:
    """异常隔离测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_adapter_exception_isolation(self):
        """Adapter 异常隔离"""
        # 无效输入应该被捕获，不抛出
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_core_exception_isolation(self):
        """Core 异常隔离"""
        # 负值 counter 会在 core 层报错
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="counter",
            value=-1.0
        )
        
        # 应该被 fallback 捕获
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_no_exception_propagation(self):
        """无异常传播"""
        # 各种无效输入
        invalid_inputs = [
            {"metric_name": "", "metric_type": "counter", "value": 1.0},
            {"metric_name": "test", "metric_type": "invalid", "value": 1.0},
            {"metric_name": "test", "metric_type": "counter", "value": -1.0},
        ]
        
        for inp in invalid_inputs:
            try:
                result = self.adapter.record_with_fallback(**inp)
                assert result["success"] is True
            except Exception as e:
                pytest.fail(f"Should not propagate exception: {e}")


class TestCircuitBreakerIsolation:
    """熔断器隔离测试"""
    
    def setup_method(self):
        self.breaker = MetricsCircuitBreaker()
    
    def test_circuit_breaker_opens_on_failures(self):
        """熔断器在失败时打开"""
        # 记录多次失败
        for _ in range(5):
            self.breaker.record_failure()
        
        # 熔断器应该打开
        assert self.breaker.state == CircuitState.OPEN
        assert not self.breaker.can_execute()
    
    def test_circuit_breaker_closes_on_success(self):
        """熔断器在成功时关闭"""
        # 使用短超时配置
        from protection.circuit_breaker import CircuitBreakerConfig
        self.breaker = MetricsCircuitBreaker(CircuitBreakerConfig(timeout_seconds=0))
        
        # 先打开熔断器
        for _ in range(5):
            self.breaker.record_failure()
        
        assert self.breaker.state == CircuitState.OPEN
        
        # 立即检查（超时时间为0）
        # 半开状态，允许试探
        assert self.breaker.can_execute()
        
        # 记录成功
        for _ in range(3):
            self.breaker.record_success()
        
        # 应该关闭
        assert self.breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_isolates_failures(self):
        """熔断器隔离失败"""
        # 打开熔断器
        for _ in range(5):
            self.breaker.record_failure()
        
        # 应该阻止执行
        assert not self.breaker.can_execute()


class TestTimeoutIsolation:
    """超时隔离测试"""
    
    def test_timeout_returns_fallback(self):
        """超时返回 fallback"""
        from protection.timeout_guard import TimeoutGuard
        
        guard = TimeoutGuard(default_timeout_ms=1)  # 1ms 超时
        
        def slow_function():
            import time
            time.sleep(0.1)  # 100ms，会超时
            return {"success": True, "metric_id": "test"}
        
        result = guard.execute(slow_function)
        
        # 应该返回 fallback
        assert result["metric_id"] == "dropped"
        assert result.get("error") == "timeout"


class TestMemoryIsolation:
    """内存隔离测试"""
    
    def test_buffer_size_limit(self):
        """缓冲区大小限制"""
        # 创建小缓冲区
        small_adapter = create_adapter(max_buffer_size=10)
        
        # 记录超过容量的指标
        for i in range(20):
            small_adapter.record_with_fallback(
                metric_name=f"metric_{i}",
                metric_type="counter",
                value=float(i)
            )
        
        # 查询
        query = small_adapter.query_metrics()
        
        # 应该只保留最近的 10 个
        assert query["total"] == 10
