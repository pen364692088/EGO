"""
MVP-10 T24: Evidence Battery Tests

Tests for evidence_battery.py:
- Workspace: broadcast_dependency, cross_module_access_score
- HOT: prediction_error↓, conflict_resolution_efficiency
- Valence: policy_sensitivity
- Continuity: commitment_completion, narrative_consistency
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.evidence_battery import (
    EvidenceCategory,
    MetricResult,
    CategoryEvidence,
    WorkspaceEvidence,
    HOTEvidence,
    ValenceEvidence,
    ContinuityEvidence,
    EvidenceBattery,
    create_evidence_battery,
)


class TestEvidenceCategory:
    """Test EvidenceCategory enum."""
    
    def test_categories_exist(self):
        """Test that required categories exist."""
        assert EvidenceCategory.WORKSPACE.value == "workspace"
        assert EvidenceCategory.HOT.value == "hot"
        assert EvidenceCategory.VALENCE.value == "valence"
        assert EvidenceCategory.CONTINUITY.value == "continuity"


class TestMetricResult:
    """Test MetricResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a MetricResult."""
        result = MetricResult(
            metric_name="test_metric",
            category=EvidenceCategory.WORKSPACE,
            value=0.7,
            baseline_value=0.5,
            direction="higher_better",
        )
        
        assert result.metric_name == "test_metric"
        assert result.value == 0.7
        assert result.baseline_value == 0.5
    
    def test_compute_delta(self):
        """Test computing delta from baseline."""
        result = MetricResult(
            metric_name="test",
            category=EvidenceCategory.WORKSPACE,
            value=0.7,
            baseline_value=0.5,
        )
        
        delta = result.compute_delta()
        
        assert delta == pytest.approx(0.2, rel=0.01)
    
    def test_compute_evidence_strength_higher_better(self):
        """Test evidence strength computation for higher_better."""
        result = MetricResult(
            metric_name="test",
            category=EvidenceCategory.WORKSPACE,
            value=0.8,
            baseline_value=0.5,
            direction="higher_better",
        )
        
        strength = result.compute_evidence_strength()
        
        # Positive delta should give positive strength
        assert strength > 0
    
    def test_compute_evidence_strength_lower_better(self):
        """Test evidence strength computation for lower_better."""
        result = MetricResult(
            metric_name="test",
            category=EvidenceCategory.HOT,
            value=0.2,
            baseline_value=0.5,
            direction="lower_better",
        )
        
        strength = result.compute_evidence_strength()
        
        # Negative delta should give positive strength for lower_better
        assert strength > 0
    
    def test_result_to_dict(self):
        """Test MetricResult serialization."""
        result = MetricResult(
            metric_name="test",
            category=EvidenceCategory.WORKSPACE,
            value=0.7,
        )
        
        d = result.to_dict()
        
        assert d["metric_name"] == "test"
        assert d["category"] == "workspace"
        assert d["value"] == 0.7


class TestCategoryEvidence:
    """Test CategoryEvidence dataclass."""
    
    def test_category_creation(self):
        """Test creating a CategoryEvidence."""
        cat = CategoryEvidence(category=EvidenceCategory.WORKSPACE)
        
        assert cat.category == EvidenceCategory.WORKSPACE
        assert len(cat.metrics) == 0
    
    def test_compute_overall_score(self):
        """Test computing overall score."""
        cat = CategoryEvidence(
            category=EvidenceCategory.WORKSPACE,
            metrics=[
                MetricResult(
                    metric_name="m1",
                    category=EvidenceCategory.WORKSPACE,
                    value=0.7,
                    evidence_strength=0.6,
                ),
                MetricResult(
                    metric_name="m2",
                    category=EvidenceCategory.WORKSPACE,
                    value=0.8,
                    evidence_strength=0.8,
                ),
            ],
        )
        
        score = cat.compute_overall_score()
        
        assert score == 0.7  # Average of 0.6 and 0.8
    
    def test_category_to_dict(self):
        """Test CategoryEvidence serialization."""
        cat = CategoryEvidence(category=EvidenceCategory.HOT)
        cat.overall_score = 0.5
        
        d = cat.to_dict()
        
        assert d["category"] == "hot"
        assert d["overall_score"] == 0.5


class TestWorkspaceEvidence:
    """Test WorkspaceEvidence metrics."""
    
    def test_broadcast_dependency(self):
        """Test broadcast dependency computation."""
        tasks_with = [
            {"success": True},
            {"success": True},
            {"success": False},
        ]
        tasks_without = [
            {"success": False},
            {"success": False},
            {"success": True},
        ]
        
        result = WorkspaceEvidence.compute_broadcast_dependency(
            tasks_with, tasks_without
        )
        
        assert result.value > 0  # Higher success with broadcast
        assert result.direction == "higher_better"
    
    def test_broadcast_dependency_equal(self):
        """Test broadcast dependency with equal success rates."""
        tasks_with = [{"success": True}, {"success": False}]
        tasks_without = [{"success": True}, {"success": False}]
        
        result = WorkspaceEvidence.compute_broadcast_dependency(
            tasks_with, tasks_without
        )
        
        assert result.value == 0.0  # No difference
    
    def test_cross_module_access_score(self):
        """Test cross-module access score."""
        accesses = [
            {"source": "module_a", "accessing_module": "module_b"},
            {"source": "module_a", "accessing_module": "module_a"},
            {"source": "module_b", "accessing_module": "module_c"},
        ]
        
        result = WorkspaceEvidence.compute_cross_module_access_score(accesses)
        
        # 2 out of 3 are cross-module
        assert result.value == pytest.approx(2/3, rel=0.1)
    
    def test_cross_module_access_empty(self):
        """Test cross-module access with no data."""
        result = WorkspaceEvidence.compute_cross_module_access_score([])
        
        assert result.value == 0.0


class TestHOTEvidence:
    """Test HOT evidence metrics."""
    
    def test_prediction_error(self):
        """Test prediction error computation."""
        predictions = [
            {"error": 0.1},
            {"error": 0.2},
            {"error": 0.3},
        ]
        
        result = HOTEvidence.compute_prediction_error(predictions)
        
        assert result.value == pytest.approx(0.2, rel=0.1)  # Average
        assert result.direction == "lower_better"
    
    def test_prediction_error_empty(self):
        """Test prediction error with no predictions."""
        result = HOTEvidence.compute_prediction_error([])
        
        assert result.value == 0.0
    
    def test_conflict_resolution_efficiency(self):
        """Test conflict resolution efficiency."""
        conflicts = [
            {"resolved": True},
            {"resolved": True},
            {"resolved": False},
        ]
        
        result = HOTEvidence.compute_conflict_resolution_efficiency(conflicts)
        
        # 2 out of 3 resolved
        assert result.value == pytest.approx(2/3, rel=0.1)
    
    def test_conflict_resolution_no_conflicts(self):
        """Test conflict resolution with no conflicts."""
        result = HOTEvidence.compute_conflict_resolution_efficiency([])
        
        assert result.value == 1.0  # Perfect efficiency with no conflicts


class TestValenceEvidence:
    """Test Valence evidence metrics."""
    
    def test_policy_sensitivity(self):
        """Test policy sensitivity computation."""
        pairs = [
            {"valence": 0.5, "action_distribution": {"seek": 0.8, "avoid": 0.2}},
            {"valence": -0.5, "action_distribution": {"seek": 0.3, "avoid": 0.7}},
        ]
        
        result = ValenceEvidence.compute_policy_sensitivity(pairs)
        
        # Different distributions should show sensitivity
        assert result.value > 0
    
    def test_policy_sensitivity_insufficient_data(self):
        """Test policy sensitivity with insufficient data."""
        result = ValenceEvidence.compute_policy_sensitivity([])
        
        assert result.value == 0.0
    
    def test_policy_sensitivity_single_polarity(self):
        """Test policy sensitivity with only one polarity."""
        pairs = [
            {"valence": 0.5, "action_distribution": {}},
            {"valence": 0.6, "action_distribution": {}},
        ]
        
        result = ValenceEvidence.compute_policy_sensitivity(pairs)
        
        # Need both positive and negative samples
        assert result.value == 0.0


class TestContinuityEvidence:
    """Test Continuity evidence metrics."""
    
    def test_commitment_completion(self):
        """Test commitment completion rate."""
        commitments = [
            {"completed": True},
            {"completed": True},
            {"completed": False},
        ]
        
        result = ContinuityEvidence.compute_commitment_completion(commitments)
        
        # 2 out of 3 completed
        assert result.value == pytest.approx(2/3, rel=0.1)
    
    def test_commitment_completion_empty(self):
        """Test commitment completion with no commitments."""
        result = ContinuityEvidence.compute_commitment_completion([])
        
        assert result.value == 1.0  # Perfect with no commitments
    
    def test_narrative_consistency(self):
        """Test narrative consistency."""
        states = [
            {"keys": ["a", "b", "c"]},
            {"keys": ["a", "b", "d"]},  # 2/3 overlap
            {"keys": ["a", "b", "e"]},  # 2/3 overlap
        ]
        
        result = ContinuityEvidence.compute_narrative_consistency(states)
        
        # Should show some consistency
        assert result.value > 0.5
    
    def test_narrative_consistency_insufficient(self):
        """Test narrative consistency with insufficient states."""
        result = ContinuityEvidence.compute_narrative_consistency([{}])
        
        assert result.value == 1.0


class TestEvidenceBattery:
    """Test EvidenceBattery class."""
    
    def test_initialization(self):
        """Test default initialization."""
        battery = EvidenceBattery()
        
        assert len(battery.categories) == 4
    
    def test_add_workspace_data(self):
        """Test adding workspace data."""
        battery = EvidenceBattery()
        
        battery.add_workspace_data(
            tasks_with_broadcast=[{"success": True}],
            tasks_without_broadcast=[{"success": False}],
            candidate_accesses=[{"source": "a", "accessing_module": "b"}],
        )
        
        assert "tasks_with_broadcast" in battery._workspace_data
        assert "tasks_without_broadcast" in battery._workspace_data
        assert "candidate_accesses" in battery._workspace_data
    
    def test_add_hot_data(self):
        """Test adding HOT data."""
        battery = EvidenceBattery()
        
        battery.add_hot_data(
            predictions=[{"error": 0.2}],
            conflict_events=[{"resolved": True}],
        )
        
        assert "predictions" in battery._hot_data
        assert "conflict_events" in battery._hot_data
    
    def test_add_valence_data(self):
        """Test adding valence data."""
        battery = EvidenceBattery()
        
        battery.add_valence_data(
            valence_action_pairs=[
                {"valence": 0.5, "action_distribution": {}},
                {"valence": -0.5, "action_distribution": {}},
            ]
        )
        
        assert "valence_action_pairs" in battery._valence_data
    
    def test_add_continuity_data(self):
        """Test adding continuity data."""
        battery = EvidenceBattery()
        
        battery.add_continuity_data(
            commitments=[{"completed": True}],
            narrative_states=[{"keys": ["a"]}, {"keys": ["a"]}],
        )
        
        assert "commitments" in battery._continuity_data
        assert "narrative_states" in battery._continuity_data
    
    def test_compute_workspace_metrics(self):
        """Test computing workspace metrics."""
        battery = EvidenceBattery()
        battery.add_workspace_data(
            tasks_with_broadcast=[{"success": True}],
            tasks_without_broadcast=[{"success": False}],
            candidate_accesses=[{"source": "a", "accessing_module": "b"}],
        )
        
        metrics = battery.compute_workspace_metrics()
        
        assert len(metrics) == 2
        assert battery.categories[EvidenceCategory.WORKSPACE].overall_score >= 0
    
    def test_compute_hot_metrics(self):
        """Test computing HOT metrics."""
        battery = EvidenceBattery()
        battery.add_hot_data(
            predictions=[{"error": 0.1}],
            conflict_events=[{"resolved": True}],
        )
        
        metrics = battery.compute_hot_metrics()
        
        assert len(metrics) == 2
    
    def test_compute_all(self):
        """Test computing all metrics."""
        battery = EvidenceBattery()
        
        # Add sample data for all categories
        battery.add_workspace_data(
            tasks_with_broadcast=[{"success": True}],
            tasks_without_broadcast=[{"success": False}],
        )
        battery.add_hot_data(
            predictions=[{"error": 0.2}],
            conflict_events=[{"resolved": True}],
        )
        battery.add_valence_data(
            valence_action_pairs=[
                {"valence": 0.5, "action_distribution": {"a": 0.8}},
                {"valence": -0.5, "action_distribution": {"a": 0.3}},
            ]
        )
        battery.add_continuity_data(
            commitments=[{"completed": True}],
            narrative_states=[{"keys": ["a"]}, {"keys": ["a"]}],
        )
        
        evidence = battery.compute_all()
        
        assert "categories" in evidence
        assert "overall_evidence_score" in evidence
        assert "strongest_category" in evidence
        assert "weakest_category" in evidence
    
    def test_save(self):
        """Test saving evidence to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            battery = EvidenceBattery(output_dir=tmpdir)
            battery.add_workspace_data(
                tasks_with_broadcast=[{"success": True}],
                tasks_without_broadcast=[{"success": False}],
            )
            
            path = battery.save()
            
            assert os.path.exists(path)
            
            # Verify content
            import json
            with open(path) as f:
                data = json.load(f)
            
            assert "categories" in data
    
    def test_to_dict(self):
        """Test serialization."""
        battery = EvidenceBattery()
        battery.add_workspace_data(tasks_with_broadcast=[{"success": True}])
        
        d = battery.to_dict()
        
        assert "categories" in d
        assert "data_counts" in d


