"""
Emotion Context Formatter - Integration Stub

主链接入桩，定义接入点但不实际接入
"""

from typing import Dict, Any, Optional, Callable
from adapter.context_adapter import create_adapter, EmotionFormatterAdapter


class IntegrationStub:
    """
    主链接入桩
    
    定义了如何接入 reply_pipeline，但当前不实际执行接入。
    用于验证 integration plan 的可行性。
    """
    
    # 接入点定义
    INTEGRATION_POINT = "reply_pipeline.pre_process"
    FEATURE_FLAG = "emotion_context_enabled"
    
    def __init__(self):
        self.adapter: Optional[EmotionFormatterAdapter] = None
        self.enabled = False
        self._original_handler: Optional[Callable] = None
    
    def initialize(self, timeout_ms: int = 100) -> None:
        """初始化适配器"""
        self.adapter = create_adapter(timeout_ms=timeout_ms)
    
    def enable(self) -> None:
        """启用模块（模拟）"""
        self.enabled = True
        print(f"[IntegrationStub] {self.FEATURE_FLAG} = True")
    
    def disable(self) -> None:
        """禁用模块（模拟）"""
        self.enabled = False
        print(f"[IntegrationStub] {self.FEATURE_FLAG} = False")
    
    def process(self, raw_context: str, emotion_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理入口（模拟 reply_pipeline 调用）
        
        Args:
            raw_context: 原始上下文
            emotion_state: 情绪状态
            
        Returns:
            格式化结果
        """
        if not self.enabled or not self.adapter:
            # 未启用时直接透传
            return {
                "formatted_context": raw_context,
                "emotion_applied": False,
                "meta": {
                    "emotion_label": "none",
                    "processing_time_ms": 0
                }
            }
        
        return self.adapter.format_with_fallback(raw_context, emotion_state)
    
    def get_integration_plan(self) -> Dict[str, Any]:
        """获取集成计划"""
        return {
            "integration_point": self.INTEGRATION_POINT,
            "feature_flag": self.FEATURE_FLAG,
            "rollout_strategy": "shadow_mode",
            "rollback_plan": f"关闭 feature flag {self.FEATURE_FLAG}",
            "steps": [
                "1. 在 reply_pipeline.pre_process 添加 hook",
                "2. 检查 feature flag emotion_context_enabled",
                "3. 如果启用，调用 EmotionFormatterAdapter.format_with_fallback",
                "4. 使用返回的 formatted_context 继续后续流程",
                "5. 记录 metrics 和 logs"
            ],
            "risks": [
                "延迟增加（默认 100ms 超时）",
                "情绪状态依赖外部系统"
            ],
            "mitigations": [
                "fallback 机制保证可用性",
                "可快速关闭 feature flag"
            ]
        }


def create_stub() -> IntegrationStub:
    """工厂函数"""
    return IntegrationStub()


# 模拟主链调用的示例
if __name__ == "__main__":
    stub = create_stub()
    stub.initialize()
    
    # 测试禁用状态
    print("=== 禁用状态 ===")
    result = stub.process("用户询问天气", {"valence": 0.5, "arousal": 0.3})
    print(f"Result: {result}")
    
    # 测试启用状态
    print("\n=== 启用状态 ===")
    stub.enable()
    result = stub.process("用户询问天气", {"valence": 0.5, "arousal": 0.3})
    print(f"Result: {result}")
    
    # 打印集成计划
    print("\n=== 集成计划 ===")
    plan = stub.get_integration_plan()
    for key, value in plan.items():
        print(f"{key}: {value}")
