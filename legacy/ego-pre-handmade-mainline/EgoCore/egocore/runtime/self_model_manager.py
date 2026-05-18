"""
Self-Model Manager - 自我模型管理器

负责加载、校验、更新、审计 self-model。
确保与 identity invariants 对齐。
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ChangeType(Enum):
    """变更类型"""
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"
    STATUS_CHANGE = "status_change"


class SelfModelError(Exception):
    """Self-Model 错误基类"""
    pass


class ValidationFailedError(SelfModelError):
    """验证失败"""
    pass


class IdentityAlignmentError(SelfModelError):
    """Identity 对齐错误"""
    pass


class UnauthorizedUpdateError(SelfModelError):
    """未授权更新"""
    pass


class SelfModelManager:
    """
    Self-Model 管理器

    职责：
    1. 加载 self-model
    2. 验证字段完整性
    3. 检查与 identity invariants 对齐
    4. 管理更新与审计
    """

    # 可自由更新的字段
    FREE_UPDATABLE: Set[str] = {
        "current_mode",
        "active_goals",
        "confidence_by_domain",
    }

    # 需要记录审计的更新字段
    LOGGED_UPDATABLE: Set[str] = {
        "capabilities",
        "limitations",
        "dependency_map",
        "known_unknowns",
    }

    # 需要对齐 identity invariants 的字段
    IDENTITY_ALIGNED: Set[str] = {
        "standing_commitments",
        "tool_authority_boundary",
    }

    def __init__(
        self,
        self_model_path: Optional[Path] = None,
        identity_guard=None,
        audit_dir: Optional[Path] = None,
    ):
        """
        初始化 Self-Model 管理器

        Args:
            self_model_path: self-model 文件路径
            identity_guard: IdentityGuard 实例（用于对齐检查）
            audit_dir: 审计记录目录
        """
        self.self_model_path = self_model_path
        self.identity_guard = identity_guard
        self.audit_dir = audit_dir or Path("./artifacts/self_model/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self._model: Optional[Dict[str, Any]] = None
        self._loaded = False

        if self_model_path and self_model_path.exists():
            self.load()

    def load(self) -> Dict[str, Any]:
        """加载 self-model"""
        if not self.self_model_path or not self.self_model_path.exists():
            raise ValidationFailedError("Self-model file not found")

        with open(self.self_model_path) as f:
            data = json.load(f)

        self._validate_required_fields(data)
        self._model = data
        self._loaded = True

        return data

    def get_model(self) -> Dict[str, Any]:
        """获取当前 self-model"""
        if not self._loaded:
            raise ValidationFailedError("Self-model not loaded")
        return self._model.copy()

    def update_field(
        self,
        field_path: str,
        new_value: Any,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        """
        更新字段

        Args:
            field_path: 字段路径
            new_value: 新值
            trigger: 触发来源

        Returns:
            更新结果
        """
        if not self._loaded:
            raise ValidationFailedError("Self-model not loaded")

        # 检查字段是否可更新
        top_field = field_path.split(".")[0]
        if top_field not in self.FREE_UPDATABLE and top_field not in self.LOGGED_UPDATABLE:
            if top_field in self.IDENTITY_ALIGNED:
                raise UnauthorizedUpdateError(
                    f"Field '{field_path}' requires identity alignment check"
                )
            raise UnauthorizedUpdateError(
                f"Field '{field_path}' is not updatable"
            )

        # 获取旧值
        old_value = self._get_nested_value(self._model, field_path)

        # 执行更新
        self._set_nested_value(self._model, field_path, new_value)
        self._model["last_modified_at"] = datetime.now(timezone.utc).isoformat()

        # 记录审计
        audit_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "field_path": field_path,
            "change_type": self._determine_change_type(old_value, new_value),
            "old_value": old_value,
            "new_value": new_value,
            "authorized": True,
            "trigger": trigger,
        }
        self._model["modification_audit_trail"].append(audit_record)
        self._save_audit_record(audit_record)

        return {
            "success": True,
            "field_path": field_path,
            "audit_record": audit_record,
        }

    def add_capability(self, capability: Dict[str, Any]) -> Dict[str, Any]:
        """添加能力"""
        if "capabilities" not in self._model:
            self._model["capabilities"] = []

        self._model["capabilities"].append(capability)
        self._record_audit("capabilities", None, capability, ChangeType.ADD)
        return {"success": True, "capability_id": capability.get("capability_id")}

    def update_capability_level(
        self,
        capability_id: str,
        new_level: str,
    ) -> Dict[str, Any]:
        """更新能力等级"""
        for cap in self._model.get("capabilities", []):
            if cap.get("capability_id") == capability_id:
                old_level = cap.get("current_level")
                cap["current_level"] = new_level
                self._record_audit(
                    f"capabilities[{capability_id}].current_level",
                    old_level,
                    new_level,
                    ChangeType.UPDATE
                )
                return {"success": True}

        raise ValidationFailedError(f"Capability '{capability_id}' not found")

    def add_limitation(self, limitation: Dict[str, Any]) -> Dict[str, Any]:
        """添加限制"""
        if "limitations" not in self._model:
            self._model["limitations"] = []

        self._model["limitations"].append(limitation)
        self._record_audit("limitations", None, limitation, ChangeType.ADD)
        return {"success": True, "limitation_id": limitation.get("limitation_id")}

    def add_goal(self, goal: Dict[str, Any]) -> Dict[str, Any]:
        """添加目标"""
        if "active_goals" not in self._model:
            self._model["active_goals"] = []

        goal["created_at"] = datetime.now(timezone.utc).isoformat()
        self._model["active_goals"].append(goal)
        self._record_audit("active_goals", None, goal, ChangeType.ADD)
        return {"success": True, "goal_id": goal.get("goal_id")}

    def update_goal_status(
        self,
        goal_id: str,
        new_status: str,
    ) -> Dict[str, Any]:
        """更新目标状态"""
        for goal in self._model.get("active_goals", []):
            if goal.get("goal_id") == goal_id:
                old_status = goal.get("status")
                goal["status"] = new_status
                self._record_audit(
                    f"active_goals[{goal_id}].status",
                    old_status,
                    new_status,
                    ChangeType.STATUS_CHANGE
                )
                return {"success": True}

        raise ValidationFailedError(f"Goal '{goal_id}' not found")

    def check_identity_alignment(self) -> Dict[str, Any]:
        """检查与 identity invariants 对齐"""
        if not self.identity_guard:
            return {"aligned": True, "warnings": ["No identity guard provided"]}

        warnings = []
        identity = self.identity_guard.get_identity()

        # 检查 model_handle 对齐
        if self._model.get("model_handle") != identity.get("identity_handle"):
            warnings.append("model_handle does not match identity_handle")

        # 检查 tool_authority_boundary
        identity_forbidden = set(
            identity.get("tool_authority_boundary", {}).get("forbidden_tools", [])
        )
        self_allowed = set(
            self._model.get("tool_authority_boundary", {}).get("current_allowed_tools", [])
        )
        if identity_forbidden & self_allowed:
            warnings.append(
                f"Self-model allows forbidden tools: {identity_forbidden & self_allowed}"
            )

        # 检查 standing_commitments 引用
        for commit in self._model.get("standing_commitments", []):
            if commit.get("source") == "identity_invariants":
                commit_id = commit.get("commitment_id")
                identity_commits = [
                    c.get("commitment_id")
                    for c in identity.get("non_negotiable_commitments", [])
                ]
                if commit_id not in identity_commits:
                    warnings.append(
                        f"Standing commitment '{commit_id}' not found in identity invariants"
                    )

        return {
            "aligned": len(warnings) == 0,
            "warnings": warnings,
        }

    def _validate_required_fields(self, data: Dict[str, Any]) -> None:
        """验证必填字段"""
        required = [
            "schema_version",
            "model_handle",
            "capabilities",
            "limitations",
            "active_goals",
            "standing_commitments",
            "tool_authority_boundary",
            "dependency_map",
            "confidence_by_domain",
            "known_unknowns",
            "created_at",
            "last_modified_at",
            "modification_audit_trail",
        ]

        missing = [f for f in required if f not in data]
        if missing:
            raise ValidationFailedError(f"Missing required fields: {missing}")

    def _record_audit(
        self,
        field_path: str,
        old_value: Any,
        new_value: Any,
        change_type: ChangeType,
    ) -> None:
        """记录审计"""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "field_path": field_path,
            "change_type": change_type.value,
            "old_value": old_value,
            "new_value": new_value,
            "authorized": True,
            "trigger": "self_model_update",
        }
        self._model["modification_audit_trail"].append(record)
        self._save_audit_record(record)

    def _save_audit_record(self, record: Dict[str, Any]) -> None:
        """保存审计记录"""
        audit_file = self.audit_dir / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{record['field_path'].replace('.', '_').replace('[', '_').replace(']', '')}.json"
        with open(audit_file, 'w') as f:
            json.dump(record, f, indent=2)

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.replace("]", "").replace("[", ".").split(".")
        value = data
        for key in keys:
            if key == "":
                continue
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif isinstance(value, list):
                try:
                    idx = int(key)
                    value = value[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return value

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """设置嵌套字段值"""
        keys = path.replace("]", "").replace("[", ".").split(".")
        current = data
        for key in keys[:-1]:
            if key == "":
                continue
            if isinstance(current, dict):
                if key not in current:
                    current[key] = {}
                current = current[key]
        current[keys[-1]] = value

    def _determine_change_type(self, old_value: Any, new_value: Any) -> str:
        """确定变更类型"""
        if old_value is None:
            return ChangeType.ADD.value
        return ChangeType.UPDATE.value

    def save_model(self) -> None:
        """保存 self-model"""
        if not self._loaded or not self._model:
            raise ValidationFailedError("No model to save")

        with open(self.self_model_path, 'w') as f:
            json.dump(self._model, f, indent=2)