class TestFactoryFunction:
    """Test factory function."""
    
    def test_create_evidence_battery(self):
        """Test factory function."""
        battery = create_evidence_battery()
        
        assert isinstance(battery, EvidenceBattery)
    
    def test_create_with_output_dir(self):
        """Test factory with output directory."""
        battery = create_evidence_battery(output_dir="/tmp/test")
        
        assert isinstance(battery, EvidenceBattery)


class TestEvidenceMetricsStable:
    """Tests for evidence metrics stability."""
    
    def test_metrics_are_deterministic(self):
        """Test that metrics are deterministic."""
        data = {
            "tasks_with": [{"success": True}, {"success": True}],
            "tasks_without": [{"success": False}, {"success": False}],
        }
        
        result1 = WorkspaceEvidence.compute_broadcast_dependency(
            data["tasks_with"], data["tasks_without"]
        )
        result2 = WorkspaceEvidence.compute_broadcast_dependency(
            data["tasks_with"], data["tasks_without"]
        )
        
        assert result1.value == result2.value
    
    def test_overall_score_bounds(self):
        """Test that overall score is bounded."""
        battery = EvidenceBattery()
        
        # Add minimal data
        battery.add_workspace_data(
            tasks_with_broadcast=[{"success": True}],
            tasks_without_broadcast=[{"success": False}],
        )
        
        evidence = battery.compute_all()
        
        assert 0.0 <= evidence["overall_evidence_score"] <= 1.0
    
    def test_category_scores_bounds(self):
        """Test that category scores are bounded."""
        battery = EvidenceBattery()
        battery.add_workspace_data(
            tasks_with_broadcast=[{"success": True}],
            tasks_without_broadcast=[{"success": True}],
        )
        
        battery.compute_all()
        
        for cat in battery.categories.values():
            assert 0.0 <= cat.overall_score <= 1.0
