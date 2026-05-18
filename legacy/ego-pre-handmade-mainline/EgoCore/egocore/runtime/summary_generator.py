"""
Summary Generator - 长期自我摘要生成器

负责生成、刷新、验证 long-term self summary。
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SummaryAction(Enum):
    """摘要动作"""
    CREATED = "created"
    REFRESHED = "refreshed"
    UPDATED = "updated"
    VERIFIED = "verified"


class SummaryError(Exception):
    """摘要错误基类"""
    pass


class ValidationFailedError(SummaryError):
    """验证失败"""
    pass


class AlignmentError(SummaryError):
    """对齐错误"""
    pass


@dataclass
class SummaryAuditRecord:
    """摘要审计记录"""
    timestamp: str
    action: str
    authorized: bool
    trigger: str
    changes_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SummaryGenerator:
    """
    长期自我摘要生成器

    职责：
    1. 从 identity invariants 和 self-model 生成摘要
    2. 验证一致性
    3. 刷新过期内容
    4. 记录审计轨迹
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
    ):
        """
        初始化摘要生成器

        Args:
            output_dir: 摘要输出目录
            audit_dir: 审计记录目录
        """
        self.output_dir = output_dir or Path("./artifacts/summary")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir = audit_dir or Path("./artifacts/summary/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self._summary: Optional[Dict[str, Any]] = None

    def generate(
        self,
        identity_invariants: Dict[str, Any],
        self_model: Dict[str, Any],
        recent_events: Optional[List[Dict[str, Any]]] = None,
        stable_conclusions: Optional[List[Dict[str, Any]]] = None,
        open_questions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        生成摘要

        Args:
            identity_invariants: 身份不变量
            self_model: 自我模型
            recent_events: 近期事件列表
            stable_conclusions: 稳定结论列表
            open_questions: 开放问题列表

        Returns:
            生成的摘要
        """
        now = datetime.now(timezone.utc)

        summary = {
            "schema_version": "1.0.0",
            "summary_id": f"summary_{now.strftime('%Y%m%d_%H%M%S')}",
            "identity_handle_ref": identity_invariants.get("identity_handle"),
            "summary_created_at": now.isoformat(),
            "summary_period_start": now.isoformat(),
            "summary_period_end": now.isoformat(),
            "identity_summary": self._extract_identity_summary(identity_invariants),
            "current_phase_summary": self._extract_phase_summary(self_model),
            "capability_summary": self._extract_capability_summary(self_model),
            "constraint_summary": self._extract_constraint_summary(identity_invariants, self_model),
            "active_commitments_summary": self._extract_commitments_summary(identity_invariants),
            "recent_key_events_summary": self._compress_events(recent_events or []),
            "stable_conclusions": stable_conclusions or [],
            "open_questions": open_questions or [],
            "self_model_version_ref": {
                "model_handle": self_model.get("model_handle"),
                "snapshot_timestamp": self_model.get("last_modified_at"),
            },
            "recovery_hints": self._generate_recovery_hints(self_model),
            "last_modified_at": now.isoformat(),
            "modification_audit_trail": [
                SummaryAuditRecord(
                    timestamp=now.isoformat(),
                    action=SummaryAction.CREATED.value,
                    authorized=True,
                    trigger="manual_generation",
                    changes_summary="初始生成",
                ).to_dict()
            ],
        }

        self._summary = summary
        self._save_summary()
        self._save_audit_record(summary["modification_audit_trail"][0])

        return summary

    def refresh(
        self,
        existing_summary: Dict[str, Any],
        identity_invariants: Dict[str, Any],
        self_model: Dict[str, Any],
        recent_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        刷新摘要

        Args:
            existing_summary: 现有摘要
            identity_invariants: 身份不变量
            self_model: 自我模型
            recent_events: 近期事件

        Returns:
            刷新后的摘要
        """
        now = datetime.now(timezone.utc)

        # 检查对齐
        alignment_issues = self._check_alignment(existing_summary, identity_invariants, self_model)

        # 更新摘要
        updated = existing_summary.copy()
        updated["summary_period_end"] = now.isoformat()
        updated["identity_summary"] = self._extract_identity_summary(identity_invariants)
        updated["current_phase_summary"] = self._extract_phase_summary(self_model)
        updated["capability_summary"] = self._extract_capability_summary(self_model)
        updated["constraint_summary"] = self._extract_constraint_summary(identity_invariants, self_model)
        updated["recent_key_events_summary"] = self._merge_events(
            existing_summary.get("recent_key_events_summary", []),
            recent_events or []
        )
        updated["self_model_version_ref"] = {
            "model_handle": self_model.get("model_handle"),
            "snapshot_timestamp": self_model.get("last_modified_at"),
        }
        updated["recovery_hints"] = self._generate_recovery_hints(self_model)
        updated["last_modified_at"] = now.isoformat()

        # 添加审计记录
        audit_record = SummaryAuditRecord(
            timestamp=now.isoformat(),
            action=SummaryAction.REFRESHED.value,
            authorized=True,
            trigger="periodic_refresh",
            changes_summary=f"刷新摘要，对齐问题: {len(alignment_issues)}",
        ).to_dict()
        updated["modification_audit_trail"].append(audit_record)

        self._summary = updated
        self._save_summary()
        self._save_audit_record(audit_record)

        return updated

    def verify_alignment(
        self,
        summary: Dict[str, Any],
        identity_invariants: Dict[str, Any],
        self_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        验证对齐

        Args:
            summary: 摘要
            identity_invariants: 身份不变量
            self_model: 自我模型

        Returns:
            验证结果
        """
        issues = self._check_alignment(summary, identity_invariants, self_model)

        return {
            "aligned": len(issues) == 0,
            "issues": issues,
            "summary_id": summary.get("summary_id"),
        }

    def _extract_identity_summary(self, identity: Dict[str, Any]) -> Dict[str, Any]:
        """提取身份摘要"""
        return {
            "core_name": identity.get("core_name", ""),
            "core_role": identity.get("core_role", ""),
            "primary_owner": identity.get("owner_relationship", {}).get("owner_id", ""),
            "identity_stability_note": "身份稳定" if identity else "未知",
        }

    def _extract_phase_summary(self, self_model: Dict[str, Any]) -> Dict[str, Any]:
        """提取阶段摘要"""
        goals = self_model.get("active_goals", [])
        active_goals = [g for g in goals if g.get("status") == "in_progress"]

        return {
            "phase_name": "开发阶段" if active_goals else "待机阶段",
            "phase_start": datetime.now(timezone.utc).isoformat(),
            "primary_focus": active_goals[0].get("description", "") if active_goals else "",
            "key_activities": [g.get("description", "") for g in active_goals[:5]],
            "progress_indicators": {
                g.get("goal_id", ""): g.get("progress", 0)
                for g in active_goals
            },
        }

    def _extract_capability_summary(self, self_model: Dict[str, Any]) -> Dict[str, Any]:
        """提取能力摘要"""
        capabilities = self_model.get("capabilities", [])
        limitations = self_model.get("limitations", [])

        strong = [c for c in capabilities if c.get("current_level") in ["advanced", "expert"]]
        developing = [c for c in capabilities if c.get("current_level") in ["basic", "intermediate"]]

        return {
            "strong_domains": [c.get("category", "") for c in strong],
            "developing_domains": [c.get("category", "") for c in developing],
            "known_limitations": [l.get("description", "") for l in limitations],
            "capability_trend": "growing" if len(strong) > len(developing) else "stable",
        }

    def _extract_constraint_summary(
        self,
        identity: Dict[str, Any],
        self_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """提取约束摘要"""
        commitments = identity.get("non_negotiable_commitments", [])
        hard = [c.get("description", "") for c in commitments if c.get("binding_level") == "absolute"]

        return {
            "hard_constraints": hard,
            "soft_constraints": [],
            "temporary_constraints": [],
        }

    def _extract_commitments_summary(self, identity: Dict[str, Any]) -> Dict[str, Any]:
        """提取承诺摘要"""
        commitments = identity.get("non_negotiable_commitments", [])

        return {
            "standing_commitments": [c.get("description", "") for c in commitments],
            "recent_new_commitments": [],
            "commitments_fulfilled": [],
        }

    def _compress_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """压缩事件列表"""
        # 最多保留 20 条，按重要性排序
        sorted_events = sorted(
            events,
            key=lambda e: {"high": 0, "medium": 1, "low": 2}.get(e.get("significance", "low"), 2)
        )
        return sorted_events[:20]

    def _merge_events(
        self,
        existing: List[Dict[str, Any]],
        new: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """合并事件列表"""
        combined = existing + new
        # 去重并保留最新的
        seen = set()
        unique = []
        for event in reversed(combined):
            key = event.get("summary", "")
            if key not in seen:
                seen.add(key)
                unique.append(event)
        return self._compress_events(list(reversed(unique)))

    def _generate_recovery_hints(self, self_model: Dict[str, Any]) -> Dict[str, Any]:
        """生成恢复提示"""
        goals = self_model.get("active_goals", [])
        pending = [g for g in goals if g.get("status") in ["proposed", "in_progress", "blocked"]]

        return {
            "last_active_context": goals[0].get("description", "") if goals else "",
            "suggested_start_actions": ["检查身份和自我模型状态"],
            "pending_tasks": [g.get("description", "") for g in pending[:5]],
        }

    def _check_alignment(
        self,
        summary: Dict[str, Any],
        identity: Dict[str, Any],
        self_model: Dict[str, Any],
    ) -> List[str]:
        """检查对齐"""
        issues = []

        # 检查 identity_handle 对齐
        if summary.get("identity_handle_ref") != identity.get("identity_handle"):
            issues.append("identity_handle_ref 不匹配")

        # 检查 core_role 对齐
        summary_role = summary.get("identity_summary", {}).get("core_role")
        identity_role = identity.get("core_role")
        if summary_role and identity_role and summary_role != identity_role:
            issues.append("identity_summary.core_role 不匹配")

        # 检查 self_model 引用
        model_ref = summary.get("self_model_version_ref", {})
        if model_ref.get("model_handle") != self_model.get("model_handle"):
            issues.append("self_model_version_ref 不匹配")

        return issues

    def _save_summary(self) -> None:
        """保存摘要"""
        if not self._summary:
            return

        output_file = self.output_dir / f"{self._summary['summary_id']}.json"
        with open(output_file, 'w') as f:
            json.dump(self._summary, f, indent=2)

    def _save_audit_record(self, record: Dict[str, Any]) -> None:
        """保存审计记录"""
        now = datetime.now(timezone.utc)
        audit_file = self.audit_dir / f"audit_{now.strftime('%Y%m%d_%H%M%S')}.json"
        with open(audit_file, 'w') as f:
            json.dump(record, f, indent=2)
