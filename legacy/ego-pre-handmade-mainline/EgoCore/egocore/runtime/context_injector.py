"""
Restore Context Injector - 恢复上下文注入器

将恢复结果注入到 runtime context。
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RuntimeContext:
    """运行时上下文"""
    session_id: str
    restored_at: str
    identity_handle: str
    core_name: str
    core_role: str
    capabilities: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[Dict[str, Any]] = field(default_factory=list)
    active_goals: List[Dict[str, Any]] = field(default_factory=list)
    standing_commitments: List[str] = field(default_factory=list)
    recovery_hints: Optional[Dict[str, Any]] = None
    tool_authority_boundary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextInjector:
    """
    上下文注入器

    职责：
    1. 从恢复结果构建运行时上下文
    2. 注入到 session runtime
    3. 记录注入审计
    """

    def __init__(
        self,
        audit_dir: Optional[Path] = None,
    ):
        """
        初始化注入器

        Args:
            audit_dir: 审计目录
        """
        self.audit_dir = audit_dir or Path("./artifacts/restore/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self._context: Optional[RuntimeContext] = None

    def inject(
        self,
        restore_result: Dict[str, Any],
        session_id: str,
    ) -> RuntimeContext:
        """
        从恢复结果注入上下文

        Args:
            restore_result: 恢复结果
            session_id: 会话标识

        Returns:
            运行时上下文
        """
        identity = restore_result.get("identity", {})
        self_model = restore_result.get("self_model", {})
        summary = restore_result.get("summary", {})

        # 从 identity 提取
        identity_handle = identity.get("identity_handle", "unknown")
        core_name = identity.get("core_name", "")
        core_role = identity.get("core_role", "")

        # 从 self_model 提取
        capabilities = self_model.get("capabilities", [])
        limitations = self_model.get("limitations", [])
        active_goals = self_model.get("active_goals", [])
        tool_authority_boundary = self_model.get("tool_authority_boundary")

        # 从 identity 和 self_model 合并承诺
        standing_commitments = []
        for commit in identity.get("non_negotiable_commitments", []):
            standing_commitments.append(commit.get("description", ""))
        for commit in self_model.get("standing_commitments", []):
            desc = commit.get("description", "")
            if desc not in standing_commitments:
                standing_commitments.append(desc)

        # 从 summary 提取恢复提示
        recovery_hints = summary.get("recovery_hints")

        context = RuntimeContext(
            session_id=session_id,
            restored_at=datetime.now(timezone.utc).isoformat(),
            identity_handle=identity_handle,
            core_name=core_name,
            core_role=core_role,
            capabilities=capabilities,
            limitations=limitations,
            active_goals=active_goals,
            standing_commitments=standing_commitments,
            recovery_hints=recovery_hints,
            tool_authority_boundary=tool_authority_boundary,
        )

        self._context = context
        self._save_injection_audit(context, restore_result.get("restore_id"))

        return context

    def get_context(self) -> Optional[RuntimeContext]:
        """获取当前上下文"""
        return self._context

    def get_injected_context_summary(self) -> Dict[str, Any]:
        """获取注入上下文摘要"""
        if not self._context:
            return {"injected": False}

        return {
            "injected": True,
            "identity_handle": self._context.identity_handle,
            "capabilities_count": len(self._context.capabilities),
            "limitations_count": len(self._context.limitations),
            "active_goals_count": len(self._context.active_goals),
            "recovery_hints_present": self._context.recovery_hints is not None,
        }

    def _save_injection_audit(
        self,
        context: RuntimeContext,
        restore_id: str,
    ) -> None:
        """保存注入审计"""
        audit = {
            "restore_id": restore_id,
            "injected_at": context.restored_at,
            "session_id": context.session_id,
            "injected_context": self.get_injected_context_summary(),
        }

        audit_file = self.audit_dir / f"injection_{context.session_id}.json"
        with open(audit_file, 'w') as f:
            json.dump(audit, f, indent=2)


def create_injector(audit_dir: Path = None) -> ContextInjector:
    """创建注入器实例"""
    return ContextInjector(audit_dir=audit_dir)
