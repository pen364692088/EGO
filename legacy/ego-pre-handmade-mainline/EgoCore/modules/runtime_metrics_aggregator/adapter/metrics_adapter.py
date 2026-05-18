"""
Runtime Metrics Aggregator - Adapter Module

负责外部上下文转换和依赖注入。
"""

from typing import Dict, Any, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.aggregator import (
    RuntimeMetricsAggregator,
    MetricType,
    RecordResult,
    QueryResult,
    create_aggregator
)


class MetricsError(Exception):
    """指标错误"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def parse_metric_type(type_str: str) -> MetricType:
    """
    解析指标类型
    
    Args:
        type_str: 类型字符串
        
    Returns:
        MetricType: 指标类型枚举
        
    Raises:
        MetricsError: 无效类型
    """
    try:
        return MetricType(type_str.lower())
    except ValueError:
        raise MetricsError(
            code="INVALID_METRIC",
            message=f"Invalid metric type: {type_str}",
            details={"valid_types": [t.value for t in MetricType]}
        )


def validate_metric_name(name: str) -> None:
    """
    验证指标名称
    
    Args:
        name: 指标名称
        
    Raises:
        MetricsError: 无效名称
    """
    if not name:
        raise MetricsError(
            code="INVALID_METRIC",
            message="Metric name cannot be empty"
        )
    
    # 只允许小写字母、数字、下划线
    if not all(c.islower() or c.isdigit() or c == '_' for c in name):
        raise MetricsError(
            code="INVALID_METRIC",
            message=f"Invalid metric name: {name}. Only [a-z0-9_] allowed",
            details={"name": name}
        )


def validate_labels(labels: Optional[Dict[str, str]]) -> None:
    """
    验证标签
    
    Args:
        labels: 标签字典
        
    Raises:
        MetricsError: 无效标签
    """
    if labels is None:
        return
    
    for key, value in labels.items():
        if not all(c.islower() or c.isdigit() or c == '_' for c in key):
            raise MetricsError(
                code="INVALID_METRIC",
                message=f"Invalid label key: {key}. Only [a-z0-9_] allowed",
                details={"key": key}
            )


def record_result_to_dict(result: RecordResult) -> Dict[str, Any]:
    """将记录结果转换为字典"""
    output = {
        "success": result.success,
        "metric_id": result.metric_id
    }
    if result.error:
        output["error"] = result.error
    return output


def query_result_to_dict(result: QueryResult) -> Dict[str, Any]:
    """将查询结果转换为字典"""
    return {
        "metrics": result.metrics,
        "total": result.total
    }


class MetricsAdapter:
    """指标适配器"""
    
    def __init__(self, max_buffer_size: int = 10000):
        self.aggregator = create_aggregator(max_buffer_size=max_buffer_size)
    
    def record_metric(
        self,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
        module: str = "unknown"
    ) -> Dict[str, Any]:
        """
        记录指标（适配器入口）
        
        Args:
            metric_name: 指标名称
            metric_type: 指标类型字符串
            value: 指标值
            labels: 标签
            timestamp: 时间戳
            module: 来源模块
            
        Returns:
            Dict: 记录结果
            
        Raises:
            MetricsError: 验证失败
        """
        # 验证
        validate_metric_name(metric_name)
        validate_labels(labels)
        mtype = parse_metric_type(metric_type)
        
        # 调用 core
        result = self.aggregator.record(
            name=metric_name,
            metric_type=mtype,
            value=value,
            labels=labels,
            timestamp=timestamp,
            module=module
        )
        
        return record_result_to_dict(result)
    
    def record_with_fallback(
        self,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
        module: str = "unknown"
    ) -> Dict[str, Any]:
        """
        带 fallback 的记录
        
        任何错误都返回 success=true, metric_id="dropped"
        """
        try:
            return self.record_metric(
                metric_name=metric_name,
                metric_type=metric_type,
                value=value,
                labels=labels,
                timestamp=timestamp,
                module=module
            )
        except Exception:
            # Fallback: 丢弃但返回成功（捕获所有异常）
            return {
                "success": True,
                "metric_id": "dropped"
            }
    
    def query_metrics(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        since_ms: Optional[int] = None,
        module: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询指标
        
        Args:
            name: 指标名过滤
            labels: 标签过滤
            since_ms: 时间窗口
            module: 模块过滤
            
        Returns:
            Dict: 查询结果
        """
        result = self.aggregator.query(
            name=name,
            labels=labels,
            since_ms=since_ms,
            module=module
        )
        return query_result_to_dict(result)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.aggregator.get_stats()


def create_adapter(max_buffer_size: int = 10000) -> MetricsAdapter:
    """工厂函数"""
    return MetricsAdapter(max_buffer_size=max_buffer_size)
