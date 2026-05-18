"""
Runtime Metrics Aggregator - Contract Tests

验证契约合规性
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapter.metrics_adapter import create_adapter, MetricsError


class TestInputSchemaCompliance:
    """输入 schema 合规测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_valid_input(self):
        """测试有效输入"""
        result = self.adapter.record_metric(
            metric_name="test_counter",
            metric_type="counter",
            value=1.0,
            labels={"source": "test"},
            timestamp=1710420000000,
            module="test_module"
        )
        
        assert result["success"] is True
        assert "metric_id" in result
    
    def test_minimal_input(self):
        """测试最小输入（只含必填字段）"""
        result = self.adapter.record_metric(
            metric_name="test_gauge",
            metric_type="gauge",
            value=42.0
        )
        
        assert result["success"] is True
    
    def test_missing_required_name(self):
        """测试缺少必填字段 metric_name"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="",
                metric_type="counter",
                value=1.0
            )
        assert exc_info.value.code == "INVALID_METRIC"
    
    def test_invalid_metric_type(self):
        """测试无效指标类型"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="test",
                metric_type="invalid_type",
                value=1.0
            )
        assert exc_info.value.code == "INVALID_METRIC"
    
    def test_invalid_metric_name_uppercase(self):
        """测试大写字母指标名"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="TestCounter",
                metric_type="counter",
                value=1.0
            )
        assert exc_info.value.code == "INVALID_METRIC"
    
    def test_invalid_metric_name_special_chars(self):
        """测试特殊字符指标名"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="test-counter",
                metric_type="counter",
                value=1.0
            )
        assert exc_info.value.code == "INVALID_METRIC"
    
    def test_invalid_label_key(self):
        """测试无效标签键"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="test",
                metric_type="counter",
                value=1.0,
                labels={"Invalid-Key": "value"}
            )
        assert exc_info.value.code == "INVALID_METRIC"
    
    def test_all_valid_metric_types(self):
        """测试所有有效指标类型"""
        types = ["counter", "gauge", "histogram", "timer"]
        for mtype in types:
            result = self.adapter.record_metric(
                metric_name=f"test_{mtype}",
                metric_type=mtype,
                value=1.0
            )
            assert result["success"] is True, f"Type {mtype} failed"


class TestOutputSchemaCompliance:
    """输出 schema 合规测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_output_fields(self):
        """测试输出字段完整"""
        result = self.adapter.record_metric(
            metric_name="test",
            metric_type="counter",
            value=1.0
        )
        
        # 必填字段
        assert "success" in result
        assert "metric_id" in result
        
        # 类型检查
        assert isinstance(result["success"], bool)
        assert isinstance(result["metric_id"], str)
    
    def test_error_output(self):
        """测试错误输出"""
        # 通过 fallback 获取错误结果
        result = self.adapter.record_with_fallback(
            metric_name="",
            metric_type="counter",
            value=1.0
        )
        
        # fallback 返回 success=true, metric_id=dropped
        assert result["success"] is True
        assert result["metric_id"] == "dropped"
    
    def test_query_output_schema(self):
        """测试查询输出 schema"""
        # 先记录一些数据
        self.adapter.record_metric("test", "counter", 1.0, module="mod1")
        self.adapter.record_metric("test", "counter", 2.0, module="mod2")
        
        result = self.adapter.query_metrics()
        
        # 必填字段
        assert "metrics" in result
        assert "total" in result
        assert isinstance(result["metrics"], list)
        assert isinstance(result["total"], int)
        
        # 指标字段
        if result["metrics"]:
            metric = result["metrics"][0]
            assert "id" in metric
            assert "name" in metric
            assert "type" in metric
            assert "value" in metric
            assert "labels" in metric
            assert "timestamp" in metric
            assert "module" in metric


class TestErrorSchemaCompliance:
    """错误 schema 合规测试"""
    
    def setup_method(self):
        self.adapter = create_adapter()
    
    def test_error_structure(self):
        """测试错误结构"""
        try:
            self.adapter.record_metric(
                metric_name="",
                metric_type="counter",
                value=1.0
            )
            pytest.fail("Should raise MetricsError")
        except MetricsError as e:
            assert hasattr(e, 'code')
            assert hasattr(e, 'message')
            assert hasattr(e, 'details')
            assert isinstance(e.code, str)
            assert isinstance(e.message, str)
            assert isinstance(e.details, dict)
    
    def test_error_code_invalid_metric(self):
        """测试 INVALID_METRIC 错误码"""
        with pytest.raises(MetricsError) as exc_info:
            self.adapter.record_metric(
                metric_name="",
                metric_type="counter",
                value=1.0
            )
        assert exc_info.value.code == "INVALID_METRIC"


class TestContractFrozen:
    """契约冻结测试"""
    
    def test_contract_file_exists(self):
        """测试 contract 文件存在"""
        contract_path = Path(__file__).parent.parent / "runtime_metrics_aggregator_contract.yaml"
        assert contract_path.exists()
    
    def test_contract_valid_yaml(self):
        """测试 contract 是有效 YAML"""
        import yaml
        contract_path = Path(__file__).parent.parent / "runtime_metrics_aggregator_contract.yaml"
        
        with open(contract_path, 'r') as f:
            data = yaml.safe_load(f)
        
        assert data is not None
        assert "metadata" in data
        assert "input" in data
        assert "output" in data
        assert "error" in data
        assert "fallback" in data
