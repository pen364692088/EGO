"""
Runtime Metrics Aggregator - Timeout Guard

超时保护机制
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import signal
import functools
from typing import Callable, Any, Optional
from contextlib import contextmanager


class TimeoutError(Exception):
    """超时异常"""
    pass


@contextmanager
def timeout_context(seconds: float):
    """
    超时上下文管理器
    
    Args:
        seconds: 超时秒数
        
    Raises:
        TimeoutError: 超时时抛出
    """
    def handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds}s")
    
    # 设置信号处理
    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def with_timeout(timeout_ms: int):
    """
    超时装饰器
    
    Args:
        timeout_ms: 超时毫秒数
        
    Returns:
        decorator
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with timeout_context(timeout_ms / 1000):
                    return func(*args, **kwargs)
            except TimeoutError:
                return {
                    "success": True,
                    "metric_id": "dropped",
                    "error": "timeout"
                }
        return wrapper
    return decorator


class TimeoutGuard:
    """超时守卫"""
    
    def __init__(self, default_timeout_ms: int = 50):
        self.default_timeout_ms = default_timeout_ms
    
    def execute(self, func: Callable, *args, timeout_ms: Optional[int] = None, **kwargs) -> Any:
        """
        执行函数，带超时保护
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            timeout_ms: 超时毫秒数（可选）
            **kwargs: 关键字参数
            
        Returns:
            函数返回值，或超时 fallback
        """
        timeout = timeout_ms or self.default_timeout_ms
        
        try:
            with timeout_context(timeout / 1000):
                return func(*args, **kwargs)
        except TimeoutError:
            return {
                "success": True,
                "metric_id": "dropped",
                "error": "timeout"
            }


# 全局实例
_default_guard: Optional[TimeoutGuard] = None


def get_timeout_guard() -> TimeoutGuard:
    """获取全局超时守卫"""
    global _default_guard
    if _default_guard is None:
        _default_guard = TimeoutGuard()
    return _default_guard
