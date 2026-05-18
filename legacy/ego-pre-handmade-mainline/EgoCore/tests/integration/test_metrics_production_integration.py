"""
Runtime Metrics Aggregator - Production Integration Tests

正式接入后的主链集成测试
Phase: PRODUCTION_INTEGRATION
"""

import pytest
import sys
import os
from pathlib import Path

# 设置测试环境
os.environ["runtime_metrics_enabled"] = "false"
os.environ["runtime_metrics_shadow"] = "true"

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from system_core import get_metrics_hook, record_metric, initialize_metrics


class TestFlagOffConsistency:
    """Feature flag OFF 时一致性测试"""
    
    def setup_method(self):
        """每个测试前重置状态"""
        os.environ["runtime_metrics_enabled"] = "false"
        self.hook = get_metrics_hook()
        self.hook.initialize()
    
    def test_flag_off_returns_dropped(self):
        """Flag OFF 时返回 dropped"""
        result = record_metric(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_flag_off_zero_overhead(self):
        """Flag OFF 时零开销"""
        import time
        
        start = time.time()
        for _ in range(1000):
            record_metric(
                metric_name="test",
                metric_type="counter",
                value=1.0
            )
        elapsed_ms = (time.time() - start) * 1000
        
        # 1000 次调用应该在 10ms 内完成
        assert elapsed_ms < 10
    
    def test_flag_off_no_exception(self):
        """Flag OFF 时不抛出异常"""
        try:
            for _ in range(100):
                record_metric(
                    metric_name="test",
                    metric_type="counter",
                    value=1.0
                )
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")


class TestFlagOnNormalPath:
    """Flag ON 正常路径测试"""
    
    def setup_method(self):
        """启用指标收集"""
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_flag_on_records_metric(self):
        """Flag ON 时记录指标"""
        result = record_metric(
            metric_name="test_counter",
            metric_type="counter",
            value=1.0,
            labels={"env": "test"},
            module="test_module"
        )
        
        assert result["success"] is True
        assert result["metric_id"] != "dropped"
    
    def test_flag_on_query_returns_data(self):
        """Flag ON 时查询返回数据"""
        # 记录指标
        record_metric(
            metric_name="query_test",
            metric_type="gauge",
            value=42.0,
            module="test"
        )
        
        # 查询
        result = self.hook.query(name="query_test")
        
        assert result["total"] == 1
        assert result["metrics"][0]["name"] == "query_test"


class TestExceptionHandling:
    """异常处理测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_invalid_metric_name_fallback(self):
        """无效指标名 fallback"""
        result = record_metric(
            metric_name="",  # 无效
            metric_type="counter",
            value=1.0
        )
        
        # 应该返回 dropped，不抛出异常
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_invalid_metric_type_fallback(self):
        """无效指标类型 fallback"""
        result = record_metric(
            metric_name="test",
            metric_type="invalid_type",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_exception_does_not_propagate(self):
        """异常不传播到主链"""
        results = []
        
        # 混合有效和无效输入
        for i in range(10):
            if i % 2 == 0:
                result = record_metric(
                    metric_name=f"valid_{i}",
                    metric_type="counter",
                    value=1.0
                )
            else:
                result = record_metric(
                    metric_name="",  # 无效
                    metric_type="counter",
                    value=1.0
                )
            results.append(result)
        
        # 所有调用都应该返回 success=True
        for result in results:
            assert result["success"] is True


class TestProtectionMechanisms:
    """保护机制测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_fast_disable(self):
        """Fast disable 功能"""
        # 先启用
        assert self.hook.is_enabled() is True
        
        # 快速禁用
        result = self.hook.fast_disable("test_reason")
        
        assert result["action"] == "fast_disable"
        assert self.hook.is_enabled() is False
    
    def test_rollback(self):
        """Rollback 功能"""
        # 先记录一些数据
        record_metric(
            metric_name="before_rollback",
            metric_type="counter",
            value=1.0
        )
        
        # 回滚
        result = self.hook.rollback()
        
        assert result["success"] is True
        assert "disabled_feature_flag" in result["actions"]
        assert self.hook.is_enabled() is False


class TestMainlineConsistency:
    """主链一致性测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_metrics_do_not_block_mainline(self):
        """指标收集不阻塞主链"""
        import time
        
        start = time.time()
        
        # 记录多条指标
        for i in range(100):
            record_metric(
                metric_name=f"metric_{i}",
                metric_type="counter",
                value=float(i)
            )
        
        elapsed_ms = (time.time() - start) * 1000
        
        # 100 次调用应该在 100ms 内完成
        assert elapsed_ms < 100
    
    def test_user_output_unchanged(self):
        """用户输出不变"""
        # 无论指标收集成功还是失败，返回值格式一致
        result1 = record_metric(
            metric_name="valid",
            metric_type="counter",
            value=1.0
        )
        
        result2 = record_metric(
            metric_name="",  # 无效
            metric_type="counter",
            value=1.0
        )
        
        # 两者都返回 success=True
        assert result1["success"] is True
        assert result2["success"] is True


class TestShadowMode:
    """Shadow 模式测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        os.environ["runtime_metrics_shadow"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_shadow_mode_active(self):
        """Shadow 模式激活"""
        assert self.hook.is_shadow_mode() is True
    
    def test_shadow_records_metrics(self):
        """Shadow 模式记录指标"""
        result = record_metric(
            metric_name="shadow_test",
            metric_type="counter",
            value=1.0
        )
        
        # 成功记录
        assert result["success"] is True
        assert result["metric_id"] != "dropped"


class TestPerformance:
    """性能测试"""
    
    def setup_method(self):
        os.environ["runtime_metrics_enabled"] = "true"
        self.hook = get_metrics_hook()
        self.hook.initialize()
        self.hook.enable()
    
    def test_latency_acceptable(self):
        """延迟可接受"""
        import time
        
        latencies = []
        
        for _ in range(100):
            start = time.time()
            record_metric(
                metric_name="perf_test",
                metric_type="counter",
                value=1.0
            )
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # 平均延迟 < 10ms，最大延迟 < 50ms
        assert avg_latency < 10, f"Average latency {avg_latency}ms too high"
        assert max_latency < 50, f"Max latency {max_latency}ms too high"
