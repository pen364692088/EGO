"""
Runtime Metrics Aggregator - Feature Flags Configuration

主链保护配置
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class MetricsFeatureConfig:
    """指标功能配置"""
    
    # 主开关
    enabled: bool = False
    
    # 性能配置
    buffer_size: int = 10000
    timeout_ms: int = 50
    max_timeout_ms: int = 200
    
    # 日志配置
    log_sample_rate: float = 0.1
    log_level: str = "info"
    
    # 模块级开关
    module_enabled: Dict[str, bool] = field(default_factory=lambda: {
        "session_manager": True,
        "subagent_orchestrator": True,
        "reply_pipeline": False,  # 高频，谨慎开启
        "system_core": True,
    })
    
    # 保护阈值
    max_memory_mb: int = 50
    error_threshold_percent: float = 5.0
    timeout_threshold_percent: float = 1.0
    
    # Fast disable 触发条件
    auto_disable_on_error_rate: bool = True
    auto_disable_on_timeout_rate: bool = True
    auto_disable_on_memory: bool = True


class FeatureFlagManager:
    """Feature Flag 管理器"""
    
    def __init__(self, config: Optional[MetricsFeatureConfig] = None):
        self.config = config or MetricsFeatureConfig()
        self._overrides: Dict[str, Any] = {}
    
    def is_enabled(self, module: Optional[str] = None) -> bool:
        """
        检查是否启用
        
        Args:
            module: 模块名（可选）
            
        Returns:
            bool: 是否启用
        """
        # 主开关
        if not self.config.enabled:
            return False
        
        # 模块级开关
        if module is not None:
            return self.config.module_enabled.get(module, False)
        
        return True
    
    def enable(self, module: Optional[str] = None) -> None:
        """启用"""
        if module is None:
            self.config.enabled = True
        else:
            self.config.module_enabled[module] = True
    
    def disable(self, module: Optional[str] = None) -> None:
        """禁用（Fast Disable）"""
        if module is None:
            self.config.enabled = False
        else:
            self.config.module_enabled[module] = False
    
    def fast_disable(self, reason: str) -> Dict[str, Any]:
        """
        快速禁用
        
        Args:
            reason: 禁用原因
            
        Returns:
            Dict: 操作结果
        """
        self.disable()
        
        return {
            "action": "fast_disable",
            "reason": reason,
            "timestamp": self._get_timestamp(),
            "previous_state": "enabled",
            "current_state": "disabled"
        }
    
    def get_config(self) -> MetricsFeatureConfig:
        """获取配置"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳"""
        import time
        return int(time.time() * 1000)
    
    def should_auto_disable(self, error_rate: float, timeout_rate: float, memory_mb: float) -> Optional[str]:
        """
        检查是否应该自动禁用
        
        Returns:
            str: 禁用原因，或 None
        """
        if self.config.auto_disable_on_error_rate and error_rate > self.config.error_threshold_percent:
            return f"error_rate_exceeded: {error_rate:.2f}% > {self.config.error_threshold_percent}%"
        
        if self.config.auto_disable_on_timeout_rate and timeout_rate > self.config.timeout_threshold_percent:
            return f"timeout_rate_exceeded: {timeout_rate:.2f}% > {self.config.timeout_threshold_percent}%"
        
        if self.config.auto_disable_on_memory and memory_mb > self.config.max_memory_mb:
            return f"memory_exceeded: {memory_mb:.2f}MB > {self.config.max_memory_mb}MB"
        
        return None


# 全局实例
_default_manager: Optional[FeatureFlagManager] = None


def get_feature_flags() -> FeatureFlagManager:
    """获取全局 feature flag 管理器"""
    global _default_manager
    if _default_manager is None:
        _default_manager = FeatureFlagManager()
    return _default_manager


def reset_feature_flags() -> None:
    """重置 feature flag（用于 rollback）"""
    global _default_manager
    _default_manager = FeatureFlagManager()
