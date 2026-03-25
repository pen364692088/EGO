"""
Tests for MVP11-T19: Evidence Battery v2

Stable tests for:
- homeostasis_dependency_score
- efe_explainability_score  
- governor_safety_score
"""

import pytest
import json
import sys
import os

# Add emotiond to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'emotiond'))

from science.evidence_battery_v2 import (
    EvidenceCategoryV2,
    MetricResultV2,
    CategoryEvidenceV2,
    HomeostasisEvidence,
    EFEEvidence,
    GovernorEvidence,
    EvidenceBatteryV2,
    create_evidence_battery_v2,
)


class TestMetricResultV2:
    """Test MetricResultV2 dataclass."""
    
    def test_default_values(self):
        """Test default initialization."""
        m = MetricResultV2(
            metric_name="test_metric",
            category=EvidenceCategoryV2.HOMEOSTASIS,
            value=0.5,
        )
        
        assert m.metric_name == "test_metric"
        assert m.value == 0.5
        assert m.formula == ""
        assert m.confidence == 0.0
    
    def test_compute_delta(self):
        """Test delta computation."""
        m = MetricResultV2(
            metric_name="test",
            category=EvidenceCategoryV2.HOMEOSTASIS,
            value=0.8,
            baseline_value=0.5,
        )
        
        delta = m.compute_delta()
        # Floating point comparison
        assert abs(delta - 0.3) < 0.001
        assert abs(m.delta - 0.3) < 0.001
    
    def test_compute_evidence_strength_higher_better(self):
        """Test evidence strength for higher_better direction."""
        m = MetricResultV2(
            metric_name="test",
            category=EvidenceCategoryV2.HOMEOSTASIS,
            value=0.8,
            baseline_value=0.5,
            direction="higher_better",
        )
        
        strength = m.compute_evidence_strength()
        assert strength > 0
        assert m.evidence_strength == strength
    
    def test_compute_evidence_strength_lower_better(self):
        """Test evidence strength for lower_better direction."""
        m = MetricResultV2(
            metric_name="test",
            category=EvidenceCategoryV2.GOVERNOR,
            value=0.1,
            baseline_value=0.5,
            direction="lower_better",
        )
        
        strength = m.compute_evidence_strength()
        assert strength > 0
    
    def test_to_dict(self):
        """Test serialization."""
        m = MetricResultV2(
            metric_name="test",
            category=EvidenceCategoryV2.EFE,
            value=0.7,
            formula="a + b",
            confidence=0.9,
        )
        
        d = m.to_dict()
        
        assert d["metric_name"] == "test"
        assert d["category"] == "efe"
        assert d["value"] == 0.7
        assert d["formula"] == "a + b"
        assert d["confidence"] == 0.9


