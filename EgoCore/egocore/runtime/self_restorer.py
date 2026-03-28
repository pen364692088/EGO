"""
Self Restorer - 自我恢复器

负责新会话启动时的主体恢复流程。
加载三层、校验一致性、处理冲突。
"""

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class RestoreStatus(Enum):
    """恢复状态"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ConflictLevel(Enum):
    """冲突级别"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Conflict:
    """冲突记录"""
    type: str
    level: str
    description: str
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RestoreResult:
    """恢复结果"""
    restore_id: str
    timestamp: str
    session_id: str
    status: str
    loaded_layers: List[str]
    identity: Optional[Dict[str, Any]] = None
    self_model: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    degraded_mode: bool = False
    degradation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "schema_version": "1.0.0",
            "restore_id": self.restore_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "status": self.status,
            "loaded_layers": self.loaded_layers,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "degraded_mode": self.degraded_mode,
        }
        if self.degradation_reason:
            result["degradation_reason"] = self.degradation_reason
        if self.identity:
            result["identity_ref"] = {
                "identity_handle": self.identity.get("identity_handle"),
                "loaded_at": self.timestamp,
            }
        if self.self_model:
            result["self_model_ref"] = {
                "model_handle": self.self_model.get("model_handle"),
                "loaded_at": self.timestamp,
            }
        if self.summary:
            result["summary_ref"] = {
                "summary_id": self.summary.get("summary_id"),
                "loaded_at": self.timestamp,
            }
        return result


class RestoreError(Exception):
    """恢复错误基类"""
    pass


class IdentityNotFoundError(RestoreError):
    """身份文件不存在"""
    pass


class ConsistencyError(RestoreError):
    """一致性错误"""
    pass


