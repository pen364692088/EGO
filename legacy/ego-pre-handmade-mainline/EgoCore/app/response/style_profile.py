"""
StyleProfile v1 - EgoCore

轻量风格配置，用于支持风格连续性表达。

职责：
- 定义风格维度（warmth, directness, softness, initiative）
- 在会话内保持风格稳定
- 提供风格选择给 verbalizer

边界：
- 仅用于会话内风格一致性
- 不追求长期人格一致性
- 不存储敏感数据

版本：1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import random


@dataclass
class StyleDimensions:
    """风格维度"""
    warmth: float = 0.5        # [0, 1] 温暖度：0=冷淡，1=温暖
    directness: float = 0.5    # [0, 1] 直接度：0=委婉，1=直接
    softness: float = 0.5      # [0, 1] 柔和度：0=硬朗，1=柔和
    initiative: float = 0.5    # [0, 1] 主动度：0=被动，1=主动
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "warmth": self.warmth,
            "directness": self.directness,
            "softness": self.softness,
            "initiative": self.initiative,
        }
    
    def clamp(self) -> "StyleDimensions":
        """确保所有值在 [0, 1] 范围内"""
        return StyleDimensions(
            warmth=max(0.0, min(1.0, self.warmth)),
            directness=max(0.0, min(1.0, self.directness)),
            softness=max(0.0, min(1.0, self.softness)),
            initiative=max(0.0, min(1.0, self.initiative)),
        )


@dataclass
class StyleProfile:
    """
    风格配置 v1
    
    用于在会话内保持风格一致性。
    
    关键原则：
    - 轻度风格稳定，不是固定模板
    - 允许有轻微变化
    - 基于关系上下文调整
    """
    # 会话标识
    session_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 风格维度
    dimensions: StyleDimensions = field(default_factory=StyleDimensions)
    
    # 偏好的表达风格标记
    preferred_markers: list = field(default_factory=list)
    
    # 避免的表达风格标记
    avoid_markers: list = field(default_factory=list)
    
    # 最近使用的表达变体索引（用于避免重复）
    recent_variant_indices: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dimensions": self.dimensions.to_dict(),
            "preferred_markers": self.preferred_markers,
            "avoid_markers": self.avoid_markers,
            "recent_variant_indices": self.recent_variant_indices,
        }
    
    def _update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def adjust_for_warming(self) -> None:
        """调整为更温暖的风格"""
        self._update_timestamp()
        self.dimensions.warmth = min(1.0, self.dimensions.warmth + 0.1)
        self.dimensions.softness = min(1.0, self.dimensions.softness + 0.05)
    
    def adjust_for_cooling(self) -> None:
        """调整为更冷淡的风格"""
        self._update_timestamp()
        self.dimensions.warmth = max(0.0, self.dimensions.warmth - 0.1)
    
    def adjust_for_repair(self) -> None:
        """调整为修复风格"""
        self._update_timestamp()
        self.dimensions.warmth = min(0.9, self.dimensions.warmth + 0.15)
        self.dimensions.softness = min(0.8, self.dimensions.softness + 0.1)
        self.dimensions.directness = max(0.3, self.dimensions.directness - 0.1)
    
    def adjust_for_task_mode(self) -> None:
        """调整为任务模式风格"""
        self._update_timestamp()
        self.dimensions.directness = min(0.8, self.dimensions.directness + 0.1)
        self.dimensions.initiative = min(0.7, self.dimensions.initiative + 0.1)
    
    def select_variant_index(self, mode: str, num_variants: int) -> int:
        """
        选择一个变体索引，避免重复
        
        Args:
            mode: social mode 名称
            num_variants: 可用变体数量
        
        Returns:
            选择的变体索引
        """
        if num_variants <= 1:
            return 0
        
        # 获取最近使用的索引
        last_index = self.recent_variant_indices.get(mode, -1)
        
        # 选择不同的索引
        available = list(range(num_variants))
        if last_index in available and len(available) > 1:
            available.remove(last_index)
        
        # 加权选择：更倾向中间值
        chosen = random.choice(available)
        
        # 记录
        self.recent_variant_indices[mode] = chosen
        self._update_timestamp()
        
        return chosen
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleProfile":
        """从字典创建"""
        dim_data = data.get("dimensions", {})
        dimensions = StyleDimensions(
            warmth=dim_data.get("warmth", 0.5),
            directness=dim_data.get("directness", 0.5),
            softness=dim_data.get("softness", 0.5),
            initiative=dim_data.get("initiative", 0.5),
        )
        
        return cls(
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            dimensions=dimensions,
            preferred_markers=data.get("preferred_markers", []),
            avoid_markers=data.get("avoid_markers", []),
            recent_variant_indices=data.get("recent_variant_indices", {}),
        )


# ============================================================================
# 预定义风格配置
# ============================================================================

def get_warm_style() -> StyleDimensions:
    """温暖风格"""
    return StyleDimensions(
        warmth=0.7,
        directness=0.5,
        softness=0.6,
        initiative=0.5,
    )


def get_neutral_style() -> StyleDimensions:
    """中性风格"""
    return StyleDimensions(
        warmth=0.5,
        directness=0.5,
        softness=0.5,
        initiative=0.5,
    )


def get_repair_style() -> StyleDimensions:
    """修复风格"""
    return StyleDimensions(
        warmth=0.8,
        directness=0.3,
        softness=0.7,
        initiative=0.4,
    )


def get_task_style() -> StyleDimensions:
    """任务风格"""
    return StyleDimensions(
        warmth=0.5,
        directness=0.7,
        softness=0.4,
        initiative=0.6,
    )


# ============================================================================
# 会话级别的风格配置管理器
# ============================================================================

class StyleProfileManager:
    """
    风格配置管理器
    
    管理多个会话的风格配置。
    使用内存存储，不持久化。
    """
    
    def __init__(self):
        self._profiles: Dict[str, StyleProfile] = {}
    
    def get_profile(self, session_id: str) -> StyleProfile:
        """获取会话的风格配置"""
        if session_id not in self._profiles:
            self._profiles[session_id] = StyleProfile(session_id=session_id)
        return self._profiles[session_id]
    
    def update_profile(
        self,
        session_id: str,
        dimensions: Optional[StyleDimensions] = None,
    ) -> StyleProfile:
        """更新风格配置"""
        profile = self.get_profile(session_id)
        if dimensions:
            profile.dimensions = dimensions.clamp()
        return profile
    
    def adjust_for_context(
        self,
        session_id: str,
        relationship_context: Any,  # RelationshipContext
    ) -> StyleProfile:
        """根据关系上下文调整风格"""
        profile = self.get_profile(session_id)
        
        # 根据关系状态调整
        if relationship_context.is_in_repair_mode():
            profile.adjust_for_repair()
        elif relationship_context.should_be_warmer():
            profile.adjust_for_warming()
        
        return profile
    
    def clear_profile(self, session_id: str) -> None:
        """清除会话的风格配置"""
        if session_id in self._profiles:
            del self._profiles[session_id]
    
    def cleanup_old_profiles(self, max_age_minutes: int = 60) -> int:
        """清理旧的配置"""
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for session_id, profile in self._profiles.items():
            if profile.updated_at:
                updated = datetime.fromisoformat(profile.updated_at.replace('Z', '+00:00'))
                age_minutes = (now - updated).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._profiles[session_id]
        
        return len(to_remove)


# 全局实例
_manager: Optional[StyleProfileManager] = None


def get_style_profile_manager() -> StyleProfileManager:
    """获取全局风格配置管理器"""
    global _manager
    if _manager is None:
        _manager = StyleProfileManager()
    return _manager
