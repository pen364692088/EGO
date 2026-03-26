"""
EgoCore System Core - Metrics Hook

主链指标收集钩子点。
将 runtime_metrics_aggregator 正式接入 EgoCore 主链。

Phase: PRODUCTION_INTEGRATION
Status: SHADOW_MODE (默认)
Feature Flag: runtime_metrics_enabled
"""

import os
from typing import Dict, Any, Optional

from runtime_metrics_aggregator.adapter.metrics_adapter import create_adapter, MetricsAdapter
from runtime_metrics_aggregator.config.feature_flags import FeatureFlagManager, MetricsFeatureConfig
from runtime_metrics_aggregator.protection.circuit_breaker import get_circuit_breaker
from runtime_metrics_aggregator.protection.timeout_guard import get_timeout_guard
from runtime_metrics_aggregator.protection.rollback import get_rollback_manager


class MetricsHook:
    """
    主链指标收集钩子
    
    接入点: system_core.metrics_hook
    调用方: session_manager, subagent_orchestrator, reply_pipeline, system_core
    
    保护机制:
    - Feature Flag: runtime_metrics_enabled (默认 OFF)
    - Fast Disable: 一键禁用
    - Rollback: 快速回滚
    - Timeout: 50ms 超时保护
    - Circuit Breaker: 熔断保护
    - 异常隔离: fallback 不传播异常
    """
    
    FEATURE_FLAG = "runtime_metrics_enabled"
    DEFAULT_TIMEOUT_MS = 50
    
    def __init__(self):
        self._adapter: Optional[MetricsAdapter] = None
        self._flags: Optional[FeatureFlagManager] = None
        self._initialized = False
        self._shadow_mode = True  # 默认 shadow 模式
    
    def initialize(self, max_buffer_size: int = 10000) -> None:
        """
        初始化指标钩子
        
        Args:
            max_buffer_size: 环形缓冲区大小
        """
        if self._initialized:
            return
        
        # 从环境变量读取配置
        enabled = os.environ.get(self.FEATURE_FLAG, "false").lower() == "true"
        shadow = os.environ.get("runtime_metrics_shadow", "true").lower() == "true"
        
        config = MetricsFeatureConfig(
            enabled=enabled,
            buffer_size=max_buffer_size,
            timeout_ms=self.DEFAULT_TIMEOUT_MS
        )
        
        self._flags = FeatureFlagManager(config)
        self._adapter = create_adapter(max_buffer_size=max_buffer_size)
        self._shadow_mode = shadow
        self._initialized = True
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        if not self._initialized:
            return False
        return self._flags.is_enabled() if self._flags else False
    
    def is_shadow_mode(self) -> bool:
        """检查是否在 shadow 模式"""
        return self._shadow_mode
    
    def record(
        self,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
        module: str = "unknown"
    ) -> Dict[str, Any]:
        """
        记录指标（主链接入点）
        
        Args:
            metric_name: 指标名称
            metric_type: 指标类型 (counter/gauge/histogram/timer)
            value: 指标值
            labels: 标签
            timestamp: 时间戳（毫秒）
            module: 来源模块
            
        Returns:
            Dict: 记录结果
            
        Flag 语义:
            - shadow=true, enabled=false: 旁路记录，返回 dropped（不影响主链）
            - shadow=true, enabled=true: 正常记录并返回结果
            - shadow=false, enabled=false: 不记录，返回 dropped
            - shadow=false, enabled=true: 正常记录并返回结果
            
        Note:
            - 未初始化时返回 dropped，不影响主链
            - 异常时返回 dropped，不传播异常
            - 超时保护，不阻塞主链
        """
        # 未初始化时直接返回
        if not self._initialized or not self._adapter:
            return {"success": True, "metric_id": "dropped", "reason": "not_initialized"}
        
        # ========================================
        # enabled=true 时正常模式
        # ========================================
        if self._flags.is_enabled():
            # Circuit breaker 检查
            breaker = get_circuit_breaker()
            if not breaker.can_execute():
                return {"success": True, "metric_id": "dropped", "reason": "circuit_breaker_open"}
            
            # 超时保护执行
            guard = get_timeout_guard()
            
            def do_record():
                result = self._adapter.record_with_fallback(
                    metric_name=metric_name,
                    metric_type=metric_type,
                    value=value,
                    labels=labels,
                    timestamp=timestamp,
                    module=module
                )
                
                # 记录成功/失败到 circuit breaker
                if result["metric_id"] != "dropped":
                    breaker.record_success()
                else:
                    breaker.record_failure()
                
                return result
            
            try:
                return guard.execute(do_record, timeout_ms=self.DEFAULT_TIMEOUT_MS)
            except Exception:
                breaker.record_failure()
                return {"success": True, "metric_id": "dropped"}
        
        # ========================================
        # Shadow 模式：enabled=false 且 shadow=true
        # 旁路记录样本，返回 dropped（不影响主链）
        # ========================================
        if self._shadow_mode:
            try:
                breaker = get_circuit_breaker()
                if breaker.can_execute():
                    self._adapter.record_with_fallback(
                        metric_name=metric_name,
                        metric_type=metric_type,
                        value=value,
                        labels=labels,
                        timestamp=timestamp,
                        module=module
                    )
            except Exception:
                pass  # 异常隔离
            
            return {"success": True, "metric_id": "dropped", "shadow": True}
        
        # ========================================
        # 完全禁用：enabled=false 且 shadow=false
        # ========================================
        return {"success": True, "metric_id": "dropped", "reason": "disabled"}
    
    def query(
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
            since_ms: 时间窗口（毫秒）
            module: 模块过滤
            
        Returns:
            Dict: 查询结果
            
        Note:
            - Shadow 模式下可以查询已收集的样本
            - 正常模式下需要 enabled=true 才能查询
        """
        if not self._initialized or not self._adapter:
            return {"metrics": [], "total": 0}
        
        # Shadow 模式：允许查询已收集的样本
        if self._shadow_mode:
            return self._adapter.query_metrics(
                name=name,
                labels=labels,
                since_ms=since_ms,
                module=module
            )
        
        # 正常模式：需要 enabled=true
        if not self._flags.is_enabled():
            return {"metrics": [], "total": 0}
        
        return self._adapter.query_metrics(
            name=name,
            labels=labels,
            since_ms=since_ms,
            module=module
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized or not self._adapter:
            return {"initialized": False}
        
        stats = self._adapter.get_stats()
        breaker_state = get_circuit_breaker().get_state()
        
        return {
            "initialized": True,
            "enabled": self._flags.is_enabled() if self._flags else False,
            "shadow_mode": self._shadow_mode,
            "adapter_stats": stats,
            "circuit_breaker": breaker_state
        }
    
    def enable(self) -> None:
        """启用指标收集"""
        if self._flags:
            self._flags.enable()
    
    def disable(self) -> None:
        """禁用指标收集（Fast Disable）"""
        if self._flags:
            self._flags.disable()
    
    def fast_disable(self, reason: str) -> Dict[str, Any]:
        """
        快速禁用
        
        Args:
            reason: 禁用原因
            
        Returns:
            Dict: 操作结果
        """
        if self._flags:
            return self._flags.fast_disable(reason)
        return {"success": False, "error": "Not initialized"}
    
    def rollback(self) -> Dict[str, Any]:
        """
        回滚到未启用状态
        
        Returns:
            Dict: 回滚结果
        """
        # 1. 禁用 feature flag
        self.disable()
        
        # 2. 重置 circuit breaker
        from runtime_metrics_aggregator.protection.circuit_breaker import reset_circuit_breaker
        reset_circuit_breaker()
        
        # 3. 记录回滚
        manager = get_rollback_manager()
        result = manager.quick_rollback()
        
        return result


# 全局实例
_metrics_hook: Optional[MetricsHook] = None


def get_metrics_hook() -> MetricsHook:
    """获取全局指标钩子"""
    global _metrics_hook
    if _metrics_hook is None:
        _metrics_hook = MetricsHook()
    return _metrics_hook


def record_metric(
    metric_name: str,
    metric_type: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
    timestamp: Optional[int] = None,
    module: str = "unknown"
) -> Dict[str, Any]:
    """
    便捷函数：记录指标
    
    使用示例:
        from system_core import record_metric
        
        record_metric(
            metric_name="session_created_total",
            metric_type="counter",
            value=1.0,
            labels={"source": "telegram"},
            module="session_manager"
        )
    """
    hook = get_metrics_hook()
    if not hook._initialized:
        hook.initialize()
    return hook.record(
        metric_name=metric_name,
        metric_type=metric_type,
        value=value,
        labels=labels,
        timestamp=timestamp,
        module=module
    )


def initialize_metrics(max_buffer_size: int = 10000) -> None:
    """初始化指标系统"""
    hook = get_metrics_hook()
    hook.initialize(max_buffer_size=max_buffer_size)