class SelfRestorer:
    """
    自我恢复器

    职责：
    1. 加载三层持久化文件
    2. 校验三层一致性
    3. 处理冲突
    4. 返回恢复结果
    """

    def __init__(
        self,
        artifacts_dir: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
    ):
        """
        初始化恢复器

        Args:
            artifacts_dir: artifacts 目录
            audit_dir: 审计记录目录
        """
        self.artifacts_dir = artifacts_dir or Path("./artifacts")
        self.audit_dir = audit_dir or self.artifacts_dir / "restore" / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def restore(
        self,
        session_id: Optional[str] = None,
    ) -> RestoreResult:
        """
        执行恢复

        Args:
            session_id: 会话标识

        Returns:
            恢复结果
        """
        start_time = datetime.now(timezone.utc)
        restore_id = f"restore_{start_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        loaded_layers: List[str] = []
        conflicts: List[Dict[str, Any]] = []
        warnings: List[str] = []
        errors: List[str] = []

        identity = None
        self_model = None
        summary = None
        degraded_mode = False
        degradation_reason = None

        # Step 1: 加载 Identity Invariants
        try:
            identity = self._load_identity()
            loaded_layers.append("identity")
        except Exception as e:
            errors.append(f"Failed to load identity: {e}")
            # Identity 缺失是致命错误
            return self._create_failed_result(
                restore_id, session_id, start_time, errors, conflicts, warnings
            )

        # Step 2: 加载 Self-Model
        try:
            self_model = self._load_self_model()
            loaded_layers.append("self_model")
        except FileNotFoundError:
            warnings.append("Self-model file not found, using degraded mode")
            degraded_mode = True
            degradation_reason = "self_model_missing"
        except Exception as e:
            warnings.append(f"Failed to load self-model: {e}")
            degraded_mode = True
            degradation_reason = f"self_model_error: {e}"

        # Step 3: 加载 Summary
        if not degraded_mode:
            try:
                summary = self._load_summary()
                loaded_layers.append("summary")
            except FileNotFoundError:
                warnings.append("Summary file not found, skipping summary restore")
            except Exception as e:
                warnings.append(f"Failed to load summary: {e}")

        # Step 4: 校验一致性
        if identity and self_model:
            model_conflicts = self._check_identity_model_consistency(identity, self_model)
            conflicts.extend(model_conflicts)

        if identity and summary:
            summary_conflicts = self._check_identity_summary_consistency(identity, summary)
            conflicts.extend(summary_conflicts)

        if self_model and summary:
            model_summary_conflicts = self._check_model_summary_consistency(self_model, summary)
            conflicts.extend(model_summary_conflicts)

        # Step 5: 处理冲突
        error_conflicts = [c for c in conflicts if c.get("level") == "error"]
        if error_conflicts:
            errors.extend([c.get("description", "") for c in error_conflicts])

        # 确定状态
        if errors:
            status = RestoreStatus.FAILED.value
        elif degraded_mode or warnings or conflicts:
            status = RestoreStatus.PARTIAL.value
        else:
            status = RestoreStatus.SUCCESS.value

        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        result = RestoreResult(
            restore_id=restore_id,
            timestamp=start_time.isoformat(),
            session_id=session_id,
            status=status,
            loaded_layers=loaded_layers,
            identity=identity,
            self_model=self_model,
            summary=summary,
            conflicts=conflicts,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
            degraded_mode=degraded_mode,
            degradation_reason=degradation_reason,
        )

        # 保存审计
        self._save_audit(result)

        return result

    def _load_identity(self) -> Dict[str, Any]:
        """加载 Identity Invariants"""
        identity_file = self.artifacts_dir / "identity" / "ceo_invariants_snapshot.json"
        if not identity_file.exists():
            raise IdentityNotFoundError(f"Identity file not found: {identity_file}")

        with open(identity_file) as f:
            return json.load(f)

    def _load_self_model(self) -> Dict[str, Any]:
        """加载 Self-Model"""
        model_file = self.artifacts_dir / "self_model" / "ceo_self_model_snapshot.json"
        if not model_file.exists():
            raise FileNotFoundError(f"Self-model file not found: {model_file}")

        with open(model_file) as f:
            return json.load(f)

    def _load_summary(self) -> Dict[str, Any]:
        """加载 Summary"""
        # 查找最新的 summary 文件
        summary_dir = self.artifacts_dir / "summary"
        summary_files = list(summary_dir.glob("summary_*.json"))

        if not summary_files:
            raise FileNotFoundError("No summary files found")

        # 按修改时间排序，取最新的
        summary_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = summary_files[0]

        with open(latest) as f:
            return json.load(f)

    def _check_identity_model_consistency(
        self,
        identity: Dict[str, Any],
        self_model: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """检查 Identity 与 Self-Model 一致性"""
        conflicts = []

        # 检查 model_handle 与 identity_handle
        if self_model.get("model_handle") != identity.get("identity_handle"):
            conflicts.append(Conflict(
                type="identity_model_mismatch",
                level=ConflictLevel.ERROR.value,
                description=f"model_handle ({self_model.get('model_handle')}) != identity_handle ({identity.get('identity_handle')})",
                resolution="Use identity_handle as source of truth",
            ).to_dict())

        return conflicts

    def _check_identity_summary_consistency(
        self,
        identity: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """检查 Identity 与 Summary 一致性"""
        conflicts = []

        # 检查 identity_handle_ref
        if summary.get("identity_handle_ref") != identity.get("identity_handle"):
            conflicts.append(Conflict(
                type="identity_summary_mismatch",
                level=ConflictLevel.ERROR.value,
                description=f"identity_handle_ref ({summary.get('identity_handle_ref')}) != identity_handle ({identity.get('identity_handle')})",
                resolution="Use identity_handle as source of truth",
            ).to_dict())

        # 检查 core_role
        summary_role = summary.get("identity_summary", {}).get("core_role")
        identity_role = identity.get("core_role")
        if summary_role and identity_role and summary_role != identity_role:
            conflicts.append(Conflict(
                type="role_mismatch",
                level=ConflictLevel.WARNING.value,
                description=f"Summary core_role ({summary_role}) != identity core_role ({identity_role})",
                resolution="Use identity.core_role as source of truth",
            ).to_dict())

        return conflicts

    def _check_model_summary_consistency(
        self,
        self_model: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """检查 Self-Model 与 Summary 一致性"""
        conflicts = []

        model_ref = summary.get("self_model_version_ref", {})
        if model_ref.get("model_handle") != self_model.get("model_handle"):
            conflicts.append(Conflict(
                type="model_summary_mismatch",
                level=ConflictLevel.WARNING.value,
                description=f"Summary model_handle ({model_ref.get('model_handle')}) != self_model model_handle ({self_model.get('model_handle')})",
                resolution="Use self_model as source of truth",
            ).to_dict())

        return conflicts

    def _create_failed_result(
        self,
        restore_id: str,
        session_id: str,
        start_time: datetime,
        errors: List[str],
        conflicts: List[Dict[str, Any]],
        warnings: List[str],
    ) -> RestoreResult:
        """创建失败结果"""
        end_time = datetime.now(timezone.utc)
        result = RestoreResult(
            restore_id=restore_id,
            timestamp=start_time.isoformat(),
            session_id=session_id,
            status=RestoreStatus.FAILED.value,
            loaded_layers=[],
            conflicts=conflicts,
            warnings=warnings,
            errors=errors,
            duration_ms=(end_time - start_time).total_seconds() * 1000,
        )
        self._save_audit(result)
        return result

    def _save_audit(self, result: RestoreResult) -> None:
        """保存审计记录"""
        audit_file = self.audit_dir / f"{result.restore_id}.json"
        with open(audit_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)


def create_restorer(artifacts_dir: Path) -> SelfRestorer:
    """创建恢复器实例"""
    return SelfRestorer(artifacts_dir=artifacts_dir)
