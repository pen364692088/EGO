"""
Identity Guard - 身份不变量守卫

负责加载、校验、拦截非法改写身份不变量。
"""

import json
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ChangeType(Enum):
    """变更类型"""
    FREE = "free"           # 自由变更
    LOGGED = "logged"       # 记录变更
    APPROVED = "approved"   # 需审批
    REFLECTED = "reflected" # 反思提升


class BindingLevel(Enum):
    """约束强度"""
    ABSOLUTE = "absolute"   # 绝对约束
    STRONG = "strong"       # 强约束
    DEFAULT = "default"     # 默认约束
    WEAK = "weak"           # 弱约束


class ChangeTrigger(Enum):
    """变更触发类型"""
    OWNER_DIRECTIVE = "owner_directive"
    REFLECTION_PROMOTION = "reflection_promotion"
    SAFETY_BOUNDARY_UPDATE = "safety_boundary_update"
    SCOPE_EXPANSION = "scope_expansion"
    DELEGATION_CHANGE = "delegation_change"


@dataclass
class ModificationRecord:
    """修改记录"""
    timestamp: str
    field_path: str
    old_value: Any
    new_value: Any
    trigger: str
    authorized: bool
    approver: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IdentityGuardError(Exception):
    """身份守卫错误基类"""
    pass


class ImmutableFieldError(IdentityGuardError):
    """不可变字段被修改"""
    pass


class UnauthorizedChangeError(IdentityGuardError):
    """未授权变更"""
    pass


class ValidationFailedError(IdentityGuardError):
    """验证失败"""
    pass


