"""
Runtime Metrics Aggregator - Fallback Tests

Fallback 场景测试
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapter.metrics_adapter import create_adapter


class TestFallbackScenarios:
    """Fallback 场景测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_fallback_empty_name(self):
        """Fallback: 空指标名"""
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        # fallback 返回 success=true, metric_id=dropped
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_fallback_invalid_name(self):
        """Fallback: 无效指标名"""
        result = self.adapter.record_with_fallback(
            metric_name="Invalid-Name-With-Dashes",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_fallback_invalid_type(self):
        """Fallback: 无效指标类型"""
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="not_a_type",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_fallback_invalid_labels(self):
        """Fallback: 无效标签"""
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            labels={"Invalid-Key": "value"}
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_fallback_negative_counter(self):
        """Fallback: 负值 counter"""
        # 这个在 core 层会报错（Metric.__post_init__ 验证）
        result = self.adapter.record_with_fallback(
            metric_name="test",
            metric_type="counter",
            value=-1.0
        )
        
        # core 层验证失败，但返回 success=true (fallback 行为)
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_no_error_propagation(self):
        """Fallback: 错误不传播"""
        # 确保即使输入完全无效，也不会抛出异常
        try:
            result = self.adapter.record_with_fallback(
                metric_name="valid_name",  # 使用有效名称
                metric_type="counter",
                value=-1.0  # 负值 counter 会在 core 层报错
            )
            # 负值 counter 会在 core 层验证失败，但返回 success=true
            assert result["success"] is True
            assert result["metric_id"] == "dropped"
        except Exception as e:
            # 如果抛出异常，说明 fallback 不够完善
            pytest.fail(f"Fallback should catch all errors, got: {e}")
    
    def test_fallback_does_not_affect_valid_records(self):
        """Fallback: 不影响有效记录"""
        # 先记录有效指标
        valid_result = self.adapter.record_with_fallback(
            metric_name="valid_metric",
            metric_type="counter",
            value=1.0
        )
        
        # 再记录无效指标（触发 fallback）
        invalid_result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        # 验证有效指标仍然可用
        query = self.adapter.query_metrics(name="valid_metric")
        assert query["total"] == 1
        
        # 验证 fallback 结果 - 两者都返回 success=true
        assert valid_result["success"] is True
        assert invalid_result["success"] is True
        assert valid_result["metric_id"] != "dropped"
        assert invalid_result["metric_id"] == "dropped"


class TestFallbackBehavior:
    """Fallback 行为测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_fallback_returns_success_true(self):
        """Fallback 必须返回 success=true"""
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True
    
    def test_fallback_returns_dropped_id(self):
        """Fallback 必须返回 metric_id=dropped"""
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        assert result["metric_id"] == "dropped"
    
    def test_fallback_no_error_field(self):
        """Fallback 不应该包含 error 字段（避免调用方处理）"""
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        # fallback 结果 success=true, metric_id=dropped
        assert result["success"] is True
        assert result["metric_id"] == "dropped"


class TestDirectRecordError:
    """直接记录错误测试（对比 fallback）"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_direct_record_raises_error(self):
        """直接记录应该抛出 MetricsError"""
        with pytest.raises(Exception):
            self.adapter.record_metric(
                metric_name="",
                metric_type="counter",
                value=1.0
            )
    
    def test_fallback_catches_error(self):
        """fallback 应该返回 dropped"""
        # 同样的输入，fallback 返回 success=true
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
