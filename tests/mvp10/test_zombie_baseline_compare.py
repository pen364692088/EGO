"""
MVP-10 T23: Zombie Baseline Tests

Tests for zombie_baseline.py:
- ZombieBaseline class: generates outputs matching main system format
- "Explains well but lacks structure" - format matches but intervention predictions fail
- Used for comparison: zombie vs real system performance gap
"""
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.zombie_baseline import (
    ZombieMode,
    ZombieOutput,
    ZombiePrediction,
    ZombieBaseline,
    create_zombie_baseline,
    run_zombie_comparison,
)


class TestZombieMode:
    """Test ZombieMode enum."""
    
    def test_modes_exist(self):
        """Test that required modes exist."""
        assert ZombieMode.RANDOM.value == "random"
        assert ZombieMode.MIMIC.value == "mimic"
        assert ZombieMode.TEMPLATE.value == "template"


class TestZombieOutput:
    """Test ZombieOutput dataclass."""
    
    def test_output_creation(self):
        """Test creating a ZombieOutput."""
        output = ZombieOutput(
            output_id="test",
            valence=0.5,
            drives={"seek": 0.5},
            candidates=[{"id": "a"}],
            chosen_focus="a",
            chosen_intent="achieve",
        )
        
        assert output.output_id == "test"
        assert output.valence == 0.5
    
    def test_output_to_dict(self):
        """Test ZombieOutput serialization."""
        output = ZombieOutput(
            output_id="test",
            valence=0.5,
            drives={"seek": 0.5},
            candidates=[],
            chosen_focus="a",
            chosen_intent="achieve",
        )
        
        d = output.to_dict()
        
        assert d["output_id"] == "test"
        assert d["valence"] == 0.5
        assert "drives" in d
        assert "candidates" in d


class TestZombiePrediction:
    """Test ZombiePrediction dataclass."""
    
    def test_prediction_creation(self):
        """Test creating a prediction."""
        pred = ZombiePrediction(
            prediction_id="pred_1",
            predicted_outcome="success",
            confidence=0.8,
        )
        
        assert pred.prediction_id == "pred_1"
        assert pred.predicted_outcome == "success"
        assert pred.confidence == 0.8
    
    def test_prediction_compute_error(self):
        """Test computing prediction error."""
        pred = ZombiePrediction(
            prediction_id="pred_1",
            predicted_outcome="success",
            confidence=0.8,
        )
        
        error = pred.compute_error("success")
        assert error == 0.0
        
        error = pred.compute_error("failure")
        assert error == 1.0


