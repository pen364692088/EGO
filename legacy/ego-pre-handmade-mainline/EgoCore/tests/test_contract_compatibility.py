"""
Contract Compatibility Tests

测试契约版本兼容性检查。
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from egocore.adapters.contract_guard import (
    ContractGuard,
    CompatibilityStatus,
    CompatibilityResult,
    IncompatibleSchemaError,
    MissingVersionError,
    SchemaNotFoundError,
    create_guard,
)


@pytest.fixture
def mock_registry():
    """Mock registry 数据"""
    return {
        "contracts": {
            "event_input": {
                "current_version": "1.0.0",
                "compatible_versions": ["1.0.0"],
            },
            "openemotion_output": {
                "current_version": "1.0.0",
                "compatible_versions": ["1.0.0"],
            }
        }
    }


@pytest.fixture
def guard(mock_registry, tmp_path):
    """创建带 mock registry 的 guard"""
    registry_file = tmp_path / "registry.json"
    with open(registry_file, 'w') as f:
        json.dump(mock_registry, f)
    return ContractGuard(registry_path=registry_file)


class TestContractGuard:
    """ContractGuard 测试"""

    def test_get_current_version(self, guard):
        """测试获取当前版本"""
        version = guard.get_current_version("event_input")
        assert version == "1.0.0"

    def test_get_current_version_not_found(self, guard):
        """测试获取不存在的 schema 版本"""
        version = guard.get_current_version("unknown_schema")
        assert version is None

    def test_check_compatibility_compatible(self, guard):
        """测试兼容版本"""
        result = guard.check_compatibility("event_input", "1.0.0")
        assert result.status == CompatibilityStatus.COMPATIBLE
        assert result.received_version == "1.0.0"

    def test_check_compatibility_minor_version(self, guard):
        """测试次版本兼容（主版本相同）"""
        # 1.1.0 应该与 1.0.0 兼容（主版本相同）
        result = guard.check_compatibility("event_input", "1.1.0")
        assert result.status == CompatibilityStatus.COMPATIBLE

    def test_check_compatibility_incompatible_major(self, guard):
        """测试主版本不兼容"""
        result = guard.check_compatibility("event_input", "2.0.0")
        assert result.status == CompatibilityStatus.INCOMPATIBLE_MAJOR
        assert "Major version mismatch" in result.message

    def test_check_compatibility_version_missing(self, guard):
        """测试版本缺失"""
        result = guard.check_compatibility("event_input", None)
        assert result.status == CompatibilityStatus.VERSION_MISSING

    def test_check_compatibility_schema_not_found(self, guard):
        """测试 schema 不存在"""
        result = guard.check_compatibility("nonexistent", "1.0.0")
        assert result.status == CompatibilityStatus.SCHEMA_NOT_FOUND

    def test_check_event_input(self, guard):
        """测试事件输入检查"""
        event = {
            "schema_version": "1.0.0",
            "event_id": "evt_test",
        }
        result = guard.check_event_input(event)
        assert result.status == CompatibilityStatus.COMPATIBLE

    def test_check_event_input_missing_version(self, guard):
        """测试事件输入版本缺失"""
        event = {
            "event_id": "evt_test",
            # 没有 schema_version
        }
        result = guard.check_event_input(event)
        assert result.status == CompatibilityStatus.VERSION_MISSING

    def test_check_openemotion_output(self, guard):
        """测试 OpenEmotion 输出检查"""
        output = {
            "schema_version": "1.0.0",
            "output_id": "out_test",
        }
        result = guard.check_openemotion_output(output)
        assert result.status == CompatibilityStatus.COMPATIBLE

    def test_validate_and_raise_compatible(self, guard):
        """测试验证通过"""
        result = CompatibilityResult(
            status=CompatibilityStatus.COMPATIBLE,
            schema_name="test",
            expected_version="1.0.0",
            received_version="1.0.0",
            message="OK",
        )
        # 不应抛出异常
        guard.validate_and_raise(result)

    def test_validate_and_raise_incompatible(self, guard):
        """测试验证失败抛出异常"""
        result = CompatibilityResult(
            status=CompatibilityStatus.INCOMPATIBLE_MAJOR,
            schema_name="test",
            expected_version="1.0.0",
            received_version="2.0.0",
            message="Major version mismatch",
        )
        with pytest.raises(IncompatibleSchemaError):
            guard.validate_and_raise(result)

    def test_validate_and_raise_missing_version(self, guard):
        """测试版本缺失抛出异常"""
        result = CompatibilityResult(
            status=CompatibilityStatus.VERSION_MISSING,
            schema_name="test",
            expected_version="1.0.0",
            received_version=None,
            message="Version missing",
        )
        with pytest.raises(MissingVersionError):
            guard.validate_and_raise(result)

    def test_validate_and_raise_schema_not_found(self, guard):
        """测试 schema 不存在抛出异常"""
        result = CompatibilityResult(
            status=CompatibilityStatus.SCHEMA_NOT_FOUND,
            schema_name="test",
            expected_version="unknown",
            received_version="1.0.0",
            message="Schema not found",
        )
        with pytest.raises(SchemaNotFoundError):
            guard.validate_and_raise(result)


class TestParseMajorVersion:
    """主版本号解析测试"""

    def test_parse_major_version_valid(self, guard):
        """测试有效版本解析"""
        assert guard._parse_major_version("1.0.0") == 1
        assert guard._parse_major_version("2.1.3") == 2
        assert guard._parse_major_version("10.0.0") == 10

    def test_parse_major_version_invalid(self, guard):
        """测试无效版本解析"""
        with pytest.raises(ValueError):
            guard._parse_major_version("")

        with pytest.raises(ValueError):
            guard._parse_major_version(None)

        with pytest.raises(ValueError):
            guard._parse_major_version("invalid")


class TestCreateGuard:
    """create_guard 工厂函数测试"""

    def test_create_guard(self, tmp_path):
        """测试创建 guard"""
        registry_file = tmp_path / "registry.json"
        registry_file.write_text('{"contracts": {}}')

        guard = create_guard(tmp_path)
        assert isinstance(guard, ContractGuard)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