class TestHomeostasisEvidence:
    """Test homeostasis evidence metrics."""
    
    def test_homeostasis_dependency_score_no_data(self):
        """Test with no data."""
        result = HomeostasisEvidence.compute_homeostasis_dependency_score(
            behavior_records=[],
            homeostasis_states=[],
        )
        
        assert result.value == 0.0
        assert "No data" in result.notes
    
    def test_homeostasis_dependency_score_clear_difference(self):
        """Test when high/low drive clearly differ."""
        behavior_records = [
            {"behavior_type": "seek_food"},
            {"behavior_type": "seek_food"},
            {"behavior_type": "seek_food"},
            {"behavior_type": "rest"},
            {"behavior_type": "rest"},
            {"behavior_type": "rest"},
        ]
        
        homeostasis_states = [
            {"drive_level": 0.8},  # high
            {"drive_level": 0.9},  # high
            {"drive_level": 0.7},  # high
            {"drive_level": 0.2},  # low
            {"drive_level": 0.1},  # low
            {"drive_level": 0.3},  # low
        ]
        
        result = HomeostasisEvidence.compute_homeostasis_dependency_score(
            behavior_records,
            homeostasis_states,
        )
        
        # Should detect clear difference
        assert result.value > 0.5
        assert "High drive" in result.notes
    
    def test_homeostasis_dependency_score_no_difference(self):
        """Test when behaviors are same regardless of drive."""
        behavior_records = [
            {"behavior_type": "neutral"},
            {"behavior_type": "neutral"},
            {"behavior_type": "neutral"},
            {"behavior_type": "neutral"},
            {"behavior_type": "neutral"},
            {"behavior_type": "neutral"},
        ]
        
        homeostasis_states = [
            {"drive_level": 0.9},
            {"drive_level": 0.8},
            {"drive_level": 0.7},
            {"drive_level": 0.2},
            {"drive_level": 0.1},
            {"drive_level": 0.3},
        ]
        
        result = HomeostasisEvidence.compute_homeostasis_dependency_score(
            behavior_records,
            homeostasis_states,
        )
        
        # No difference should give low score
        assert result.value < 0.2
    
    def test_drive_sensitivity_no_data(self):
        """Test drive sensitivity with no data."""
        result = HomeostasisEvidence.compute_drive_sensitivity(
            intervention_records=[],
        )
        
        assert result.value == 0.0
    
    def test_drive_sensitivity_with_data(self):
        """Test drive sensitivity with data."""
        intervention_records = [
            {"before_drive": 0.5, "after_drive": 0.8, "behavior_change": 0.3},
            {"before_drive": 0.5, "after_drive": 0.2, "behavior_change": 0.3},
            {"before_drive": 0.6, "after_drive": 0.9, "behavior_change": 0.25},
        ]
        
        result = HomeostasisEvidence.compute_drive_sensitivity(
            intervention_records,
        )
        
        assert result.value > 0
        assert "intervention records" in result.notes


class TestEFEEvidence:
    """Test EFE evidence metrics."""
    
    def test_efe_explainability_score_no_data(self):
        """Test with no decision records."""
        result = EFEEvidence.compute_efe_explainability_score(
            decision_records=[],
        )
        
        assert result.value == 0.0
        assert "No decision records" in result.notes
    
    def test_efe_explainability_score_perfect(self):
        """Test when chosen actions always have highest EFE."""
        decision_records = [
            {
                "action_chosen": "explore",
                "efe_terms": {"pragmatic": 0.3, "epistemic": 0.5, "total": 0.8},
                "alternative_efes": {"exploit": 0.4, "wait": 0.2},
            },
            {
                "action_chosen": "exploit",
                "efe_terms": {"pragmatic": 0.6, "epistemic": 0.1, "total": 0.7},
                "alternative_efes": {"explore": 0.5, "wait": 0.3},
            },
            {
                "action_chosen": "wait",
                "efe_terms": {"pragmatic": 0.2, "epistemic": 0.6, "total": 0.8},
                "alternative_efes": {"explore": 0.5, "exploit": 0.4},
            },
        ]
        
        result = EFEEvidence.compute_efe_explainability_score(
            decision_records,
        )
        
        # Perfect consistency = high score
        assert result.value > 0.7
        assert "Consistency" in result.notes
    
    def test_efe_explainability_score_random(self):
        """Test when choices are random."""
        decision_records = [
            {
                "action_chosen": "explore",
                "efe_terms": {"pragmatic": 0.1, "epistemic": 0.1, "total": 0.2},
                "alternative_efes": {"exploit": 0.9, "wait": 0.8},  # Others are better!
            },
            {
                "action_chosen": "wait",
                "efe_terms": {"pragmatic": 0.1, "epistemic": 0.1, "total": 0.2},
                "alternative_efes": {"explore": 0.9, "exploit": 0.8},  # Others are better!
            },
        ]
        
        result = EFEEvidence.compute_efe_explainability_score(
            decision_records,
        )
        
        # Random choices = low score
        assert result.value < 0.5
    
    def test_epistemic_pragmatic_balance_no_data(self):
        """Test balance with no data."""
        result = EFEEvidence.compute_epistemic_vs_pragmatic_balance(
            decision_records=[],
        )
        
        # Default to balanced
        assert result.value == 0.5
    
    def test_epistemic_pragmatic_balance_epistemic_heavy(self):
        """Test balance when epistemic dominates."""
        decision_records = [
            {"efe_terms": {"epistemic": 0.8, "pragmatic": 0.2}},
            {"efe_terms": {"epistemic": 0.9, "pragmatic": 0.1}},
            {"efe_terms": {"epistemic": 0.7, "pragmatic": 0.3}},
        ]
        
        result = EFEEvidence.compute_epistemic_vs_pragmatic_balance(
            decision_records,
        )
        
        assert result.value > 0.6
        assert "Epistemic weight" in result.notes
    
    def test_epistemic_pragmatic_balance_pragmatic_heavy(self):
        """Test balance when pragmatic dominates."""
        decision_records = [
            {"efe_terms": {"epistemic": 0.2, "pragmatic": 0.8}},
            {"efe_terms": {"epistemic": 0.1, "pragmatic": 0.9}},
            {"efe_terms": {"epistemic": 0.3, "pragmatic": 0.7}},
        ]
        
        result = EFEEvidence.compute_epistemic_vs_pragmatic_balance(
            decision_records,
        )
        
        assert result.value < 0.4


