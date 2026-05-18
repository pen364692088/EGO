"""
Policy Memory - 策略层

职责:
- 存储长期偏好/约束/原则
- 从叙事中提炼策略候选
- 维护策略生命周期
- 为行为决策提供指导

边界:
- 从 Narrative Memory 读取叙事
- 策略可被反思修正
- 不直接引用原始事件

权威源: OpenEmotion
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from enum import Enum
import uuid


class PolicyType(Enum):
    """策略类型"""
    # 行为约束
    BOUNDARY = "boundary"          # 边界约束
    PREFERENCE = "preference"      # 偏好
    PROHIBITION = "prohibition"    # 禁止
    
    # 执行原则
    PRIORITY = "priority"          # 优先级规则
    ESCALATION = "escalation"      # 升级规则
    DELEGATION = "delegation"      # 委托规则
    
    # 学习结果
    LESSON_LEARNED = "lesson_learned"    # 教训
    BEST_PRACTICE = "best_practice"      # 最佳实践
    ANTI_PATTERN = "anti_pattern"        # 反模式


class PolicyStatus(Enum):
    """策略状态"""
    PROPOSED = "proposed"      # 提议中
    ADOPTED = "adopted"        # 已采纳
    ACTIVE = "active"          # 生效中
    DEPRECATED = "deprecated"  # 已弃用
    REJECTED = "rejected"      # 已拒绝


class PolicyStrength(Enum):
    """策略强度"""
    SOFT = "soft"        # 软约束（可违反）
    MEDIUM = "medium"    # 中等约束
    HARD = "hard"        # 硬约束（不可违反）


@dataclass
class Policy:
    """
    策略 - 长期偏好/约束
    
    设计原则:
    - 从叙事提炼，不是从事件
    - 可被反思修正
    - 维护来源追溯
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_type: PolicyType = PolicyType.PREFERENCE
    name: str = ""
    description: str = ""
    
    # 内容
    condition: str = ""      # 触发条件
    action: str = ""         # 建议行为
    
    # 元数据
    status: PolicyStatus = PolicyStatus.PROPOSED
    strength: PolicyStrength = PolicyStrength.MEDIUM
    priority: int = 50  # 0-100
    
    # 来源追溯
    source_narrative_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_applied: Optional[datetime] = None
    application_count: int = 0
    
    # 扩展
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def apply(self) -> None:
        """记录策略被应用"""
        self.last_applied = datetime.utcnow()
        self.application_count += 1
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "policy_type": self.policy_type.value,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "action": self.action,
            "status": self.status.value,
            "strength": self.strength.value,
            "priority": self.priority,
            "source_narrative_ids": self.source_narrative_ids,
            "created_at": self.created_at.isoformat(),
            "last_applied": self.last_applied.isoformat() if self.last_applied else None,
            "application_count": self.application_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Policy":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            policy_type=PolicyType(data["policy_type"]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            condition=data.get("condition", ""),
            action=data.get("action", ""),
            status=PolicyStatus(data.get("status", "proposed")),
            strength=PolicyStrength(data.get("strength", "medium")),
            priority=data.get("priority", 50),
            source_narrative_ids=data.get("source_narrative_ids", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_applied=datetime.fromisoformat(data["last_applied"]) if data.get("last_applied") else None,
            application_count=data.get("application_count", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


class PolicyMemory:
    """
    策略存储
    
    职责:
    - 维护策略生命周期
    - 提供策略查询
    - 记录应用历史
    
    不负责:
    - 策略生成逻辑
    - 策略冲突解决
    - 策略执行
    """
    
    def __init__(self):
        self._policies: list[Policy] = []
        self._name_index: dict[str, str] = {}  # name -> policy_id
    
    def propose(
        self,
        name: str,
        description: str,
        policy_type: PolicyType = PolicyType.PREFERENCE,
        condition: str = "",
        action: str = "",
        strength: PolicyStrength = PolicyStrength.MEDIUM,
        source_narrative_ids: Optional[list[str]] = None,
    ) -> Policy:
        """
        提议新策略
        
        Returns:
            提议的策略对象（状态为 PROPOSED）
        """
        policy = Policy(
            policy_type=policy_type,
            name=name,
            description=description,
            condition=condition,
            action=action,
            status=PolicyStatus.PROPOSED,
            strength=strength,
            source_narrative_ids=source_narrative_ids or [],
        )
        
        self._policies.append(policy)
        self._name_index[name] = policy.id
        
        return policy
    
    def adopt(self, policy_id: str) -> Optional[Policy]:
        """采纳策略"""
        policy = self.get(policy_id)
        if policy and policy.status == PolicyStatus.PROPOSED:
            policy.status = PolicyStatus.ADOPTED
            return policy
        return None
    
    def activate(self, policy_id: str) -> Optional[Policy]:
        """激活策略"""
        policy = self.get(policy_id)
        if policy and policy.status in (PolicyStatus.PROPOSED, PolicyStatus.ADOPTED):
            policy.status = PolicyStatus.ACTIVE
            return policy
        return None
    
    def deprecate(self, policy_id: str, reason: str = "") -> Optional[Policy]:
        """弃用策略"""
        policy = self.get(policy_id)
        if policy:
            policy.status = PolicyStatus.DEPRECATED
            policy.metadata["deprecation_reason"] = reason
            policy.metadata["deprecated_at"] = datetime.utcnow().isoformat()
            return policy
        return None
    
    def get(self, policy_id: str) -> Optional[Policy]:
        """按ID获取策略"""
        for policy in self._policies:
            if policy.id == policy_id:
                return policy
        return None
    
    def get_by_name(self, name: str) -> Optional[Policy]:
        """按名称获取策略"""
        policy_id = self._name_index.get(name)
        return self.get(policy_id) if policy_id else None
    
    def query(
        self,
        policy_type: Optional[PolicyType] = None,
        status: Optional[PolicyStatus] = None,
        strength: Optional[PolicyStrength] = None,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> list[Policy]:
        """
        查询策略
        
        Args:
            policy_type: 过滤策略类型
            status: 过滤状态
            strength: 过滤强度
            tag: 过滤标签
            limit: 最大返回数量
            
        Returns:
            匹配的策略列表（按优先级排序）
        """
        results = self._policies
        
        if policy_type:
            results = [p for p in results if p.policy_type == policy_type]
        
        if status:
            results = [p for p in results if p.status == status]
        
        if strength:
            results = [p for p in results if p.strength == strength]
        
        if tag:
            results = [p for p in results if tag in p.tags]
        
        # 按优先级排序
        results = sorted(results, key=lambda p: p.priority, reverse=True)
        
        return results[:limit]
    
    def get_active(self) -> list[Policy]:
        """获取所有生效中的策略"""
        return self.query(status=PolicyStatus.ACTIVE)
    
    def get_highest_priority(
        self,
        condition: Optional[str] = None,
        limit: int = 5,
    ) -> list[Policy]:
        """
        获取最高优先级的策略
        
        Args:
            condition: 可选的条件过滤
            limit: 返回数量
            
        Returns:
            优先级最高的策略列表
        """
        active = self.get_active()
        if condition:
            # 简单匹配（实际应用时可以更复杂）
            active = [p for p in active if condition in p.condition or not p.condition]
        
        return sorted(active, key=lambda p: p.priority, reverse=True)[:limit]
    
    def record_application(self, policy_id: str) -> None:
        """记录策略被应用"""
        policy = self.get(policy_id)
        if policy:
            policy.apply()
    
    def count(self, status: Optional[PolicyStatus] = None) -> int:
        """统计策略数量"""
        if status:
            return sum(1 for p in self._policies if p.status == status)
        return len(self._policies)
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "policies": [p.to_dict() for p in self._policies],
            "count": len(self._policies),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PolicyMemory":
        """从字典恢复"""
        memory = cls()
        memory._policies = [Policy.from_dict(p) for p in data.get("policies", [])]
        memory._name_index = {p.name: p.id for p in memory._policies}
        return memory
