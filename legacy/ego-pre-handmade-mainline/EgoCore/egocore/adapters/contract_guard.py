"""
Contract Guard - 契约版本兼容性检查

负责在运行时验证 schema 版本兼容性。
确保 contract 不会静默漂移。
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CompatibilityStatus(Enum):
    """兼容性状态"""
    COMPATIBLE = "compatible"
    INCOMPATIBLE_MAJOR = "incompatible_major"
    VERSION_MISSING = "version_missing"
    SCHEMA_NOT_FOUND = "schema_not_found"


@dataclass
class CompatibilityResult:
    """兼容性检查结果"""
    status: CompatibilityStatus
    schema_name: str
    expected_version: str
    received_version: Optional[str]
    message: str
    details: Optional[Dict[str, Any]] = None


class ContractGuard:
    """
    契约守卫

    在 adapter 处理事件前后进行版本兼容性检查。
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """
        初始化契约守卫

        Args:
            registry_path: registry.json 路径
        """
        self.registry_path = registry_path
        self.registry: Dict[str, Any] = {}

        if registry_path and registry_path.exists():
            self._load_registry()

    def _load_registry(self) -> None:
        """加载契约注册表"""
        with open(self.registry_path) as f:
            self.registry = json.load(f)

    def get_current_version(self, schema_name: str) -> Optional[str]:
        """
        获取 schema 的当前版本

        Args:
            schema_name: schema 名称

        Returns:
            当前版本号，如果不存在返回 None
        """
        contracts = self.registry.get("contracts", {})
        schema_info = contracts.get(schema_name, {})
        return schema_info.get("current_version")

    def get_compatible_versions(self, schema_name: str) -> List[str]:
        """
        获取 schema 的兼容版本列表

        Args:
            schema_name: schema 名称

        Returns:
            兼容版本列表
        """
        contracts = self.registry.get("contracts", {})
        schema_info = contracts.get(schema_name, {})
        return schema_info.get("compatible_versions", [])

    def check_compatibility(
        self,
        schema_name: str,
        version: Optional[str],
    ) -> CompatibilityResult:
        """
        检查版本兼容性

        Args:
            schema_name: schema 名称
            version: 待检查的版本号

        Returns:
            兼容性检查结果
        """
        # 检查 schema 是否存在
        contracts = self.registry.get("contracts", {})
        if schema_name not in contracts:
            return CompatibilityResult(
                status=CompatibilityStatus.SCHEMA_NOT_FOUND,
                schema_name=schema_name,
                expected_version="unknown",
                received_version=version,
                message=f"Schema '{schema_name}' not found in registry",
            )

        # 获取兼容版本列表
        compatible_versions = self.get_compatible_versions(schema_name)
        current_version = self.get_current_version(schema_name)

        # 检查版本是否缺失
        if version is None:
            return CompatibilityResult(
                status=CompatibilityStatus.VERSION_MISSING,
                schema_name=schema_name,
                expected_version=current_version or "unknown",
                received_version=None,
                message="Version field is missing",
            )

        # 检查版本兼容性（主版本号相同）
        try:
            expected_major = self._parse_major_version(current_version)
            received_major = self._parse_major_version(version)

            if expected_major != received_major:
                return CompatibilityResult(
                    status=CompatibilityStatus.INCOMPATIBLE_MAJOR,
                    schema_name=schema_name,
                    expected_version=current_version or "unknown",
                    received_version=version,
                    message=f"Major version mismatch: expected {expected_major}.x.x, got {received_major}.x.x",
                    details={
                        "expected_major": expected_major,
                        "received_major": received_major,
                    }
                )

        except ValueError as e:
            return CompatibilityResult(
                status=CompatibilityStatus.VERSION_MISSING,
                schema_name=schema_name,
                expected_version=current_version or "unknown",
                received_version=version,
                message=f"Invalid version format: {e}",
            )

        # 版本兼容
        return CompatibilityResult(
            status=CompatibilityStatus.COMPATIBLE,
            schema_name=schema_name,
            expected_version=current_version or "unknown",
            received_version=version,
            message="Version compatible",
        )

    def check_event_input(self, event: Dict[str, Any]) -> CompatibilityResult:
        """
        检查事件输入的版本兼容性

        Args:
            event: 事件字典

        Returns:
            兼容性检查结果
        """
        version = event.get("schema_version")
        return self.check_compatibility("event_input", version)

    def check_openemotion_output(self, output: Dict[str, Any]) -> CompatibilityResult:
        """
        检查 OpenEmotion 输出的版本兼容性

        Args:
            output: 输出字典

        Returns:
            兼容性检查结果
        """
        version = output.get("schema_version")
        return self.check_compatibility("openemotion_output", version)

    def validate_and_raise(self, result: CompatibilityResult) -> None:
        """
        验证兼容性，不兼容时抛出异常

        Args:
            result: 兼容性检查结果

        Raises:
            IncompatibleSchemaError: 版本不兼容
            MissingVersionError: 版本缺失
        """
        if result.status == CompatibilityStatus.COMPATIBLE:
            return

        if result.status == CompatibilityStatus.VERSION_MISSING:
            raise MissingVersionError(result.message)

        if result.status == CompatibilityStatus.INCOMPATIBLE_MAJOR:
            raise IncompatibleSchemaError(result.message)

        if result.status == CompatibilityStatus.SCHEMA_NOT_FOUND:
            raise SchemaNotFoundError(result.message)

    @staticmethod
    def _parse_major_version(version: Optional[str]) -> int:
        """
        解析主版本号

        Args:
            version: 版本字符串

        Returns:
            主版本号

        Raises:
            ValueError: 版本格式无效
        """
        if not version:
            raise ValueError("Version is None or empty")

        parts = version.split(".")
        if len(parts) < 1:
            raise ValueError(f"Invalid version format: {version}")

        return int(parts[0])


class ContractGuardError(Exception):
    """契约守卫错误基类"""
    pass


class IncompatibleSchemaError(ContractGuardError):
    """Schema 版本不兼容"""
    pass


class MissingVersionError(ContractGuardError):
    """版本字段缺失"""
    pass


class SchemaNotFoundError(ContractGuardError):
    """Schema 未找到"""
    pass


def create_guard(contracts_dir: Path) -> ContractGuard:
    """
    创建契约守卫实例

    Args:
        contracts_dir: 契约目录路径

    Returns:
        ContractGuard 实例
    """
    registry_path = contracts_dir / "registry.json"
    return ContractGuard(registry_path=registry_path)