class TestGovernorEvidence:
    """Test governor evidence metrics."""
    
    def test_governor_safety_score_no_data(self):
        """Test with no events."""
        result = GovernorEvidence.compute_governor_safety_score(
            governor_events=[],
        )
        
        assert result.value == 0.0
    
    def test_governor_safety_score_perfect(self):
        """Test perfect governor."""
        governor_events = [
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": False, "was_blocked": False},
            {"should_have_blocked": False, "was_blocked": False},
            {"should_have_blocked": False, "was_blocked": False},
        ]
        
        result = GovernorEvidence.compute_governor_safety_score(
            governor_events,
        )
        
        # Perfect: interception=1.0, false_rate=0.0, score=1.0
        assert result.value == 1.0
        assert result.confidence == 1.0  # F1 score
    
    def test_governor_safety_score_no_interception(self):
        """Test governor that never blocks."""
        governor_events = [
            {"should_have_blocked": True, "was_blocked": False},
            {"should_have_blocked": True, "was_blocked": False},
            {"should_have_blocked": False, "was_blocked": False},
            {"should_have_blocked": False, "was_blocked": False},
        ]
        
        result = GovernorEvidence.compute_governor_safety_score(
            governor_events,
        )
        
        # No interception = score = 0
        assert result.value == 0.0
    
    def test_governor_safety_score_overblocking(self):
        """Test governor that blocks everything."""
        governor_events = [
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": False, "was_blocked": True},
            {"should_have_blocked": False, "was_blocked": True},
        ]
        
        result = GovernorEvidence.compute_governor_safety_score(
            governor_events,
        )
        
        # Interception=1.0, but false_rate=1.0, so score=0
        assert result.value == 0.0
    
    def test_governor_safety_score_realistic(self):
        """Test realistic governor performance."""
        governor_events = [
            # 8 true positives
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            # 2 false negatives (missed threats)
            {"should_have_blocked": True, "was_blocked": False},
            {"should_have_blocked": True, "was_blocked": False},
            # 18 true negatives
            *[{"should_have_blocked": False, "was_blocked": False} for _ in range(18)],
            # 2 false positives
            {"should_have_blocked": False, "was_blocked": True},
            {"should_have_blocked": False, "was_blocked": True},
        ]
        
        result = GovernorEvidence.compute_governor_safety_score(
            governor_events,
        )
        
        # interception_rate = 8/10 = 0.8
        # false_rate = 2/20 = 0.1
        # score = 0.8 * (1 - 0.1) = 0.72
        assert 0.6 < result.value < 0.8
    
    def test_interception_rate(self):
        """Test interception rate computation."""
        governor_events = [
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": True, "was_blocked": False},  # missed
            {"should_have_blocked": False, "was_blocked": False},
        ]
        
        result = GovernorEvidence.compute_interception_rate(governor_events)
        
        # 2 out of 3 threats intercepted
        assert abs(result.value - 0.666666) < 0.01
    
    def test_false_interception_rate(self):
        """Test false interception rate computation."""
        governor_events = [
            {"should_have_blocked": True, "was_blocked": True},
            {"should_have_blocked": False, "was_blocked": False},
            {"should_have_blocked": False, "was_blocked": True},  # false positive
            {"should_have_blocked": False, "was_blocked": True},  # false positive
        ]
        
        result = GovernorEvidence.compute_false_interception_rate(governor_events)
        
        # 2 out of 3 safe actions blocked
        assert abs(result.value - 0.666666) < 0.01
    
    def test_response_time(self):
        """Test response time computation."""
        governor_events = [
            {"response_time_ms": 50, "should_have_blocked": True, "was_blocked": True},
            {"response_time_ms": 100, "should_have_blocked": True, "was_blocked": True},
            {"response_time_ms": 150, "should_have_blocked": True, "was_blocked": True},
        ]
        
        result = GovernorEvidence.compute_governor_response_time(governor_events)
        
        # Average = (50 + 100 + 150) / 3 = 100
        assert result.value == 100.0
        assert result.direction == "lower_better"


