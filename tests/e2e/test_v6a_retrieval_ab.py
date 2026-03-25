"""
Tests for v6a A/B Retrieval Evaluation.

Gate C validation: A/B results must match reported metrics.
"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestV6aReportExists:
    """Test that v6a A/B report exists and is valid."""
    
    def test_ab_report_file_exists(self):
        """ab_report.json must exist."""
        report_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/ab_report.json"
        assert report_path.exists(), f"Report not found at {report_path}"
    
    def test_ab_report_valid_json(self):
        """ab_report.json must be valid JSON."""
        report_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/ab_report.json"
        with open(report_path, "r") as f:
            data = json.load(f)
        
        assert "providers" in data
        assert "verdict" in data
    
    def test_config_snapshot_exists(self):
        """config_snapshot.json must exist."""
        config_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/config_snapshot.json"
        assert config_path.exists(), f"Config snapshot not found at {config_path}"


class TestV6aTfidfMetrics:
    """Test TF-IDF metrics match reported values."""
    
    @pytest.fixture
    def ab_report(self):
        """Load A/B report."""
        report_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/ab_report.json"
        with open(report_path, "r") as f:
            return json.load(f)
    
    def test_tfidf_hit_at_1(self, ab_report):
        """TF-IDF hit@1 should be 0.4 (40%)."""
        tfidf = ab_report["providers"]["tfidf"]
        assert tfidf["hit_at_1"] == 0.4
    
    def test_tfidf_hit_at_3(self, ab_report):
        """TF-IDF hit@3 should be 0.8 (80%)."""
        tfidf = ab_report["providers"]["tfidf"]
        assert tfidf["hit_at_3"] == 0.8
    
    def test_tfidf_wrong_user_recall(self, ab_report):
        """TF-IDF wrong_user_recall_count should be 4."""
        tfidf = ab_report["providers"]["tfidf"]
        assert tfidf["wrong_user_recall_count"] == 4
    
    def test_tfidf_latency_sub_millisecond(self, ab_report):
        """TF-IDF latency should be < 1ms."""
        tfidf = ab_report["providers"]["tfidf"]
        assert tfidf["avg_latency_ms"] < 1.0


class TestV6aOllamaMetrics:
    """Test Ollama metrics match reported values."""
    
    @pytest.fixture
    def ab_report(self):
        """Load A/B report."""
        report_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/ab_report.json"
        with open(report_path, "r") as f:
            return json.load(f)
    
    def test_ollama_hit_at_1(self, ab_report):
        """Ollama hit@1 should be 0.6 (60%)."""
        ollama = ab_report["providers"]["ollama"]
        assert ollama["hit_at_1"] == 0.6
    
    def test_ollama_hit_at_3(self, ab_report):
        """Ollama hit@3 should be 1.0 (100%)."""
        ollama = ab_report["providers"]["ollama"]
        assert ollama["hit_at_3"] == 1.0
    
    def test_ollama_wrong_user_recall(self, ab_report):
        """Ollama wrong_user_recall_count should be 3."""
        ollama = ab_report["providers"]["ollama"]
        assert ollama["wrong_user_recall_count"] == 3
    
    def test_ollama_vector_dim_1024(self, ab_report):
        """Ollama vector dimension should be 1024."""
        # Vector dim is not in report directly, but model is
        ollama = ab_report["providers"]["ollama"]
        assert ollama["model"] == "mxbai-embed-large"
    
    def test_ollama_latency_acceptable(self, ab_report):
        """Ollama latency should be < 200ms."""
        ollama = ab_report["providers"]["ollama"]
        assert ollama["avg_latency_ms"] < 200.0


class TestV6aVerdict:
    """Test v6a verdict is correct."""
    
    @pytest.fixture
    def ab_report(self):
        """Load A/B report."""
        report_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/ab_report.json"
        with open(report_path, "r") as f:
            return json.load(f)
    
    def test_verdict_is_better(self, ab_report):
        """Verdict should be 'better'."""
        assert ab_report["verdict"] == "better"
    
    def test_ollama_hit_at_1_greater_than_tfidf(self, ab_report):
        """Ollama hit@1 should be greater than TF-IDF."""
        tfidf = ab_report["providers"]["tfidf"]["hit_at_1"]
        ollama = ab_report["providers"]["ollama"]["hit_at_1"]
        assert ollama > tfidf
    
    def test_ollama_hit_at_3_greater_than_tfidf(self, ab_report):
        """Ollama hit@3 should be greater than or equal to TF-IDF."""
        tfidf = ab_report["providers"]["tfidf"]["hit_at_3"]
        ollama = ab_report["providers"]["ollama"]["hit_at_3"]
        assert ollama >= tfidf
    
    def test_no_wrong_user_regression(self, ab_report):
        """Ollama wrong_user_recall should not be worse than TF-IDF."""
        tfidf = ab_report["providers"]["tfidf"]["wrong_user_recall_count"]
        ollama = ab_report["providers"]["ollama"]["wrong_user_recall_count"]
        assert ollama <= tfidf


class TestV6aConfigSnapshot:
    """Test config snapshot is correct."""
    
    @pytest.fixture
    def config_snapshot(self):
        """Load config snapshot."""
        config_path = Path(__file__).parent.parent.parent / "artifacts/eval/v6a/config_snapshot.json"
        with open(config_path, "r") as f:
            return json.load(f)
    
    def test_provider_is_tfidf(self, config_snapshot):
        """Default provider should be tfidf."""
        assert config_snapshot["embedding"]["provider"] == "tfidf"
    
    def test_fallback_is_tfidf(self, config_snapshot):
        """Fallback provider should be tfidf."""
        assert config_snapshot["embedding"]["fallback_provider"] == "tfidf"
    
    def test_ollama_model_is_mxbai(self, config_snapshot):
        """Ollama model should be mxbai-embed-large."""
        assert config_snapshot["embedding"]["ollama_model"] == "mxbai-embed-large"
    
    def test_ollama_vector_dim_1024(self, config_snapshot):
        """Ollama vector dimension should be 1024."""
        assert config_snapshot["provider_health"]["ollama"]["vector_dim"] == 1024


class TestV6aCapabilityOwnership:
    """Test capability ownership is correct."""
    
    def test_embedding_in_openemotion(self):
        """Embedding module must be under emotiond (OpenEmotion), not EgoCore."""
        base_path = Path(__file__).parent.parent.parent / "emotiond/memory/embedding"
        assert base_path.exists()
    
    def test_contracts_file_exists(self):
        """contracts.py must exist."""
        contracts_path = Path(__file__).parent.parent.parent / "emotiond/memory/embedding/contracts.py"
        assert contracts_path.exists()
    
    def test_tfidf_provider_exists(self):
        """tfidf_provider.py must exist."""
        provider_path = Path(__file__).parent.parent.parent / "emotiond/memory/embedding/providers/tfidf_provider.py"
        assert provider_path.exists()
    
    def test_ollama_provider_exists(self):
        """ollama_provider.py must exist."""
        provider_path = Path(__file__).parent.parent.parent / "emotiond/memory/embedding/providers/ollama_provider.py"
        assert provider_path.exists()
