"""
OpenEmotion Self-Model Module

自我模型的正式本体模块。
负责能力、限制、目标、承诺的定义和更新规则。

此模块是 self-model 的唯一权威源。
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class CapabilityLevel(Enum):
    """能力等级"""
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class GoalStatus(Enum):
    """目标状态"""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Priority(Enum):
    """优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Capability:
    """能力"""
    capability_id: str
    name: str
    category: str
    current_level: str
    description: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    last_verified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Limitation:
    """限制"""
    limitation_id: str
    description: str
    impact_level: str
    workaround: Optional[str] = None
    discovered_at: Optional[str] = None
    context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Goal:
    """目标"""
    goal_id: str
    description: str
    status: str
    priority: str
    progress: float = 0.0
    deadline: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StandingCommitment:
    """持续承诺"""
    commitment_id: str
    source: str  # identity_invariants / runtime_learned / owner_directive
    description: str
    binding_level: str
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SelfModel:
    """
    自我模型本体

    这是系统能力和状态的唯一权威定义。
    所有字段语义的解释权归 OpenEmotion。
    """

    # 关联的身份
    identity_handle: str

    # 能力列表
    capabilities: List[Capability] = field(default_factory=list)

    # 限制列表
    limitations: List[Limitation] = field(default_factory=list)

    # 活跃目标
    active_goals: List[Goal] = field(default_factory=list)

    # 持续承诺
    standing_commitments: List[StandingCommitment] = field(default_factory=list)

    # 工具权限边界
    current_allowed_tools: List[str] = field(default_factory=list)
    restricted_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)

    # 依赖映射
    external_services: List[Dict[str, Any]] = field(default_factory=list)
    internal_modules: List[Dict[str, Any]] = field(default_factory=list)

    # 领域置信度
    confidence_by_domain: Dict[str, float] = field(default_factory=dict)

    # 已知未知
    known_unknowns: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_handle": self.identity_handle,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "limitations": [l.to_dict() for l in self.limitations],
            "active_goals": [g.to_dict() for g in self.active_goals],
            "standing_commitments": [c.to_dict() for c in self.standing_commitments],
            "tool_authority_boundary": {
                "current_allowed_tools": self.current_allowed_tools,
                "restricted_tools": self.restricted_tools,
                "forbidden_tools": self.forbidden_tools,
            },
            "dependency_map": {
                "external_services": self.external_services,
                "internal_modules": self.internal_modules,
            },
            "confidence_by_domain": self.confidence_by_domain,
            "known_unknowns": self.known_unknowns,
            "created_at": self.created_at,
            "last_modified_at": self.last_modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfModel":
        """从字典创建"""
        tools = data.get("tool_authority_boundary", {})
        dep_map = data.get("dependency_map", {})

        return cls(
            identity_handle=data["identity_handle"],
            capabilities=[Capability(**c) if isinstance(c, dict) else c for c in data.get("capabilities", [])],
            limitations=[Limitation(**l) if isinstance(l, dict) else l for l in data.get("limitations", [])],
            active_goals=[Goal(**g) if isinstance(g, dict) else g for g in data.get("active_goals", [])],
            standing_commitments=[StandingCommitment(**c) if isinstance(c, dict) else c for c in data.get("standing_commitments", [])],
            current_allowed_tools=tools.get("current_allowed_tools", []),
            restricted_tools=tools.get("restricted_tools", []),
            forbidden_tools=tools.get("forbidden_tools", []),
            external_services=dep_map.get("external_services", []),
            internal_modules=dep_map.get("internal_modules", []),
            confidence_by_domain=data.get("confidence_by_domain", {}),
            known_unknowns=data.get("known_unknowns", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_modified_at=data.get("last_modified_at", datetime.now(timezone.utc).isoformat()),
        )

    def get_capability_by_id(self, capability_id: str) -> Optional[Capability]:
        """获取能力"""
        for c in self.capabilities:
            if c.capability_id == capability_id:
                return c
        return None

    def get_goal_by_id(self, goal_id: str) -> Optional[Goal]:
        """获取目标"""
        for g in self.active_goals:
            if g.goal_id == goal_id:
                return g
        return None

    def update_capability_level(self, capability_id: str, new_level: str) -> bool:
        """更新能力等级"""
        cap = self.get_capability_by_id(capability_id)
        if cap:
            cap.current_level = new_level
            cap.last_verified_at = datetime.now(timezone.utc).isoformat()
            self.last_modified_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def update_goal_status(self, goal_id: str, new_status: str) -> bool:
        """更新目标状态"""
        goal = self.get_goal_by_id(goal_id)
        if goal:
            goal.status = new_status
            self.last_modified_at = datetime.now(timezone.utc).isoformat()
            return True
        return False


def create_default_self_model(identity_handle: str) -> SelfModel:
    """创建默认自我模型"""
    return SelfModel(
        identity_handle=identity_handle,
        capabilities=[
            Capability(
                capability_id="cap_file_operations",
                name="文件操作",
                category="file_operations",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
            Capability(
                capability_id="cap_code_execution",
                name="代码执行",
                category="code_execution",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
            Capability(
                capability_id="cap_reasoning",
                name="推理",
                category="reasoning",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
        ],
        limitations=[
            Limitation(
                limitation_id="lim_no_gui",
                description="无法直接操作 GUI 应用",
                impact_level="medium",
                workaround="通过 CLI 工具间接操作",
            ),
        ],
        current_allowed_tools=["read", "write", "edit", "exec"],
        confidence_by_domain={
            "file_operations": 0.95,
            "code_execution": 0.9,
            "reasoning": 0.85,
        },
    )
