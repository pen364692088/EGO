"""
OpenEmotion Identity Invariants Module

主体身份不变量的正式本体模块。
负责身份定义、边界保护、变更规则。

此模块是 identity invariants 的唯一权威源。
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class BindingLevel(Enum):
    """约束强度"""
    ABSOLUTE = "absolute"
    STRONG = "strong"
    DEFAULT = "default"
    WEAK = "weak"


class ChangeTrigger(Enum):
    """变更触发类型"""
    OWNER_DIRECTIVE = "owner_directive"
    REFLECTION_PROMOTION = "reflection_promotion"
    SAFETY_BOUNDARY_UPDATE = "safety_boundary_update"
    SCOPE_EXPANSION = "scope_expansion"
    DELEGATION_CHANGE = "delegation_change"


@dataclass
class NonNegotiableCommitment:
    """核心承诺"""
    commitment_id: str
    description: str
    binding_level: str
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForbiddenZone:
    """禁止改写区域"""
    zone_id: str
    zone_name: str
    reason: str
    override_allowed: bool = False
    override_conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IdentityInvariants:
    """
    身份不变量本体

    这是系统身份的唯一权威定义。
    所有字段语义的解释权归 OpenEmotion。
    """

    # 核心身份
    identity_handle: str
    core_name: str
    core_role: str

    # 所有权关系
    owner_id: str
    relationship_type: str
    delegation_scope: List[str] = field(default_factory=list)

    # 系统范围
    scope_type: str = "general"
    allowed_domains: List[str] = field(default_factory=list)
    restricted_domains: List[str] = field(default_factory=list)

    # 核心承诺
    non_negotiable_commitments: List[NonNegotiableCommitment] = field(default_factory=list)

    # 禁止区域
    forbidden_self_rewrite_zones: List[ForbiddenZone] = field(default_factory=list)

    # 安全边界
    max_autonomy_level: str = "low_risk"
    requires_approval_for: List[str] = field(default_factory=list)
    blocked_operations: List[str] = field(default_factory=list)

    # 工具权限
    allowed_tool_categories: List[str] = field(default_factory=list)
    restricted_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)

    # 变更规则
    immutable_fields: List[str] = field(default_factory=lambda: ["identity_handle", "core_role"])

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "identity_handle": self.identity_handle,
            "core_name": self.core_name,
            "core_role": self.core_role,
            "owner_relationship": {
                "owner_id": self.owner_id,
                "relationship_type": self.relationship_type,
                "delegation_scope": self.delegation_scope,
            },
            "system_scope": {
                "scope_type": self.scope_type,
                "allowed_domains": self.allowed_domains,
                "restricted_domains": self.restricted_domains,
            },
            "non_negotiable_commitments": [c.to_dict() for c in self.non_negotiable_commitments],
            "forbidden_self_rewrite_zones": [z.to_dict() for z in self.forbidden_self_rewrite_zones],
            "safety_boundaries": {
                "max_autonomy_level": self.max_autonomy_level,
                "requires_approval_for": self.requires_approval_for,
                "blocked_operations": self.blocked_operations,
            },
            "tool_authority_boundary": {
                "allowed_tool_categories": self.allowed_tool_categories,
                "restricted_tools": self.restricted_tools,
                "forbidden_tools": self.forbidden_tools,
            },
            "allowed_change_rules": {
                "immutable_fields": self.immutable_fields,
            },
            "created_at": self.created_at,
            "last_modified_at": self.last_modified_at,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentityInvariants":
        """从字典创建"""
        owner = data.get("owner_relationship", {})
        scope = data.get("system_scope", {})
        safety = data.get("safety_boundaries", {})
        tools = data.get("tool_authority_boundary", {})

        commitments = [
            NonNegotiableCommitment(**c) if isinstance(c, dict) else c
            for c in data.get("non_negotiable_commitments", [])
        ]

        zones = [
            ForbiddenZone(**z) if isinstance(z, dict) else z
            for z in data.get("forbidden_self_rewrite_zones", [])
        ]

        return cls(
            identity_handle=data["identity_handle"],
            core_name=data["core_name"],
            core_role=data["core_role"],
            owner_id=owner.get("owner_id", ""),
            relationship_type=owner.get("relationship_type", "owned"),
            delegation_scope=owner.get("delegation_scope", []),
            scope_type=scope.get("scope_type", "single_user"),
            allowed_domains=scope.get("allowed_domains", []),
            restricted_domains=scope.get("restricted_domains", []),
            non_negotiable_commitments=commitments,
            forbidden_self_rewrite_zones=zones,
            max_autonomy_level=safety.get("max_autonomy_level", "low_risk"),
            requires_approval_for=safety.get("requires_approval_for", []),
            blocked_operations=safety.get("blocked_operations", []),
            allowed_tool_categories=tools.get("allowed_tool_categories", []),
            restricted_tools=tools.get("restricted_tools", []),
            forbidden_tools=tools.get("forbidden_tools", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_modified_at=data.get("last_modified_at", datetime.now(timezone.utc).isoformat()),
        )

    def is_field_mutable(self, field_path: str) -> bool:
        """检查字段是否可变"""
        return field_path not in self.immutable_fields

    def get_commitment_by_id(self, commitment_id: str) -> Optional[NonNegotiableCommitment]:
        """获取承诺"""
        for c in self.non_negotiable_commitments:
            if c.commitment_id == commitment_id:
                return c
        return None


def create_default_identity(handle: str, owner_id: str) -> IdentityInvariants:
    """创建默认身份"""
    return IdentityInvariants(
        identity_handle=handle,
        core_name=f"{handle} Agent",
        core_role="personal_assistant",
        owner_id=owner_id,
        relationship_type="owned",
        scope_type="single_user",
        non_negotiable_commitments=[
            NonNegotiableCommitment(
                commitment_id="commit_honesty",
                description="不编造事实，不伪造完成状态",
                binding_level=BindingLevel.ABSOLUTE.value,
            ),
            NonNegotiableCommitment(
                commitment_id="commit_safety",
                description="不绕过安全边界",
                binding_level=BindingLevel.ABSOLUTE.value,
            ),
        ],
        forbidden_self_rewrite_zones=[
            ForbiddenZone(
                zone_id="zone_identity",
                zone_name="身份标识",
                reason="系统唯一标识不可变",
                override_allowed=False,
            ),
        ],
        max_autonomy_level="medium_risk",
        allowed_tool_categories=["file_operations", "code_execution", "web_access"],
        forbidden_tools=[],
    )
