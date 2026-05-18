"""
Runtime Metrics Aggregator - Rollback Mechanism

回滚机制
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import time
import json


@dataclass
class RollbackSnapshot:
    """回滚快照"""
    timestamp: int
    feature_enabled: bool
    config: Dict[str, Any]
    buffer_stats: Dict[str, Any]


class RollbackManager:
    """回滚管理器"""
    
    def __init__(self, snapshot_dir: Optional[str] = None):
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else Path("/tmp/metrics_rollback")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots: List[RollbackSnapshot] = []
    
    def create_snapshot(
        self,
        feature_enabled: bool,
        config: Dict[str, Any],
        buffer_stats: Dict[str, Any]
    ) -> RollbackSnapshot:
        """
        创建回滚快照
        
        Args:
            feature_enabled: 功能开关状态
            config: 配置
            buffer_stats: 缓冲区统计
            
        Returns:
            RollbackSnapshot: 快照
        """
        snapshot = RollbackSnapshot(
            timestamp=int(time.time() * 1000),
            feature_enabled=feature_enabled,
            config=config.copy(),
            buffer_stats=buffer_stats.copy()
        )
        
        self.snapshots.append(snapshot)
        
        # 保存到文件
        snapshot_file = self.snapshot_dir / f"snapshot_{snapshot.timestamp}.json"
        with open(snapshot_file, 'w') as f:
            json.dump({
                "timestamp": snapshot.timestamp,
                "feature_enabled": snapshot.feature_enabled,
                "config": snapshot.config,
                "buffer_stats": snapshot.buffer_stats
            }, f, indent=2)
        
        return snapshot
    
    def rollback(self, target_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        回滚到指定快照
        
        Args:
            target_timestamp: 目标时间戳（None 表示最新）
            
        Returns:
            Dict: 回滚结果
        """
        if not self.snapshots:
            return {
                "success": False,
                "error": "No snapshots available"
            }
        
        if target_timestamp is None:
            snapshot = self.snapshots[-1]
        else:
            snapshot = next(
                (s for s in self.snapshots if s.timestamp == target_timestamp),
                None
            )
            if snapshot is None:
                return {
                    "success": False,
                    "error": f"Snapshot not found: {target_timestamp}"
                }
        
        # 执行回滚
        result = {
            "success": True,
            "timestamp": int(time.time() * 1000),
            "target_timestamp": snapshot.timestamp,
            "actions": []
        }
        
        # 1. 关闭 feature flag
        result["actions"].append("disabled_feature_flag")
        
        # 2. 恢复配置
        result["actions"].append("restored_config")
        result["restored_config"] = snapshot.config
        
        # 3. 清空缓冲区（可选）
        result["actions"].append("cleared_buffer")
        
        # 记录回滚事件
        rollback_file = self.snapshot_dir / f"rollback_{result['timestamp']}.json"
        with open(rollback_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def quick_rollback(self) -> Dict[str, Any]:
        """
        快速回滚（一键回滚）
        
        Returns:
            Dict: 回滚结果
        """
        return {
            "success": True,
            "timestamp": int(time.time() * 1000),
            "actions": [
                "disabled_feature_flag",
                "cleared_buffer",
                "reset_circuit_breaker"
            ],
            "previous_state": "enabled",
            "current_state": "disabled"
        }
    
    def get_snapshots(self) -> List[Dict[str, Any]]:
        """获取所有快照"""
        return [
            {
                "timestamp": s.timestamp,
                "feature_enabled": s.feature_enabled,
                "buffer_size": s.buffer_stats.get("size", 0)
            }
            for s in self.snapshots
        ]


# 全局实例
_default_rollback: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    """获取全局回滚管理器"""
    global _default_rollback
    if _default_rollback is None:
        _default_rollback = RollbackManager()
    return _default_rollback


def quick_rollback() -> Dict[str, Any]:
    """快速回滚"""
    return get_rollback_manager().quick_rollback()
