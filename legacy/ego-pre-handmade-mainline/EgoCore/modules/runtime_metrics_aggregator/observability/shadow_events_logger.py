"""
Runtime Metrics Aggregator - Shadow Events Logger

持久化 shadow 事件日志（JSONL append-only）
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


class ShadowEventsLogger:
    """
    Shadow 事件日志记录器
    
    写入 JSONL append-only 事件流，供 daily check 读取
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            # 默认存储位置
            self.log_dir = Path(__file__).parent.parent.parent / "data" / "shadow_metrics"
        else:
            self.log_dir = Path(log_dir)
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file = None
        self._current_date = None
    
    def _get_log_file(self) -> Path:
        """获取当天的日志文件"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"shadow_events_{today}.jsonl"
        return self._current_file
    
    def log_event(
        self,
        source: str,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        module: str = "unknown",
        shadow_enabled: bool = True,
        metrics_enabled: bool = False,
        result: str = "dropped",
        latency_ms: float = 0.0,
        error_class: Optional[str] = None,
        user_visible_impact: bool = False,
    ) -> Dict[str, Any]:
        """
        记录 shadow 事件
        
        Args:
            source: 来源（telegram_bot, command_router 等）
            metric_name: 指标名
            metric_type: 指标类型
            value: 指标值
            labels: 标签
            module: 模块名
            shadow_enabled: Shadow 模式是否开启
            metrics_enabled: Feature flag 是否开启
            result: 结果（stored, dropped）
            latency_ms: 延迟毫秒
            error_class: 错误类型（如果有）
            user_visible_impact: 是否影响用户可见输出
            
        Returns:
            Dict: 事件记录
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "request_id": str(uuid.uuid4())[:8],
            "pid": os.getpid(),
            "source": source,
            "metric": {
                "name": metric_name,
                "type": metric_type,
                "value": value,
                "labels": labels or {},
                "module": module,
            },
            "flags": {
                "shadow_enabled": shadow_enabled,
                "metrics_enabled": metrics_enabled,
            },
            "result": result,
            "latency_ms": round(latency_ms, 3),
            "error_class": error_class,
            "user_visible_impact": user_visible_impact,
        }
        
        # 追加写入 JSONL
        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        
        return event
    
    def get_events_for_date(self, date_str: str) -> list:
        """
        读取指定日期的所有事件
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            list: 事件列表
        """
        log_file = self.log_dir / f"shadow_events_{date_str}.jsonl"
        if not log_file.exists():
            return []
        
        events = []
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        
        return events
    
    def get_stats_for_date(self, date_str: str) -> Dict[str, Any]:
        """
        获取指定日期的统计
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            Dict: 统计结果
        """
        events = self.get_events_for_date(date_str)
        
        if not events:
            return {
                "date": date_str,
                "total_events": 0,
                "total_calls": 0,
                "stored_count": 0,
                "dropped_count": 0,
                "error_count": 0,
                "avg_latency_ms": 0.0,
                "user_impact_count": 0,
                "sources": {},
                "modules": {},
            }
        
        total = len(events)
        stored = sum(1 for e in events if e.get("result") == "stored")
        dropped = sum(1 for e in events if e.get("result") == "dropped")
        errors = sum(1 for e in events if e.get("error_class"))
        user_impact = sum(1 for e in events if e.get("user_visible_impact"))
        
        latencies = [e.get("latency_ms", 0) for e in events]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        # 按来源统计
        sources = {}
        for e in events:
            src = e.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        # 按模块统计
        modules = {}
        for e in events:
            mod = e.get("metric", {}).get("module", "unknown")
            modules[mod] = modules.get(mod, 0) + 1
        
        return {
            "date": date_str,
            "total_events": total,
            "total_calls": total,
            "stored_count": stored,
            "dropped_count": dropped,
            "error_count": errors,
            "avg_latency_ms": round(avg_latency, 3),
            "user_impact_count": user_impact,
            "success_rate": round(stored / total * 100, 2) if total > 0 else 0,
            "dropped_rate": round(dropped / total * 100, 2) if total > 0 else 0,
            "sources": sources,
            "modules": modules,
        }


# 全局实例
_shadow_logger: Optional[ShadowEventsLogger] = None


def get_shadow_logger() -> ShadowEventsLogger:
    """获取全局 shadow logger"""
    global _shadow_logger
    if _shadow_logger is None:
        _shadow_logger = ShadowEventsLogger()
    return _shadow_logger
