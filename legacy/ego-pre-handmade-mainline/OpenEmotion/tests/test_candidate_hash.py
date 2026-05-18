"""Tests for US-644 candidate parameter hashing."""

import pytest
from scripts.candidate_hash import (
    compute_candidate_param_hash,
    compute_threshold_config_hash,
    validate_report_hashes,
    annotate_report_with_hashes,
)


class TestCandidateParamHash:
    def test_compute_hash_basic(self):
        params = {"threshold": 0.5, "weight": 0.3}
        h = compute_candidate_param_hash(params)
        assert len(h) == 64  # SHA-256 hex
        assert h.isalnum()
    
    def test_hash_is_deterministic(self):
        params = {"a": 1, "b": 2}
        h1 = compute_candidate_param_hash(params)
        h2 = compute_candidate_param_hash(params)
        assert h1 == h2
    
    def test_hash_changes_with_values(self):
        params1 = {"a": 1}
        params2 = {"a": 2}
        assert compute_candidate_param_hash(params1) != compute_candidate_param_hash(params2)
    
    def test_hash_independent_of_key_order(self):
        params1 = {"a": 1, "b": 2}
        params2 = {"b": 2, "a": 1}
        assert compute_candidate_param_hash(params1) == compute_candidate_param_hash(params2)


class TestThresholdConfigHash:
    def test_compute_threshold_hash(self):
        config = {"version": "2.3.0", "thresholds": {"metric_a": 0.5}}
        h = compute_threshold_config_hash(config)
        assert len(h) == 64
    
    def test_threshold_hash_includes_version(self):
        config1 = {"version": "2.3.0", "thresholds": {"a": 0.5}}
        config2 = {"version": "2.4.0", "thresholds": {"a": 0.5}}
        assert compute_threshold_config_hash(config1) != compute_threshold_config_hash(config2)


class TestReportValidation:
    def test_validate_missing_threshold_hash(self):
        report = {"aggregate_metrics": {}}
        result = validate_report_hashes(report)
        assert not result["valid"]
        assert "missing_threshold_config_hash" in result["issues"]
    
    def test_validate_present_threshold_hash(self):
        report = {
            "aggregate_metrics": {
                "threshold_config": {"version": "2.3.0", "hash": "abc123"}
            }
        }
        result = validate_report_hashes(report)
        assert result["valid"]
    
    def test_validate_candidate_hash_mismatch(self):
        report = {
            "aggregate_metrics": {"threshold_config": {"hash": "abc"}},
            "candidate_param_hash": "wrong",
        }
        result = validate_report_hashes(
            report,
            expected_candidate_hash="correct",
        )
        assert not result["valid"]
        assert any("candidate_hash_mismatch" in i for i in result["issues"])


class TestReportAnnotation:
    def test_annotate_adds_threshold_hash(self):
        report = {}
        config = {"version": "2.3.0", "thresholds": {}}
        annotated = annotate_report_with_hashes(report, config)
        
        assert "aggregate_metrics" in annotated
        assert "threshold_config" in annotated["aggregate_metrics"]
        assert "hash" in annotated["aggregate_metrics"]["threshold_config"]
    
    def test_annotate_adds_candidate_hash(self):
        report = {}
        config = {"version": "2.3.0"}
        params = {"weight": 0.5}
        annotated = annotate_report_with_hashes(report, config, params)
        
        assert "candidate_param_hash" in annotated
    
    def test_annotate_adds_code_version(self):
        report = {}
        config = {}
        annotated = annotate_report_with_hashes(report, config)
        
        assert "code_version" in annotated