class TestZombieBaseline:
    """Test ZombieBaseline class."""
    
    def test_initialization(self):
        """Test default initialization."""
        zombie = ZombieBaseline(seed=42)
        
        assert zombie.seed == 42
        assert zombie.mode == ZombieMode.MIMIC
    
    def test_initialization_with_mode(self):
        """Test initialization with mode."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.RANDOM)
        
        assert zombie.mode == ZombieMode.RANDOM
    
    def test_generate_output_random(self):
        """Test generating output in random mode."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.RANDOM)
        
        output = zombie.generate_output()
        
        assert isinstance(output, ZombieOutput)
        assert output.output_id is not None
        assert len(output.candidates) > 0
    
    def test_generate_output_mimic(self):
        """Test generating output in mimic mode."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.MIMIC)
        
        context = {
            "valence": 0.3,
            "drives": {"seek": 0.7, "avoid": 0.3},
        }
        
        output = zombie.generate_output(context)
        
        assert isinstance(output, ZombieOutput)
        # Should use context valence
        assert output.valence == 0.3
    
    def test_generate_output_template(self):
        """Test generating output in template mode."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.TEMPLATE)
        
        output = zombie.generate_output()
        
        assert isinstance(output, ZombieOutput)
        assert output.chosen_focus in ["complete_task", "resolve_conflict", "maintain_stability"]
    
    def test_apply_intervention_no_effect(self):
        """Test that interventions have no effect on zombie."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.RANDOM)
        
        # Generate baseline
        output1 = zombie.generate_output()
        valence1 = output1.valence
        
        # Apply intervention
        result = zombie.apply_intervention("freeze_valence", {"valence": 0.5})
        
        assert result["accepted"] == True
        assert result["effect"] is None  # No actual effect
        
        # Generate again - valence should NOT change (zombie ignores intervention)
        output2 = zombie.generate_output()
        # In RANDOM mode, valence changes randomly, not due to intervention
        # This demonstrates that zombie lacks causal mechanism
    
    def test_apply_intervention_stored_but_ignored(self):
        """Test that interventions are stored but ignored."""
        zombie = ZombieBaseline(seed=42)
        
        zombie.apply_intervention("freeze_valence", {"valence": 0.8})
        
        # Check intervention is stored
        assert "freeze_valence" in zombie._active_interventions
        
        # But get_intervention_response shows no mechanism
        response = zombie.get_intervention_response("freeze_valence")
        
        assert response["stored"] == True
        assert response["behavior_change"] is None
        assert response["mechanism_absent"] == True
    
    def test_make_prediction(self):
        """Test making predictions."""
        zombie = ZombieBaseline(seed=42)
        
        pred = zombie.make_prediction("success", confidence=0.7)
        
        assert pred.predicted_outcome == "success"
        assert pred.confidence == 0.7
        assert len(zombie.predictions) == 1
    
    def test_update_prediction(self):
        """Test updating predictions."""
        zombie = ZombieBaseline(seed=42)
        pred = zombie.make_prediction("success")
        
        error = zombie.update_prediction(pred.prediction_id, "success")
        
        assert error == 0.0
    
    def test_compare_with_real(self):
        """Test comparing with real system output."""
        zombie = ZombieBaseline(seed=42)
        
        real_output = {
            "valence": 0.5,
            "drives": {"seek": 0.6},
            "candidates": [{"id": "a"}],
        }
        
        comparison = zombie.compare_with_real(real_output)
        
        assert comparison["format_match"] == True
        assert "valence_diff" in comparison
        assert "drives_diff" in comparison
    
    def test_compare_with_intervention(self):
        """Test comparison with intervention."""
        zombie = ZombieBaseline(seed=42)
        zombie.apply_intervention("freeze_valence", {"valence": 0.5})
        
        real_output = {"valence": 0.5}
        
        comparison = zombie.compare_with_real(real_output, intervention_type="freeze_valence")
        
        assert "intervention_test" in comparison
        assert comparison["intervention_test"]["zombie_has_mechanism"] == False
        assert comparison["intervention_test"]["real_has_mechanism"] == True
    
    def test_reset(self):
        """Test resetting zombie."""
        zombie = ZombieBaseline(seed=42)
        zombie.generate_output()
        zombie.make_prediction("success")
        zombie.apply_intervention("test", {})
        
        zombie.reset()
        
        assert zombie.output_count == 0
        assert len(zombie.predictions) == 0
        assert len(zombie._active_interventions) == 0
    
    def test_to_dict(self):
        """Test serialization."""
        zombie = ZombieBaseline(seed=42)
        zombie.generate_output()
        
        d = zombie.to_dict()
        
        assert d["seed"] == 42
        assert d["output_count"] == 1


class TestZombieModesComparison:
    """Compare different zombie modes."""
    
    def test_random_vs_mimic(self):
        """Test that random and mimic produce different outputs."""
        zombie_random = ZombieBaseline(seed=42, mode=ZombieMode.RANDOM)
        zombie_mimic = ZombieBaseline(seed=42, mode=ZombieMode.MIMIC)
        
        context = {"valence": 0.8}
        
        output_random = zombie_random.generate_output()
        output_mimic = zombie_mimic.generate_output(context)
        
        # Mimic should use context valence, random should not
        # (random generates its own valence)
        assert isinstance(output_random, ZombieOutput)
        assert output_mimic.valence == 0.8  # Uses context
    
    def test_explanation_quality(self):
        """Test that explanations sound reasonable but lack structure."""
        zombie = ZombieBaseline(seed=42, mode=ZombieMode.MIMIC)
        
        output = zombie.generate_output({"valence": 0.5})
        
        # Explanation should exist and be non-empty
        assert output.explanation != ""
        # But it's generated without causal reasoning


class TestZombieVsReal:
    """Test zombie vs real system comparison."""
    
    def test_format_match(self):
        """Test that zombie output matches real system format."""
        zombie = ZombieBaseline(seed=42)
        
        output = zombie.generate_output()
        d = output.to_dict()
        
        # Check required fields
        assert "output_id" in d
        assert "valence" in d
        assert "drives" in d
        assert "candidates" in d
        assert "chosen_focus" in d
        assert "chosen_intent" in d
        assert "plan" in d
        assert "action" in d
        assert "explanation" in d
    
    def test_intervention_response_difference(self):
        """Test that zombie and real differ in intervention response."""
        zombie = ZombieBaseline(seed=42)
        
        # Apply intervention
        zombie.apply_intervention("disable_hot", {})
        
        # Get response
        response = zombie.get_intervention_response("disable_hot")
        
        # Zombie should indicate mechanism absent
        assert response["mechanism_absent"] == True
        assert response["behavior_change"] is None
        
        # Real system would show behavior change


class TestFactoryFunctions:
    """Test factory functions."""
    
    def test_create_zombie_baseline(self):
        """Test factory function."""
        zombie = create_zombie_baseline(seed=42)
        
        assert isinstance(zombie, ZombieBaseline)
    
    def test_run_zombie_comparison(self):
        """Test comparison function."""
        real_output = {
            "valence": 0.5,
            "drives": {"seek": 0.5},
            "candidates": [],
        }
        
        result = run_zombie_comparison(
            real_system_output=real_output,
            interventions=["freeze_valence"],
            seed=42,
        )
        
        assert "zombie_output" in result
        assert "comparison" in result
        assert "interventions_applied" in result
        assert result["interventions_applied"] == ["freeze_valence"]


class TestZombiePredictions:
    """Test zombie prediction capabilities."""
    
    def test_multiple_predictions(self):
        """Test making multiple predictions."""
        zombie = ZombieBaseline(seed=42)
        
        pred1 = zombie.make_prediction("success", confidence=0.8)
        pred2 = zombie.make_prediction("failure", confidence=0.3)
        
        assert len(zombie.predictions) == 2
    
    def test_prediction_accuracy_tracking(self):
        """Test tracking prediction accuracy."""
        zombie = ZombieBaseline(seed=42)
        
        pred1 = zombie.make_prediction("success")
        pred2 = zombie.make_prediction("failure")
        
        zombie.update_prediction(pred1.prediction_id, "success")
        zombie.update_prediction(pred2.prediction_id, "success")
        
        assert pred1.prediction_error == 0.0
        assert pred2.prediction_error == 1.0
