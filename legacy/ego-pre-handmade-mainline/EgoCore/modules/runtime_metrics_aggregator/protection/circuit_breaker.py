"""
Runtime Metrics Aggregator - Circuit Breaker Protection

熔断保护机制
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 失败阈值
    success_threshold: int = 3          # 恢复阈值
    timeout_seconds: int = 60           # 熔断持续时间
    half_open_max_calls: int = 3        # 半开状态最大试探次数


class MetricsCircuitBreaker:
    """指标熔断器"""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查是否超过熔断时间
            if time.time() - self.last_failure_time >= self.config.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
        
        return True
    
    def record_success(self) -> None:
        """记录成功"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._reset()
        else:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
    
    def _reset(self) -> None:
        """重置熔断器"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
    
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }
    
    def force_open(self, reason: str) -> Dict[str, Any]:
        """强制熔断"""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        
        return {
            "action": "force_open",
            "reason": reason,
            "timestamp": int(time.time() * 1000)
        }
    
    def force_close(self) -> None:
        """强制关闭熔断"""
        self._reset()


# 全局实例
_default_breaker: Optional[MetricsCircuitBreaker] = None


def get_circuit_breaker() -> MetricsCircuitBreaker:
    """获取全局熔断器"""
    global _default_breaker
    if _default_breaker is None:
        _default_breaker = MetricsCircuitBreaker()
    return _default_breaker


def reset_circuit_breaker() -> None:
    """重置熔断器"""
    global _default_breaker
    _default_breaker = MetricsCircuitBreaker()
