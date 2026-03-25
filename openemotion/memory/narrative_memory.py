"""
Narrative Memory - 叙事层

职责:
- 聚合事件形成叙事（可变）
- 维护叙事弧（主题、发展、转折）
- 提供跨会话连续性
- 为策略层提供候选素材

边界:
- 从 Event Memory 读取原始事件
- 不直接修改事件
- 叙事可被修正/覆盖

权威源: OpenEmotion
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum
import uuid


class NarrativeType(Enum):
    """叙事类型"""
    # 项目叙事
    PROJECT_START = "project_start"
    PROJECT_PROGRESS = "project_progress"
    PROJECT_MILESTONE = "project_milestone"
    PROJECT_COMPLETION = "project_completion"
    
    # 关系叙事
    RELATIONSHIP_FORMATION = "relationship_formation"
    RELATIONSHIP_EVOLUTION = "relationship_evolution"
    
    # 学习叙事
    SKILL_ACQUISITION = "skill_acquisition"
    KNOWLEDGE_INTEGRATION = "knowledge_integration"
    PATTERN_RECOGNITION = "pattern_recognition"
    
    # 问题叙事
    PROBLEM_ENCOUNTERED = "problem_encountered"
    PROBLEM_SOLVED = "problem_solved"
    PROBLEM_UNSOLVED = "problem_unsolved"
    
    # 反思叙事
    INSIGHT = "insight"
    BEHAVIOR_CHANGE = "behavior_change"
    PREFERENCE_SHIFT = "preference_shift"


class NarrativeStatus(Enum):
    """叙事状态"""
    ACTIVE = "active"          # 正在发展
    PAUSED = "paused"          # 暂停/等待
    COMPLETED = "completed"    # 已完结
    SUPERSEDED = "superseded"  # 被新叙事取代


@dataclass
class Narrative:
    """
    叙事 - 事件的结构化聚合
    
    设计原则:
    - 可变（可被修正/覆盖）
    - 从事件派生，但不修改事件
    - 维护引用关系
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    narrative_type: NarrativeType = NarrativeType.PROJECT_PROGRESS
    title: str = ""
    summary: str = ""
    status: NarrativeStatus = NarrativeStatus.ACTIVE
    
    # 事件引用
    event_ids: list[str] = field(default_factory=list)
    
    # 时间范围
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # 元数据
    themes: list[str] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)
    related_narrative_ids: list[str] = field(default_factory=list)
    
    # 扩展字段
    metadata: dict = field(default_factory=dict)
    
    def add_event(self, event_id: str) -> None:
        """添加事件引用"""
        if event_id not in self.event_ids:
            self.event_ids.append(event_id)
            self.last_updated = datetime.utcnow()
    
    def add_insight(self, insight: str) -> None:
        """添加洞察"""
        if insight not in self.key_insights:
            self.key_insights.append(insight)
            self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "narrative_type": self.narrative_type.value,
            "title": self.title,
            "summary": self.summary,
            "status": self.status.value,
            "event_ids": self.event_ids,
            "started_at": self.started_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "themes": self.themes,
            "key_insights": self.key_insights,
            "related_narrative_ids": self.related_narrative_ids,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Narrative":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            narrative_type=NarrativeType(data["narrative_type"]),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            status=NarrativeStatus(data.get("status", "active")),
            event_ids=data.get("event_ids", []),
            started_at=datetime.fromisoformat(data["started_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            themes=data.get("themes", []),
            key_insights=data.get("key_insights", []),
            related_narrative_ids=data.get("related_narrative_ids", []),
            metadata=data.get("metadata", {}),
        )


class NarrativeMemory:
    """
    叙事存储
    
    职责:
    - 维护叙事弧
    - 聚合相关事件
    - 提供主题查询
    
    不负责:
    - 原始事件存储
    - 策略生成
    - 重要性判断
    """
    
    def __init__(self):
        self._narratives: list[Narrative] = []
        self._event_to_narratives: dict[str, list[str]] = {}  # event_id -> narrative_ids
    
    def create(
        self,
        narrative_type: NarrativeType,
        title: str,
        summary: str = "",
        event_ids: Optional[list[str]] = None,
        themes: Optional[list[str]] = None,
    ) -> Narrative:
        """
        创建叙事
        
        Returns:
            创建的叙事对象
        """
        narrative = Narrative(
            narrative_type=narrative_type,
            title=title,
            summary=summary,
            event_ids=event_ids or [],
            themes=themes or [],
        )
        self._narratives.append(narrative)
        
        # 更新索引
        for event_id in narrative.event_ids:
            if event_id not in self._event_to_narratives:
                self._event_to_narratives[event_id] = []
            self._event_to_narratives[event_id].append(narrative.id)
        
        return narrative
    
    def get(self, narrative_id: str) -> Optional[Narrative]:
        """按ID获取叙事"""
        for narrative in self._narratives:
            if narrative.id == narrative_id:
                return narrative
        return None
    
    def update(
        self,
        narrative_id: str,
        summary: Optional[str] = None,
        status: Optional[NarrativeStatus] = None,
        add_events: Optional[list[str]] = None,
        add_insights: Optional[list[str]] = None,
    ) -> Optional[Narrative]:
        """
        更新叙事
        
        Returns:
            更新后的叙事对象，或 None 如果不存在
        """
        narrative = self.get(narrative_id)
        if not narrative:
            return None
        
        if summary:
            narrative.summary = summary
        
        if status:
            narrative.status = status
        
        if add_events:
            for event_id in add_events:
                narrative.add_event(event_id)
                if event_id not in self._event_to_narratives:
                    self._event_to_narratives[event_id] = []
                if narrative_id not in self._event_to_narratives[event_id]:
                    self._event_to_narratives[event_id].append(narrative_id)
        
        if add_insights:
            for insight in add_insights:
                narrative.add_insight(insight)
        
        narrative.last_updated = datetime.utcnow()
        return narrative
    
    def query(
        self,
        narrative_type: Optional[NarrativeType] = None,
        status: Optional[NarrativeStatus] = None,
        theme: Optional[str] = None,
        limit: int = 50,
    ) -> list[Narrative]:
        """
        查询叙事
        
        Args:
            narrative_type: 过滤叙事类型
            status: 过滤状态
            theme: 过滤主题
            limit: 最大返回数量
            
        Returns:
            匹配的叙事列表
        """
        results = self._narratives
        
        if narrative_type:
            results = [n for n in results if n.narrative_type == narrative_type]
        
        if status:
            results = [n for n in results if n.status == status]
        
        if theme:
            results = [n for n in results if theme in n.themes]
        
        # 按最后更新时间排序
        results = sorted(results, key=lambda n: n.last_updated, reverse=True)
        
        return results[:limit]
    
    def find_by_event(self, event_id: str) -> list[Narrative]:
        """查找包含特定事件的所有叙事"""
        narrative_ids = self._event_to_narratives.get(event_id, [])
        return [n for n in self._narratives if n.id in narrative_ids]
    
    def get_active(self) -> list[Narrative]:
        """获取所有活跃叙事"""
        return self.query(status=NarrativeStatus.ACTIVE)
    
    def count(self, status: Optional[NarrativeStatus] = None) -> int:
        """统计叙事数量"""
        if status:
            return sum(1 for n in self._narratives if n.status == status)
        return len(self._narratives)
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "narratives": [n.to_dict() for n in self._narratives],
            "count": len(self._narratives),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "NarrativeMemory":
        """从字典恢复"""
        memory = cls()
        memory._narratives = [Narrative.from_dict(n) for n in data.get("narratives", [])]
        
        # 重建索引
        for narrative in memory._narratives:
            for event_id in narrative.event_ids:
                if event_id not in memory._event_to_narratives:
                    memory._event_to_narratives[event_id] = []
                memory._event_to_narratives[event_id].append(narrative.id)
        
        return memory
