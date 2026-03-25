"""
Self-Model Adapter

连接 openemotion.self_model 到 emotiond/core.py。

职责:
- 提供 legacy SelfModelV0 兼容接口
- 内部使用 openemotion.self_model.SelfModel
- 处理 identity_handle 默认值

边界:
- 不修改 openemotion.self_model 语义
- 只做接口适配
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认 identity_handle
DEFAULT_IDENTITY_HANDLE = "openemotion-default"

# Feature flag
ENABLE_OPENEMOTION_SELF_MODEL = True


class SelfModelAdapter:
    """
    Self-Model 适配器
    
    将 openemotion.self_model.SelfModel 适配为 legacy 接口。
    
    使用方式:
        adapter = SelfModelAdapter()
        
        # Legacy 风格调用（不需要 identity_handle）
        state = adapter.get_state()
        adapter.apply_event(event_dict)
        
        # 内部会调用 openemotion.self_model.SelfModel
    """
    
    _instance: Optional["SelfModelAdapter"] = None
    
    def __init__(
        self,
        identity_handle: str = DEFAULT_IDENTITY_HANDLE,
        shadow_mode: bool = True,
    ):
        """
        初始化适配器
        
        Args:
            identity_handle: 身份标识
            shadow_mode: 是否运行在 shadow 模式（与 legacy 双轨运行）
        """
        self.identity_handle = identity_handle
        self.shadow_mode = shadow_mode
        self._new_model = None
        self._legacy_model = None
        self._metrics = {
            "total_calls": 0,
            "new_model_calls": 0,
            "legacy_calls": 0,
            "errors": 0,
        }
        
        # 尝试加载新的 SelfModel
        if ENABLE_OPENEMOTION_SELF_MODEL:
            try:
                from openemotion.self_model import SelfModel
                self._new_model = SelfModel(identity_handle=identity_handle)
                logger.info(f"[SelfModelAdapter] OpenEmotion SelfModel loaded (identity_handle={identity_handle})")
            except Exception as e:
                logger.warning(f"[SelfModelAdapter] Failed to load OpenEmotion SelfModel: {e}")
                self._metrics["errors"] += 1
        
        # 加载 legacy SelfModelV0
        try:
            from emotiond.self_model import SelfModelV0, get_self_model_v0
            self._legacy_model = get_self_model_v0()
            logger.info("[SelfModelAdapter] Legacy SelfModelV0 loaded")
        except Exception as e:
            logger.warning(f"[SelfModelAdapter] Failed to load legacy SelfModelV0: {e}")
    
    @classmethod
    def get_instance(cls) -> "SelfModelAdapter":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """重置实例"""
        cls._instance = None
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取自我模型状态
        
        Returns:
            状态字典（兼容 legacy 格式）
        """
        self._metrics["total_calls"] += 1
        
        # Shadow mode: 同时调用两个模型
        if self.shadow_mode and self._new_model and self._legacy_model:
            self._metrics["new_model_calls"] += 1
            self._metrics["legacy_calls"] += 1
            
            new_state = self._new_model.to_dict()
            legacy_state = self._get_legacy_state()
            
            # 返回 legacy 格式，但记录 new_state 到 shadow artifact
            self._record_shadow_artifact(new_state, legacy_state)
            
            return legacy_state
        
        # 非 shadow mode: 只用 new model
        if self._new_model:
            self._metrics["new_model_calls"] += 1
            return self._new_model.to_dict()
        
        # Fallback: 只用 legacy
        if self._legacy_model:
            self._metrics["legacy_calls"] += 1
            return self._get_legacy_state()
        
        # 兜底
        return {}
    
    def _get_legacy_state(self) -> Dict[str, Any]:
        """获取 legacy 模型状态"""
        if self._legacy_model:
            try:
                return {
                    "self_confidence": getattr(self._legacy_model, "self_confidence", 0.5),
                    "conflict_level": getattr(self._legacy_model, "conflict_level", 0.0),
                    "control_estimate": getattr(self._legacy_model, "control_estimate", 0.5),
                }
            except Exception as e:
                logger.warning(f"[SelfModelAdapter] Failed to get legacy state: {e}")
        return {}
    
    def apply_event(self, event_dict: Dict[str, Any], ctx: Optional[Dict] = None) -> Dict[str, Any]:
        """
        应用事件到自我模型
        
        Args:
            event_dict: 事件字典
            ctx: 上下文
            
        Returns:
            更新结果
        """
        self._metrics["total_calls"] += 1
        
        result = {}
        
        # Shadow mode: 同时调用两个模型
        if self.shadow_mode and self._new_model:
            self._metrics["new_model_calls"] += 1
            try:
                # 新模型可能没有 apply_event 方法，这里只是尝试
                if hasattr(self._new_model, "apply_event"):
                    result["new_model"] = self._new_model.apply_event(event_dict, ctx)
            except Exception as e:
                logger.warning(f"[SelfModelAdapter] New model apply_event failed: {e}")
                result["new_model_error"] = str(e)
        
        # Legacy 调用
        if self._legacy_model:
            self._metrics["legacy_calls"] += 1
            try:
                if hasattr(self._legacy_model, "apply_event"):
                    result["legacy"] = self._legacy_model.apply_event(event_dict, ctx)
            except Exception as e:
                logger.warning(f"[SelfModelAdapter] Legacy apply_event failed: {e}")
                result["legacy_error"] = str(e)
        
        return result
    
    def _record_shadow_artifact(self, new_state: Dict, legacy_state: Dict) -> None:
        """记录 shadow artifact"""
        try:
            import json
            from datetime import datetime
            
            artifact_dir = Path("artifacts/self_model_adapter")
            artifact_dir.mkdir(parents=True, exist_ok=True)
            
            artifact = {
                "timestamp": datetime.utcnow().isoformat(),
                "new_model_state": new_state,
                "legacy_state": legacy_state,
                "metrics": self._metrics,
            }
            
            artifact_path = artifact_dir / f"shadow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
            
        except Exception as e:
            logger.warning(f"[SelfModelAdapter] Failed to record shadow artifact: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取适配器指标"""
        return {
            **self._metrics,
            "new_model_available": self._new_model is not None,
            "legacy_model_available": self._legacy_model is not None,
            "shadow_mode": self.shadow_mode,
            "identity_handle": self.identity_handle,
        }


# 便捷函数
_adapter: Optional[SelfModelAdapter] = None


def get_self_model_adapter() -> SelfModelAdapter:
    """获取 SelfModelAdapter 单例"""
    global _adapter
    if _adapter is None:
        _adapter = SelfModelAdapter.get_instance()
    return _adapter


def reset_self_model_adapter() -> None:
    """重置 SelfModelAdapter"""
    global _adapter
    _adapter = None
    SelfModelAdapter.reset()
