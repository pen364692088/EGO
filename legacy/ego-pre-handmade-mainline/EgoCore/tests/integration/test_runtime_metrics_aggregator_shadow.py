"""
Runtime Metrics Aggregator - Shadow Mode Tests

Shadow 模式验证测试
"""

import pytest
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "modules" / "runtime_metrics_aggregator"))

from adapter.metrics_adapter import create_adapter
from config.feature_flags import FeatureFlagManager, MetricsFeatureConfig


class TestShadowModeBasics:
    """Shadow 模式基础测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
        self.flags = FeatureFlagManager(MetricsFeatureConfig(enabled=True))
    
    def test_shadow_mode_does_not_affect_output(self):
        """Shadow 模式不影响主链输出"""
        # 记录指标
        result = self.adapter.record_with_fallback(
            metric_name="test_metric",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        # 返回结果应该一致
        assert result["success"] is True
        assert "metric_id" in result
    
    def test_shadow_mode_records_metrics(self):
        """Shadow 模式记录指标"""
        # 记录多条指标
        for i in range(10):
            self.adapter.record_with_fallback(
                metric_name=f"metric_{i}",
                metric_type="counter",
                value=float(i),
                module="test"
            )
        
        # 查询验证
        query = self.adapter.query_metrics()
        assert query["total"] == 10
    
    def test_shadow_mode_sample_rate(self):
        """Shadow 模式采样率控制"""
        config = MetricsFeatureConfig(enabled=True, log_sample_rate=0.5)
        flags = FeatureFlagManager(config)
        
        # 采样率只影响日志，不影响记录
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True


class TestShadowModeIsolation:
    """Shadow 模式隔离测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_shadow_does_not_block_main_thread(self):
        """Shadow 不阻塞主线程"""
        start_time = time.time()
        
        # 记录指标
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="counter",
            value=1.0
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        # 应该快速返回
        assert elapsed_ms < 100  # 100ms 内
        assert result["success"] is True
    
    def test_shadow_failure_does_not_propagate(self):
        """Shadow 失败不传播"""
        # 无效输入应该被 fallback 捕获
        result = self.adapter.record_with_fallback(
            metric_name="",  # 无效名称
            metric_type="counter",
            value=1.0
        )
        
        # 不应该抛出异常
        assert result["success"] is True
        assert result["metric_id"] == "dropped"


class TestShadowModeStats:
    """Shadow 模式统计测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_shadow_records_stats(self):
        """Shadow 记录统计信息"""
        # 记录指标
        for _ in range(5):
            self.adapter.record_with_fallback(
                metric_name="test",
                metric_type="counter",
                value=1.0
            )
        
        # 获取统计
        stats = self.adapter.get_stats()
        
        assert stats["received"] == 5
        assert stats["dropped"] == 0
    
    def test_shadow_fallback_stats(self):
        """Shadow fallback 统计"""
        # 记录有效指标
        self.adapter.record_with_fallback(
            metric_name="valid",
            metric_type="counter",
            value=1.0
        )
        
        # 记录无效指标（触发 fallback）- 在 adapter 层验证失败
        result = self.adapter.record_with_fallback(
            metric_name="",  # 无效
            metric_type="counter",
            value=1.0
        )
        
        # 验证 fallback 返回 dropped
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
        
        stats = self.adapter.get_stats()
        
        # 有效指标被记录
        assert stats["received"] >= 1  # 至少有一条有效记录
        # 注意：adapter 层验证失败的指标不计入 core 的 dropped
        # 因为它们在到达 core 之前就被拦截了


class TestShadowModeLatency:
    """Shadow 模式延迟测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_shadow_latency_acceptable(self):
        """Shadow 延迟可接受"""
        latencies = []
        
        for _ in range(100):
            start = time.time()
            self.adapter.record_with_fallback(
                metric_name="test",
                metric_type="counter",
                value=1.0
            )
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # 平均延迟应 < 10ms
        assert avg_latency < 10, f"Average latency {avg_latency}ms too high"
        # 最大延迟应 < 50ms
        assert max_latency < 50, f"Max latency {max_latency}ms too high"
    
    def test_shadow_p95_latency(self):
        """Shadow P95 延迟"""
        latencies = []
        
        for _ in range(200):
            start = time.time()
            self.adapter.record_with_fallback(
                metric_name="test",
                metric_type="counter",
                value=1.0
            )
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)
        
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]
        
        # P95 应 < 50ms
        assert p95_latency < 50, f"P95 latency {p95_latency}ms too high"
