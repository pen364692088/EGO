"""
Consolidation - 记忆整合

职责: 把事件层向更高层提炼

最小职责:
- 从原始事件抽叙事候选
- 抽 policy/constraint 候选
- 给出合并/覆盖/忽略建议

设计原则:
- 这是"候选生成器"，不直接越权写最终 policy
- 必须有可解释结构输出

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import re


class ConsolidationAction(str, Enum):
    """整合动作"""
    CREATE = "create"  # 创建新的
    MERGE = "merge"  # 合并到已有
    UPDATE = "update"  # 更新已有
    IGNORE = "ignore"  # 忽略
    FLAG = "flag"  # 标记需要人工确认


@dataclass
class NarrativeCandidate:
    """
    叙事候选

    从事件提炼出的叙事结构
    """
    theme: str  # 主题
    summary: str  # 摘要
    arc_type: str = "progress"  # 弧类型: progress/regression/stable/conflict

    # 关键事件
    key_events: list[str] = field(default_factory=list)

    # 时间范围
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 置信度
    confidence: float = 0.5

    # 建议
    action: ConsolidationAction = ConsolidationAction.CREATE
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "summary": self.summary,
            "arc_type": self.arc_type,
            "key_events": self.key_events,
            "confidence": round(self.confidence, 3),
            "action": self.action.value,
            "reason": self.reason,
        }


@dataclass
class PolicyCandidate:
    """
    策略候选

    从事件提炼出的偏好/约束
    """
    policy_type: str  # preference/constraint/rule
    name: str  # 名称
    description: str  # 描述

    # 触发条件
    triggers: list[str] = field(default_factory=list)

    # 行为建议
    behavior: str = ""

    # 来源
    source_event_id: str = ""
    source_type: str = "inferred"  # inferred/explicit/learned

    # 置信度
    confidence: float = 0.5

    # 建议
    action: ConsolidationAction = ConsolidationAction.CREATE
    reason: str = ""

    # 有效期
    expires_after_events: Optional[int] = None  # N 个事件后过期

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_type": self.policy_type,
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "behavior": self.behavior,
            "source_event_id": self.source_event_id,
            "source_type": self.source_type,
            "confidence": round(self.confidence, 3),
            "action": self.action.value,
            "reason": self.reason,
        }


@dataclass
class ConsolidationResult:
    """
    整合结果
    """
    narrative_candidates: list[NarrativeCandidate] = field(default_factory=list)
    policy_candidates: list[PolicyCandidate] = field(default_factory=list)

    # 合并建议
    merge_suggestions: list[dict] = field(default_factory=list)

    # 置信度
    overall_confidence: float = 0.5

    # 原因
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "narrative_candidates": [n.to_dict() for n in self.narrative_candidates],
            "policy_candidates": [p.to_dict() for p in self.policy_candidates],
            "merge_suggestions": self.merge_suggestions,
            "overall_confidence": round(self.overall_confidence, 3),
            "reasons": self.reasons,
        }


class Consolidator:
    """
    记忆整合器

    职责: 从事件提炼叙事和策略候选
    """

    def __init__(self):
        # 叙事模式识别
        self.narrative_patterns = {
            "progress": ["完成", "成功", "实现", "达成", "搞定"],
            "regression": ["失败", "放弃", "倒退", "退步"],
            "conflict": ["冲突", "矛盾", "问题", "纠结"],
            "stable": ["继续", "维持", "保持"],
        }

        # 策略模式识别
        self.policy_patterns = {
            "preference": ["喜欢", "偏好", "更愿意", "倾向于"],
            "constraint": ["不要", "别", "禁止", "必须", "不能"],
            "rule": ["每次", "总是", "永远", "从不"],
        }

    def consolidate(
        self,
        event_dict: dict[str, Any],
        current_state: Any,  # LatentSelfState
        memory_gate_result: Any,  # MemoryGateResult
        existing_memories: Optional[dict] = None,
    ) -> ConsolidationResult:
        """
        执行记忆整合

        Args:
            event_dict: 事件数据
            current_state: 当前状态
            memory_gate_result: 记忆门决策结果
            existing_memories: 已有记忆（用于合并判断）

        Returns:
            ConsolidationResult: 整合结果
        """
        result = ConsolidationResult()

        event_type = event_dict.get("event_type", "unknown")
        event_content = event_dict.get("content", "")
        event_id = event_dict.get("event_id", "")

        # 1. 生成叙事候选
        if memory_gate_result.narrative_candidate:
            narrative = self._generate_narrative_candidate(
                event_dict, current_state, existing_memories
            )
            if narrative:
                result.narrative_candidates.append(narrative)
                result.reasons.append(f"生成叙事候选: {narrative.theme}")

        # 2. 生成策略候选
        if memory_gate_result.policy_candidate:
            policy = self._generate_policy_candidate(
                event_dict, current_state, event_id
            )
            if policy:
                result.policy_candidates.append(policy)
                result.reasons.append(f"生成策略候选: {policy.name}")

        # 3. 检查是否可以合并到已有记忆
        if existing_memories and result.narrative_candidates:
            result.merge_suggestions = self._check_merge_opportunities(
                result.narrative_candidates, existing_memories
            )

        # 4. 计算整体置信度
        result.overall_confidence = self._compute_overall_confidence(
            result.narrative_candidates, result.policy_candidates
        )

        return result

    def _generate_narrative_candidate(
        self,
        event_dict: dict[str, Any],
        current_state: Any,
        existing_memories: Optional[dict],
    ) -> Optional[NarrativeCandidate]:
        """
        生成叙事候选

        从事件中提取有意义的叙事结构
        """
        event_content = event_dict.get("content", "")
        event_type = event_dict.get("event_type", "")

        # 提取主题
        theme = self._extract_narrative_theme(event_content, event_type)
        if not theme:
            return None

        # 提取摘要
        summary = self._extract_summary(event_content)

        # 判断弧类型
        arc_type = self._infer_arc_type(event_content, event_type)

        # 计算置信度
        confidence = self._compute_narrative_confidence(event_content, arc_type)

        # 判断动作
        action = self._decide_narrative_action(event_type, existing_memories)

        return NarrativeCandidate(
            theme=theme,
            summary=summary,
            arc_type=arc_type,
            key_events=[event_dict.get("event_id", "")],
            start_time=datetime.now(timezone.utc),
            confidence=confidence,
            action=action,
            reason=f"从 {event_type} 事件提炼",
        )

    def _generate_policy_candidate(
        self,
        event_dict: dict[str, Any],
        current_state: Any,
        event_id: str,
    ) -> Optional[PolicyCandidate]:
        """
        生成策略候选

        从事件中提取偏好/约束
        """
        event_content = event_dict.get("content", "")
        event_type = event_dict.get("event_type", "")

        # 检测策略模式
        policy_type, description = self._detect_policy_pattern(event_content)
        if not policy_type:
            return None

        # 生成名称
        name = self._generate_policy_name(policy_type, description)

        # 提取触发条件
        triggers = self._extract_triggers(event_content)

        # 推断行为建议
        behavior = self._infer_behavior(policy_type, description)

        # 计算置信度
        confidence = self._compute_policy_confidence(event_content, policy_type)

        # 判断来源类型
        source_type = "explicit" if "我" in event_content else "inferred"

        return PolicyCandidate(
            policy_type=policy_type,
            name=name,
            description=description,
            triggers=triggers,
            behavior=behavior,
            source_event_id=event_id,
            source_type=source_type,
            confidence=confidence,
            action=ConsolidationAction.CREATE,
            reason=f"从事件中检测到明确的{policy_type}模式",
        )

    def _extract_narrative_theme(self, content: str, event_type: str) -> Optional[str]:
        """提取叙事主题"""
        # 基于事件类型
        type_themes = {
            "task_complete": "任务完成",
            "goal_set": "目标设定",
            "boundary_crossing": "边界突破",
            "world_event": "外部事件",
        }
        if event_type in type_themes:
            return type_themes[event_type]

        # 基于内容关键词
        theme_keywords = {
            "项目": "项目进展",
            "工作": "工作相关",
            "学习": "学习成长",
            "关系": "人际关系",
            "目标": "目标追求",
        }
        for keyword, theme in theme_keywords.items():
            if keyword in content:
                return theme

        return "一般事件"

    def _extract_summary(self, content: str, max_length: int = 100) -> str:
        """提取摘要"""
        # 简单截取
        if len(content) <= max_length:
            return content

        # 尝试找句号
        sentences = re.split(r'[。！？]', content)
        if sentences:
            return sentences[0][:max_length]

        return content[:max_length]

    def _infer_arc_type(self, content: str, event_type: str) -> str:
        """推断弧类型"""
        for arc_type, keywords in self.narrative_patterns.items():
            for keyword in keywords:
                if keyword in content:
                    return arc_type
        return "stable"

    def _detect_policy_pattern(self, content: str) -> tuple[Optional[str], Optional[str]]:
        """检测策略模式"""
        for policy_type, keywords in self.policy_patterns.items():
            for keyword in keywords:
                if keyword in content:
                    # 提取关键词后的描述
                    idx = content.find(keyword)
                    description = content[idx:idx+50]
                    return policy_type, description

        return None, None

    def _generate_policy_name(self, policy_type: str, description: str) -> str:
        """生成策略名称"""
        # 简化的命名规则
        if policy_type == "preference":
            return f"偏好_{hash(description) % 10000}"
        elif policy_type == "constraint":
            return f"约束_{hash(description) % 10000}"
        else:
            return f"规则_{hash(description) % 10000}"

    def _extract_triggers(self, content: str) -> list[str]:
        """提取触发条件"""
        triggers = []

        # 简单的关键词提取
        trigger_patterns = ["当", "如果", "遇到", "看到"]
        for pattern in trigger_patterns:
            if pattern in content:
                # 提取模式后的内容（简化）
                idx = content.find(pattern)
                trigger = content[idx:idx+30]
                triggers.append(trigger)

        return triggers

    def _infer_behavior(self, policy_type: str, description: str) -> str:
        """推断行为建议"""
        if policy_type == "preference":
            return "倾向于此方向"
        elif policy_type == "constraint":
            return "避免此方向"
        else:
            return "遵循此规则"

    def _compute_narrative_confidence(self, content: str, arc_type: str) -> float:
        """计算叙事置信度"""
        # 有明确弧类型时置信度高
        if arc_type != "stable":
            return 0.7

        # 内容长度加成
        if len(content) > 100:
            return 0.6

        return 0.5

    def _compute_policy_confidence(self, content: str, policy_type: str) -> float:
        """计算策略置信度"""
        # 显式表达时置信度高
        if policy_type == "constraint" and ("必须" in content or "不能" in content):
            return 0.85
        elif policy_type == "preference" and "喜欢" in content:
            return 0.75

        return 0.6

    def _decide_narrative_action(
        self,
        event_type: str,
        existing_memories: Optional[dict],
    ) -> ConsolidationAction:
        """决定叙事动作"""
        if not existing_memories:
            return ConsolidationAction.CREATE

        # 检查是否有同类叙事
        # 简化：总是建议创建新条目
        return ConsolidationAction.CREATE

    def _check_merge_opportunities(
        self,
        candidates: list[NarrativeCandidate],
        existing_memories: dict,
    ) -> list[dict]:
        """检查合并机会"""
        suggestions = []

        # 简化实现：检查主题相同
        existing_themes = existing_memories.get("themes", [])
        for candidate in candidates:
            if candidate.theme in existing_themes:
                suggestions.append({
                    "type": "merge",
                    "theme": candidate.theme,
                    "reason": "已存在相同主题的叙事",
                })

        return suggestions

    def _compute_overall_confidence(
        self,
        narrative_candidates: list[NarrativeCandidate],
        policy_candidates: list[PolicyCandidate],
    ) -> float:
        """计算整体置信度"""
        if not narrative_candidates and not policy_candidates:
            return 0.0

        confidences = []
        for n in narrative_candidates:
            confidences.append(n.confidence)
        for p in policy_candidates:
            confidences.append(p.confidence)

        return sum(confidences) / len(confidences)


# 默认实例
default_consolidator = Consolidator()


# 版本标记
CONSOLIDATION_V1_VERSION = "1.0.0"
