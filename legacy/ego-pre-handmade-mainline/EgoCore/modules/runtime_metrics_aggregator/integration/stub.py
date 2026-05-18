"""
Runtime Metrics Aggregator - Integration Stub

主链接入桩
"""

from typing import Dict, Any, Optional
from adapter.metrics_adapter import create_adapter, MetricsAdapter


class IntegrationStub:
    """
    主链接入桩
    
    定义了如何接入 system_core.metrics_hook
    """
    
    INTEGRATION_POINT = "system_core.metrics_hook"
    FEATURE_FLAG = "runtime_metrics_enabled"
    
    def __init__(self):
        self.adapter: Optional[MetricsAdapter] = None
        self.enabled = False
    
    def initialize(self, max_buffer_size: int = 10000) -> None:
        """初始化"""
        self.adapter = create_adapter(max_buffer_size=max_buffer_size)
    
    def enable(self) -> None:
        """启用"""
        self.enabled = True
        print(f"[IntegrationStub] {self.FEATURE_FLAG} = True")
    
    def disable(self) -> None:
        """禁用"""
        self.enabled = False
        print(f"[IntegrationStub] {self.FEATURE_FLAG} = False")
    
    def record(
        self,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
        module: str = "unknown"
    ) -> Dict[str, Any]:
        """记录指标（模拟主链调用）"""
        if not self.enabled or not self.adapter:
            # 未启用时返回 dropped
            return {"success": True, "metric_id": "dropped"}
        
        result = self.adapter.record_with_fallback(
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            labels=labels,
            timestamp=timestamp,
            module=module
        )
        
        # 如果禁用后返回 dropped，不存储
        if result["metric_id"] == "dropped":
            return result
        
        return result
    
    def query(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        since_ms: Optional[int] = None,
        module: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询指标"""
        # 查询不依赖 enabled 状态，只要有 adapter 就查询已存储数据
        if not self.adapter:
            return {"metrics": [], "total": 0}
        
        return self.adapter.query_metrics(
            name=name,
            labels=labels,
            since_ms=since_ms,
            module=module
        )
    
    def get_integration_plan(self) -> Dict[str, Any]:
        """获取集成计划"""
        return {
            "integration_point": self.INTEGRATION_POINT,
            "feature_flag": self.FEATURE_FLAG,
            "rollout_strategy": "gradual",
            "rollback_plan": f"关闭 feature flag {self.FEATURE_FLAG}",
            "steps": [
                "1. 在 system_core.metrics_hook 注册回调",
                "2. 检查 feature flag runtime_metrics_enabled",
                "3. 如果启用，调用 MetricsAdapter.record_with_fallback",
                "4. 各模块通过统一接口上报指标",
                "5. 支持查询接口获取聚合数据"
            ],
            "risks": [
                "内存使用增加（环形缓冲区）",
                "指标上报延迟"
            ],
            "mitigations": [
                "缓冲区大小限制",
                "fallback 机制",
                "可快速关闭"
            ]
        }


def create_stub() -> IntegrationStub:
    """工厂函数"""
    return IntegrationStub()


if __name__ == "__main__":
    stub = create_stub()
    stub.initialize()
    
    print("=== 禁用状态 ===")
    result = stub.record("test_counter", "counter", 1, module="test")
    print(f"Result: {result}")
    
    print("\n=== 启用状态 ===")
    stub.enable()
    result = stub.record("test_counter", "counter", 1, {"label": "value"}, module="test")
    print(f"Result: {result}")
    
    query_result = stub.query(name="test_counter")
    print(f"Query: {query_result}")
    
    print("\n=== 集成计划 ===")
    plan = stub.get_integration_plan()
    for key, value in plan.items():
        print(f"{key}: {value}")