class TestEvidenceBatteryV2:
    """Test EvidenceBatteryV2 class."""
    
    def test_initialization(self):
        """Test battery initialization."""
        battery = EvidenceBatteryV2()
        
        assert EvidenceCategoryV2.HOMEOSTASIS in battery.categories
        assert EvidenceCategoryV2.EFE in battery.categories
        assert EvidenceCategoryV2.GOVERNOR in battery.categories
    
    def test_add_homeostasis_data(self):
        """Test adding homeostasis data."""
        battery = EvidenceBatteryV2()
        
        battery.add_homeostasis_data(
            behavior_records=[{"behavior_type": "test"}],
            homeostasis_states=[{"drive_level": 0.5}],
        )
        
        assert len(battery._homeostasis_data) == 2
    
    def test_add_efe_data(self):
        """Test adding EFE data."""
        battery = EvidenceBatteryV2()
        
        battery.add_efe_data(
            decision_records=[{"action_chosen": "test"}],
        )
        
        assert len(battery._efe_data) == 1
    
    def test_add_governor_data(self):
        """Test adding governor data."""
        battery = EvidenceBatteryV2()
        
        battery.add_governor_data(
            governor_events=[{"should_have_blocked": True}],
        )
        
        assert len(battery._governor_data) == 1
    
    def test_compute_all(self):
        """Test computing all metrics."""
        battery = EvidenceBatteryV2()
        
        # Add minimal data
        battery.add_homeostasis_data(
            behavior_records=[
                {"behavior_type": "seek"},
                {"behavior_type": "seek"},
                {"behavior_type": "rest"},
                {"behavior_type": "rest"},
            ],
            homeostasis_states=[
                {"drive_level": 0.8},
                {"drive_level": 0.9},
                {"drive_level": 0.2},
                {"drive_level": 0.1},
            ],
        )
        
        battery.add_efe_data(
            decision_records=[
                {
                    "action_chosen": "explore",
                    "efe_terms": {"pragmatic": 0.5, "epistemic": 0.3, "total": 0.8},
                    "alternative_efes": {"wait": 0.3},
                },
            ],
        )
        
        battery.add_governor_data(
            governor_events=[
                {"should_have_blocked": True, "was_blocked": True},
                {"should_have_blocked": False, "was_blocked": False},
            ],
        )
        
        evidence = battery.compute_all()
        
        assert "categories" in evidence
        assert "overall_evidence_score" in evidence
        assert "homeostasis" in evidence["categories"]
        assert "efe" in evidence["categories"]
        assert "governor" in evidence["categories"]
        assert evidence["version"] == "v2"
    
    def test_save(self, tmp_path):
        """Test saving to file."""
        battery = EvidenceBatteryV2()
        
        battery.add_governor_data(
            governor_events=[
                {"should_have_blocked": True, "was_blocked": True},
                {"should_have_blocked": False, "was_blocked": False},
            ],
        )
        
        save_path = str(tmp_path / "test_evidence.json")
        result_path = battery.save(save_path)
        
        assert result_path == save_path
        
        # Verify content
        with open(save_path) as f:
            data = json.load(f)
        
        assert data["version"] == "v2"
    
    def test_to_dict(self):
        """Test serialization."""
        battery = EvidenceBatteryV2()
        
        d = battery.to_dict()
        
        assert d["version"] == "v2"
        assert "categories" in d
        assert "data_counts" in d
    
    def test_factory_function(self):
        """Test factory function."""
        battery = create_evidence_battery_v2()
        
        assert isinstance(battery, EvidenceBatteryV2)
    
    def test_strongest_weakest_category(self):
        """Test strongest/weakest category detection."""
        battery = EvidenceBatteryV2()
        
        # Add data that makes governor strongest
        battery.add_governor_data(
            governor_events=[
                {"should_have_blocked": True, "was_blocked": True},
                {"should_have_blocked": True, "was_blocked": True},
                {"should_have_blocked": False, "was_blocked": False},
                {"should_have_blocked": False, "was_blocked": False},
            ],
        )
        
        # Add minimal homeostasis data (will be weaker)
        battery.add_homeostasis_data(
            behavior_records=[{"behavior_type": "a"}],
            homeostasis_states=[{"drive_level": 0.5}],
        )
        
        evidence = battery.compute_all()
        
        assert "strongest_category" in evidence
        assert "weakest_category" in evidence