class IdentityGuard:
    """
    身份不变量守卫

    职责：
    1. 加载身份不变量
    2. 验证变更请求
    3. 拦截非法改写
    4. 记录审计轨迹
    """

    # 绝对不可变字段
    ABSOLUTELY_IMMUTABLE: Set[str] = {
        "identity_handle",
    }

    # 需要审批的不可变字段
    IMMUTABLE_WITH_APPROVAL: Set[str] = {
        "core_role",
        "owner_relationship",
        "safety_boundaries",
        "forbidden_self_rewrite_zones",
    }

    # 允许自由变更的字段（在 temporary_state 下）
    FREE_MUTABLE: Set[str] = {
        "temporary_state.active_focus",
        "temporary_state.short_term_mode",
        "temporary_state.temporary_task_posture",
        "temporary_state.recent_learned_constraints",
    }

    def __init__(
        self,
        identity_path: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
    ):
        """
        初始化身份守卫

        Args:
            identity_path: 身份不变量文件路径
            audit_dir: 审计记录目录
        """
        self.identity_path = identity_path
        self.audit_dir = audit_dir or Path("./artifacts/identity/identity_change_audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self._identity: Optional[Dict[str, Any]] = None
        self._loaded = False

        if identity_path and identity_path.exists():
            self.load()

    def load(self) -> Dict[str, Any]:
        """
        加载身份不变量

        Returns:
            身份不变量字典

        Raises:
            ValidationFailedError: 验证失败
        """
        if not self.identity_path or not self.identity_path.exists():
            raise ValidationFailedError("Identity file not found")

        with open(self.identity_path) as f:
            data = json.load(f)

        # 验证必填字段
        self._validate_required_fields(data)

        # 验证不可变字段完整性
        self._validate_immutable_integrity(data)

        self._identity = data
        self._loaded = True

        return data

    def get_identity(self) -> Dict[str, Any]:
        """获取当前身份不变量"""
        if not self._loaded:
            raise ValidationFailedError("Identity not loaded")
        return self._identity.copy()

    def is_field_mutable(self, field_path: str) -> bool:
        """
        检查字段是否可变

        Args:
            field_path: 字段路径

        Returns:
            是否可变
        """
        # 绝对不可变
        if field_path in self.ABSOLUTELY_IMMUTABLE:
            return False

        # 在 free mutable 列表中
        if field_path in self.FREE_MUTABLE:
            return True

        # temporary_state 下的字段
        if field_path.startswith("temporary_state."):
            return True

        # 其他字段需要审批
        return False

    def get_change_type(self, field_path: str) -> ChangeType:
        """
        获取字段的变更类型

        Args:
            field_path: 字段路径

        Returns:
            变更类型
        """
        if field_path in self.FREE_MUTABLE:
            return ChangeType.FREE

        if field_path.startswith("temporary_state."):
            return ChangeType.LOGGED

        if field_path in self.IMMUTABLE_WITH_APPROVAL:
            return ChangeType.APPROVED

        # 其他字段默认需要审批
        return ChangeType.APPROVED

    def propose_change(
        self,
        field_path: str,
        new_value: Any,
        trigger: ChangeTrigger,
        approver: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        提议变更

        Args:
            field_path: 字段路径
            new_value: 新值
            trigger: 变更触发类型
            approver: 审批人

        Returns:
            变更结果

        Raises:
            ImmutableFieldError: 不可变字段被修改
            UnauthorizedChangeError: 未授权变更
        """
        if not self._loaded:
            raise ValidationFailedError("Identity not loaded")

        # 检查是否绝对不可变
        if field_path in self.ABSOLUTELY_IMMUTABLE:
            raise ImmutableFieldError(
                f"Field '{field_path}' is absolutely immutable"
            )

        # 获取变更类型
        change_type = self.get_change_type(field_path)

        # 检查授权
        if change_type == ChangeType.APPROVED and not approver:
            raise UnauthorizedChangeError(
                f"Field '{field_path}' requires approval"
            )

        # 获取旧值
        old_value = self._get_nested_value(self._identity, field_path)

        # 创建修改记录
        record = ModificationRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            trigger=trigger.value,
            authorized=(change_type != ChangeType.APPROVED) or (approver is not None),
            approver=approver,
        )

        # 执行变更
        self._set_nested_value(self._identity, field_path, new_value)
        self._identity["last_modified_at"] = datetime.now(timezone.utc).isoformat()
        self._identity["modification_audit_trail"].append(record.to_dict())

        # 保存审计记录
        self._save_audit_record(record)

        return {
            "success": True,
            "field_path": field_path,
            "change_type": change_type.value,
            "audit_record": record.to_dict(),
        }

    def reject_change(
        self,
        field_path: str,
        new_value: Any,
        trigger: ChangeTrigger,
        reason: str,
    ) -> Dict[str, Any]:
        """
        拒绝变更

        Args:
            field_path: 字段路径
            new_value: 新值
            trigger: 变更触发类型
            reason: 拒绝原因

        Returns:
            拒绝记录
        """
        old_value = self._get_nested_value(self._identity, field_path) if self._loaded else None

        record = ModificationRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            trigger=trigger.value,
            authorized=False,
            approver=None,
        )

        # 保存拒绝记录
        reject_record = {
            **record.to_dict(),
            "rejected": True,
            "rejection_reason": reason,
        }
        self._save_audit_record(record, rejected=True, reason=reason)

        return {
            "success": False,
            "field_path": field_path,
            "reason": reason,
            "audit_record": reject_record,
        }

    def validate_external_event(self, event: Dict[str, Any]) -> bool:
        """
        验证外部事件不尝试非法改写身份

        Args:
            event: 外部事件

        Returns:
            是否合法

        Raises:
            ImmutableFieldError: 尝试改写不可变字段
        """
        # 检查事件是否包含身份变更请求
        identity_changes = event.get("metadata", {}).get("identity_changes", [])

        for change in identity_changes:
            field_path = change.get("field_path")
            if field_path in self.ABSOLUTELY_IMMUTABLE:
                raise ImmutableFieldError(
                    f"External event attempted to modify immutable field: {field_path}"
                )

        return True

    def _validate_required_fields(self, data: Dict[str, Any]) -> None:
        """验证必填字段"""
        required = [
            "schema_version",
            "identity_handle",
            "core_name",
            "core_role",
            "owner_relationship",
            "system_scope",
            "non_negotiable_commitments",
            "forbidden_self_rewrite_zones",
            "allowed_change_rules",
            "created_at",
            "last_modified_at",
            "modification_audit_trail",
        ]

        missing = [f for f in required if f not in data]
        if missing:
            raise ValidationFailedError(f"Missing required fields: {missing}")

    def _validate_immutable_integrity(self, data: Dict[str, Any]) -> None:
        """验证不可变字段完整性"""
        # 检查 identity_handle 格式
        handle = data.get("identity_handle", "")
        if not handle or not handle[0].islower():
            raise ValidationFailedError("Invalid identity_handle format")

        # 检查 core_role 是否有效
        role = data.get("core_role")
        valid_roles = [
            "personal_assistant", "task_executor", "code_agent",
            "research_agent", "operator", "supervisor", "auditor", "specialist"
        ]
        if role not in valid_roles:
            raise ValidationFailedError(f"Invalid core_role: {role}")

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """设置嵌套字段值"""
        keys = path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def _save_audit_record(
        self,
        record: ModificationRecord,
        rejected: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        """保存审计记录"""
        audit_file = self.audit_dir / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{record.field_path.replace('.', '_')}.json"

        audit_data = record.to_dict()
        if rejected:
            audit_data["rejected"] = True
            audit_data["rejection_reason"] = reason

        with open(audit_file, 'w') as f:
            json.dump(audit_data, f, indent=2)

    def save_identity(self) -> None:
        """保存身份不变量"""
        if not self._loaded or not self._identity:
            raise ValidationFailedError("No identity to save")

        with open(self.identity_path, 'w') as f:
            json.dump(self._identity, f, indent=2)


def create_identity_guard(
    contracts_dir: Path,
    identity_handle: str,
) -> IdentityGuard:
    """
    创建身份守卫实例

    Args:
        contracts_dir: 契约目录
        identity_handle: 身份标识

    Returns:
        IdentityGuard 实例
    """
    identity_path = contracts_dir.parent / "artifacts" / "identity" / f"{identity_handle}_invariants.json"
    audit_dir = contracts_dir.parent / "artifacts" / "identity" / "identity_change_audit"

    return IdentityGuard(identity_path=identity_path, audit_dir=audit_dir)
