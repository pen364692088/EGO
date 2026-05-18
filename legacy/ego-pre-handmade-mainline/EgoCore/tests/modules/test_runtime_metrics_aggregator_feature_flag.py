"""
Runtime Metrics Aggregator - Feature Flag Tests

Feature flag 和 disable 测试
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "modules" / "runtime_metrics_aggregator"))

from integration.stub import create_stub


class TestFeatureFlagDisabled:
    """Feature flag 关闭测试"""
    
    def setup_method(self):
        self.stub = create_stub()
        self.stub.initialize()
        # 默认 disabled
    
    def test_record_when_disabled(self):
        """关闭时记录返回 dropped"""
        result = self.stub.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_query_when_disabled(self):
        """关闭时查询返回空"""
        result = self.stub.query()
        
        assert result["metrics"] == []
        assert result["total"] == 0
    
    def test_no_side_effect_when_disabled(self):
        """关闭时不产生副作用"""
        # 记录一些数据（虽然会被丢弃）
        for i in range(100):
            self.stub.record(
                metric_name=f"metric_{i}",
                metric_type="counter",
                value=1.0,
                module="test"
            )
        
        # 查询应该仍然为空
        result = self.stub.query()
        assert result["total"] == 0


class TestFeatureFlagEnabled:
    """Feature flag 开启测试"""
    
    def setup_method(self):
        self.stub = create_stub()
        self.stub.initialize()
        self.stub.enable()
    
    def test_record_when_enabled(self):
        """开启时正常记录"""
        result = self.stub.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["success"] is True
        assert result["metric_id"] != "dropped"
    
    def test_query_when_enabled(self):
        """开启时正常查询"""
        self.stub.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        result = self.stub.query(name="test")
        
        assert result["total"] == 1
        assert result["metrics"][0]["name"] == "test"


class TestFastDisable:
    """快速禁用测试"""
    
    def setup_method(self):
        self.stub = create_stub()
        self.stub.initialize()
        self.stub.enable()
    
    def test_disable_stops_recording(self):
        """禁用后停止记录"""
        # 先记录一条
        self.stub.record(
            metric_name="before",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        # 禁用
        self.stub.disable()
        
        # 再记录一条
        self.stub.record(
            metric_name="after",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        # 查询应该只有 before
        result = self.stub.query()
        assert result["total"] == 1
        assert result["metrics"][0]["name"] == "before"
    
    def test_disable_is_immediate(self):
        """禁用立即生效"""
        self.stub.disable()
        
        result = self.stub.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["metric_id"] == "dropped"
    
    def test_re_enable(self):
        """重新启用"""
        self.stub.disable()
        self.stub.enable()
        
        result = self.stub.record(
            metric_name="test",
            metric_type="counter",
            value=1.0,
            module="test"
        )
        
        assert result["metric_id"] != "dropped"


class TestNoImpactOnMainChain:
    """不影响主链测试"""
    
    def setup_method(self):
        self.stub = create_stub()
        self.stub.initialize()
    
    def test_disabled_no_exception(self):
        """关闭时不抛出异常"""
        try:
            for i in range(100):
                self.stub.record(
                    metric_name=f"metric_{i}",
                    metric_type="counter",
                    value=1.0,
                    module="test"
                )
        except Exception as e:
            pytest.fail(f"Should not raise exception when disabled: {e}")
    
    def test_enabled_no_exception(self):
        """开启时不抛出异常"""
        self.stub.enable()
        
        try:
            for i in range(100):
                self.stub.record(
                    metric_name=f"metric_{i}",
                    metric_type="counter",
                    value=1.0,
                    module="test"
                )
        except Exception as e:
            pytest.fail(f"Should not raise exception when enabled: {e}")
    
    def test_fallback_no_exception(self):
        """fallback 不抛出异常"""
        self.stub.enable()
        
        try:
            # 无效输入
            self.stub.record(
                metric_name="",
                metric_type="counter",
                value=1.0,
                module="test"
            )
            
            # 正常输入
            self.stub.record(
                metric_name="valid",
                metric_type="counter",
                value=1.0,
                module="test"
            )
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")


class TestIntegrationPoint:
    """集成点测试"""
    
    def test_integration_point_defined(self):
        """集成点已定义"""
        stub = create_stub()
        
        assert stub.INTEGRATION_POINT == "system_core.metrics_hook"
    
    def test_feature_flag_defined(self):
        """Feature flag 已定义"""
        stub = create_stub()
        
        assert stub.FEATURE_FLAG == "runtime_metrics_enabled"
    
    def test_integration_plan_complete(self):
        """集成计划完整"""
        stub = create_stub()
        stub.initialize()
        
        plan = stub.get_integration_plan()
        
        assert "integration_point" in plan
        assert "feature_flag" in plan
        assert "rollback_plan" in plan
        assert "steps" in plan
        assert "risks" in plan
        assert "mitigations" in plan
