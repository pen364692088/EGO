"""
Replay Regression Tests

测试重放回归套件。
"""

import pytest
import json
from pathlib import Path

from egocore.adapters.openemotion_adapter import OpenEmotionAdapter, AdapterMode
from tools.replay_regression import (
    ReplayRegression,
    CANONICAL_CASES,
    run_regression,
)


@pytest.fixture
def adapter():
    """创建测试用 adapter"""
    return OpenEmotionAdapter(mode=AdapterMode.MOCK)


@pytest.fixture
def artifacts_dir(tmp_path):
    """创建临时 artifact 目录"""
    return tmp_path / "replay_regression"


class TestCanonicalCases:
    """Canonical Cases 测试"""

    def test_canonical_cases_count(self):
        """测试 canonical cases 数量 >= 5"""
        assert len(CANONICAL_CASES) >= 5

    def test_canonical_cases_have_required_fields(self):
        """测试 canonical cases 有必需字段"""
        for case in CANONICAL_CASES:
            assert case.case_id
            assert case.description
            assert case.fixed_input
            assert case.expected_keys
            assert case.assertions

    def test_canonical_cases_fixed_input_has_schema_version(self):
        """测试 canonical cases 输入有 schema_version"""
        for case in CANONICAL_CASES:
            assert "schema_version" in case.fixed_input


class TestReplayRegression:
    """ReplayRegression 测试"""

    def test_run_all_passes(self, adapter, artifacts_dir):
        """测试所有 case 通过"""
        suite = ReplayRegression(artifacts_dir=artifacts_dir)
        report = suite.run_all(adapter)

        assert report["total_cases"] == 5
        assert report["status"] == "PASS"
        assert report["failed"] == 0

    def test_artifacts_created(self, adapter, artifacts_dir):
        """测试 artifact 文件创建"""
        suite = ReplayRegression(artifacts_dir=artifacts_dir)
        suite.run_all(adapter)

        # 检查报告文件
        report_file = artifacts_dir / "REPLAY_REGRESSION_REPORT.json"
        assert report_file.exists()

        # 检查各 case 文件
        for case in CANONICAL_CASES:
            case_file = artifacts_dir / f"{case.case_id}.json"
            assert case_file.exists()

    def test_output_has_expected_keys(self, adapter, artifacts_dir):
        """测试输出有期望的键"""
        suite = ReplayRegression(artifacts_dir=artifacts_dir)
        results = suite.run_all(adapter)

        for case_result in results["cases"]:
            if case_result["status"] == "PASS":
                output = case_result["output"]
                case_id = case_result["case_id"]

                # 查找对应的 case
                case = next(c for c in CANONICAL_CASES if c.case_id == case_id)

                for key in case.expected_keys:
                    assert key in output, f"Case {case_id}: Missing key {key}"

    def test_event_id_ref_correct(self, adapter, artifacts_dir):
        """测试 event_id_ref 正确"""
        suite = ReplayRegression(artifacts_dir=artifacts_dir)
        results = suite.run_all(adapter)

        for case_result in results["cases"]:
            output = case_result["output"]
            case_id = case_result["case_id"]

            case = next(c for c in CANONICAL_CASES if c.case_id == case_id)
            expected_event_id = case.fixed_input["event_id"]

            assert output["event_id_ref"] == expected_event_id

    def test_confidence_metadata_present(self, adapter, artifacts_dir):
        """测试 confidence_metadata 存在"""
        suite = ReplayRegression(artifacts_dir=artifacts_dir)
        results = suite.run_all(adapter)

        for case_result in results["cases"]:
            output = case_result["output"]

            assert "confidence_metadata" in output
            assert "overall_confidence" in output["confidence_metadata"]

    def test_run_regression_convenience_function(self, adapter, artifacts_dir):
        """测试便捷函数"""
        report = run_regression(adapter, artifacts_dir=artifacts_dir)

        assert "total_cases" in report
        assert "passed" in report
        assert "failed" in report


class TestRegressioStability:
    """回归稳定性测试"""

    def test_same_input_same_output_structure(self, adapter):
        """测试相同输入产生相同结构"""
        suite = ReplayRegression()

        case = CANONICAL_CASES[0]

        # 运行两次
        result1 = adapter.process_event(case.fixed_input)
        result2 = adapter.process_event(case.fixed_input)

        # 检查结构相同（值可能不同，如 output_id）
        assert set(result1.keys()) == set(result2.keys())

    def test_mock_mode_stability(self, adapter):
        """测试 mock 模式稳定性"""
        suite = ReplayRegression()

        for case in CANONICAL_CASES:
            output = adapter.process_event(case.fixed_input)

            # 检查关键字段存在
            assert "output_id" in output
            assert "event_id_ref" in output
            assert "confidence_metadata" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
