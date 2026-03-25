"""
OpenEmotion Long-Term Self Summary Module

长期自我摘要的正式本体模块。
负责摘要生成、刷新、一致性校验。

此模块是 long-term self summary 的唯一权威源。
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class KeyEvent:
    """关键事件"""
    event_type: str
    summary: str
    significance: str
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StableConclusion:
    """稳定结论"""
    conclusion_id: str
    statement: str
    confidence: float
    basis: str
    formed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpenQuestion:
    """开放问题"""
    question_id: str
    question: str
    priority: str
    blocking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryHints:
    """恢复提示"""
    last_active_context: str
    suggested_start_actions: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LongTermSelfSummary:
    """
    长期自我摘要本体

    这是系统摘要的唯一权威定义。
    所有字段语义的解释权归 OpenEmotion。
    """

    # 摘要标识
    summary_id: str
    identity_handle: str

    # 时间范围
    summary_created_at: str
    summary_period_start: str
    summary_period_end: str

    # 身份摘要
    core_name: str
    core_role: str
    primary_owner: str
    identity_stability_note: str = "身份稳定"

    # 当前阶段摘要
    phase_name: str = "未定义"
    primary_focus: str = ""
    key_activities: List[str] = field(default_factory=list)
    progress_indicators: Dict[str, float] = field(default_factory=dict)

    # 能力摘要
    strong_domains: List[str] = field(default_factory=list)
    developing_domains: List[str] = field(default_factory=list)
    known_limitations: List[str] = field(default_factory=list)
    capability_trend: str = "stable"

    # 约束摘要
    hard_constraints: List[str] = field(default_factory=list)
    soft_constraints: List[str] = field(default_factory=list)
    temporary_constraints: List[str] = field(default_factory=list)

    # 承诺摘要
    standing_commitments: List[str] = field(default_factory=list)
    recent_new_commitments: List[str] = field(default_factory=list)
    commitments_fulfilled: List[str] = field(default_factory=list)

    # 关键事件（压缩表示）
    recent_key_events: List[KeyEvent] = field(default_factory=list)

    # 稳定结论
    stable_conclusions: List[StableConclusion] = field(default_factory=list)

    # 开放问题
    open_questions: List[OpenQuestion] = field(default_factory=list)

    # 恢复提示
    recovery_hints: Optional[RecoveryHints] = None

    # 元数据
    last_modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "summary_id": self.summary_id,
            "identity_handle": self.identity_handle,
            "summary_created_at": self.summary_created_at,
            "summary_period_start": self.summary_period_start,
            "summary_period_end": self.summary_period_end,
            "identity_summary": {
                "core_name": self.core_name,
                "core_role": self.core_role,
                "primary_owner": self.primary_owner,
                "identity_stability_note": self.identity_stability_note,
            },
            "current_phase_summary": {
                "phase_name": self.phase_name,
                "primary_focus": self.primary_focus,
                "key_activities": self.key_activities,
                "progress_indicators": self.progress_indicators,
            },
            "capability_summary": {
                "strong_domains": self.strong_domains,
                "developing_domains": self.developing_domains,
                "known_limitations": self.known_limitations,
                "capability_trend": self.capability_trend,
            },
            "constraint_summary": {
                "hard_constraints": self.hard_constraints,
                "soft_constraints": self.soft_constraints,
                "temporary_constraints": self.temporary_constraints,
            },
            "active_commitments_summary": {
                "standing_commitments": self.standing_commitments,
                "recent_new_commitments": self.recent_new_commitments,
                "commitments_fulfilled": self.commitments_fulfilled,
            },
            "recent_key_events": [e.to_dict() for e in self.recent_key_events[:20]],  # 最多 20 条
            "stable_conclusions": [c.to_dict() for c in self.stable_conclusions],
            "open_questions": [q.to_dict() for q in self.open_questions],
            "last_modified_at": self.last_modified_at,
        }
        if self.recovery_hints:
            result["recovery_hints"] = self.recovery_hints.to_dict()
        return result


def generate_summary(
    identity: Dict[str, Any],
    self_model: Dict[str, Any],
    recent_events: List[Dict[str, Any]] = None,
) -> LongTermSelfSummary:
    """
    从 identity 和 self-model 生成摘要

    这是摘要生成的唯一正式入口。
    """
    now = datetime.now(timezone.utc)

    # 提取能力摘要
    capabilities = self_model.get("capabilities", [])
    strong = [c.get("category", "") for c in capabilities if c.get("current_level") in ["advanced", "expert"]]
    developing = [c.get("category", "") for c in capabilities if c.get("current_level") in ["basic", "intermediate"]]

    # 提取限制
    limitations = self_model.get("limitations", [])
    limitation_descs = [l.get("description", "") for l in limitations]

    # 提取目标
    goals = self_model.get("active_goals", [])
    active_goals = [g for g in goals if g.get("status") == "in_progress"]

    # 提取承诺
    commitments = identity.get("non_negotiable_commitments", [])
    commitment_descs = [c.get("description", "") for c in commitments]

    # 压缩事件
    key_events = []
    for event in (recent_events or [])[:20]:
        key_events.append(KeyEvent(
            event_type=event.get("event_type", "unknown"),
            summary=event.get("summary", ""),
            significance=event.get("significance", "medium"),
            timestamp=event.get("timestamp"),
        ))

    # 生成恢复提示
    recovery_hints = RecoveryHints(
        last_active_context=active_goals[0].get("description", "") if active_goals else "",
        suggested_start_actions=["检查身份和自我模型状态"],
        pending_tasks=[g.get("description", "") for g in active_goals[:5]],
    )

    return LongTermSelfSummary(
        summary_id=f"summary_{now.strftime('%Y%m%d_%H%M%S')}_{identity.get('identity_handle', 'unknown')}",
        identity_handle=identity.get("identity_handle", "unknown"),
        summary_created_at=now.isoformat(),
        summary_period_start=now.isoformat(),
        summary_period_end=now.isoformat(),
        core_name=identity.get("core_name", ""),
        core_role=identity.get("core_role", ""),
        primary_owner=identity.get("owner_relationship", {}).get("owner_id", ""),
        phase_name="开发阶段" if active_goals else "待机阶段",
        primary_focus=active_goals[0].get("description", "") if active_goals else "",
        key_activities=[g.get("description", "") for g in active_goals[:5]],
        progress_indicators={g.get("goal_id", ""): g.get("progress", 0) for g in active_goals},
        strong_domains=strong,
        developing_domains=developing,
        known_limitations=limitation_descs,
        capability_trend="growing" if len(strong) > len(developing) else "stable",
        hard_constraints=commitment_descs,
        standing_commitments=commitment_descs,
        recent_key_events=key_events,
        recovery_hints=recovery_hints,
    )