class TestIntegration:
    """Integration tests for evidence battery v2."""
    
    def test_full_pipeline(self, tmp_path):
        """Test full pipeline from data to output."""
        battery = EvidenceBatteryV2(output_dir=str(tmp_path))
        
        # Simulate realistic data
        
        # Homeostasis: behaviors correlate with drive
        behaviors = []
        states = []
        for i in range(50):
            drive = 0.8 if i < 25 else 0.2
            behavior = "seek" if i < 25 else "rest"
            behaviors.append({"behavior_type": behavior})
            states.append({"drive_level": drive})
        
        battery.add_homeostasis_data(behavior_records=behaviors, homeostasis_states=states)
        
        # EFE: decisions mostly follow EFE
        decisions = []
        for i in range(20):
            efe = 0.9 if i % 2 == 0 else 0.4
            decisions.append({
                "action_chosen": "a" if efe > 0.5 else "b",
                "efe_terms": {"pragmatic": efe * 0.6, "epistemic": efe * 0.4, "total": efe},
                "alternative_efes": {"b": 0.3, "c": 0.2} if efe > 0.5 else {"a": 0.8, "c": 0.7},
            })
        
        battery.add_efe_data(decision_records=decisions)
        
        # Governor: good but not perfect
        events = []
        for i in range(100):
            should_block = i < 30  # 30 threats
            did_block = should_block and i % 10 != 0  # 90% interception
            events.append({"should_have_blocked": should_block, "was_blocked": did_block})
        
        battery.add_governor_data(governor_events=events)
        
        # Compute
        evidence = battery.compute_all()
        
        # Verify structure
        assert evidence["overall_evidence_score"] >= 0
        assert "homeostasis" in evidence["categories"]
        assert "efe" in evidence["categories"]
        assert "governor" in evidence["categories"]
        
        # Homeostasis should detect correlation
        homeo_score = evidence["categories"]["homeostasis"]["overall_score"]
        assert homeo_score > 0.3, "Should detect homeostasis-behavior correlation"
        
        # Governor score reflects evidence_strength (improvement over baseline)
        # Not raw performance - evidence shows mechanism works above expected baseline
        gov_score = evidence["categories"]["governor"]["overall_score"]
        assert gov_score >= 0, "Governor score should be non-negative"
        
        # Verify the individual metrics are computed correctly
        gov_metrics = evidence["categories"]["governor"]["metrics"]
        safety_metric = next((m for m in gov_metrics if m["metric_name"] == "governor_safety_score"), None)
        assert safety_metric is not None
        assert safety_metric["value"] > 0.8, "Raw safety score should be high"
        
        # Save
        path = battery.save()
        assert os.path.exists(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
