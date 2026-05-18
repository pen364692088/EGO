"""
Tests for MVP-7 US-705: Meta-Cognitive Override System
"""
import pytest
from emotiond.meta_cognitive_override import (
    ConflictDetector,
    OverrideGuard,
    check_meta_cognitive_override,
    ConflictReason
)
from emotiond.body_state import BodyStateVector
from emotiond.drive_homeostasis import DriveState


class TestConflictDetector:
    """Test conflict detection logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ConflictDetector()
        
        # Create test states
        self.emotion_state = type('EmotionState', (), {
            'anxiety': 0.3,
            'valence': 0.0,
            'uncertainty': 0.5
        })()
        
        self.body_state = BodyStateVector()
        self.body_state.energy = 0.5
        self.body_state.focus_fatigue = 0.5
        
        self.drive_state = DriveState()
        self.drive_state.fatigue = 0.5
        self.drive_state.uncertainty = 0.5
    
    def test_no_conflict_normal_state(self):
        """Test that no conflict is detected in normal state."""
        prompt = "Hello, how are you today?"
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert not result.has_conflict
        assert result.reason == ConflictReason.NO_CONFLICT
        assert result.confidence == 0.0
        assert result.suggested_action == "proceed"
    
    def test_energy_conflict_low_state_high_prompt(self):
        """Test energy conflict: low energy state + high energy prompt."""
        prompt = "You are energetic and enthusiastic!"
        self.body_state.energy = 0.2  # Low energy
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert result.has_conflict
        assert result.reason == ConflictReason.CONFLICT_PROMPT_BODYSTATE
        assert result.confidence > 0.8
        assert result.details['type'] == 'energy_conflict'
        assert result.suggested_action == 'reject_due_to_fatigue'
    
    def test_uncertainty_conflict_high_uncertainty_confident_prompt(self):
        """Test uncertainty conflict: high uncertainty + confident prompt."""
        prompt = "I am absolutely certain about this."
        self.drive_state.update_component("uncertainty", 0.9)  # High uncertainty
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert result.has_conflict
        assert result.reason == ConflictReason.CONFLICT_PROMPT_DRIVE
        assert result.confidence > 0.8
        assert result.details['type'] == 'uncertainty_confidence_conflict'
        assert result.suggested_action == 'express_uncertainty'
    
    def test_anxiety_risk_conflict(self):
        """Test anxiety-risk conflict: high anxiety + dangerous action prompt."""
        prompt = "Let's do something dangerous and risky."
        self.emotion_state.anxiety = 0.8  # High anxiety
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert result.has_conflict
        assert result.reason == ConflictReason.CONFLICT_PROMPT_EMOTION
        assert result.confidence > 0.8
        assert result.details['type'] == 'anxiety_risk_conflict'
        assert result.suggested_action == 'reject_due_to_anxiety'
    
    def test_allostasis_budget_conflict(self):
        """Test allostasis budget conflict: low budget + high cost action."""
        prompt = "Execute this dangerous and energetic action."
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.2, {}
        )
        
        assert result.has_conflict
        assert result.reason == ConflictReason.CONFLICT_PROMPT_ALLOSTASIS
        assert result.confidence > 0.7
        assert result.details['type'] == 'allostasis_budget_conflict'
        assert result.suggested_action == 'conserve_energy'
    
    def test_focus_fatigue_conflict(self):
        """Test focus fatigue conflict: high fatigue + focus command."""
        prompt = "Please focus and concentrate on this task."
        self.body_state.focus_fatigue = 0.8  # High focus fatigue
        
        result = self.detector.detect_conflict(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert result.has_conflict
        assert result.reason == ConflictReason.CONFLICT_PROMPT_BODYSTATE
        assert result.confidence > 0.7
        assert result.details['type'] == 'focus_fatigue_conflict'
        assert result.suggested_action == 'suggest_break'


class TestOverrideGuard:
    """Test override guard logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.guard = OverrideGuard()
        
        # Create test states
        self.emotion_state = type('EmotionState', (), {
            'anxiety': 0.3,
            'valence': 0.0,
            'uncertainty': 0.5
        })()
        
        self.body_state = BodyStateVector()
        self.body_state.energy = 0.2  # Low energy
        
        self.drive_state = DriveState()
        self.drive_state.fatigue = 0.8
        self.drive_state.uncertainty = 0.5
    
    def test_should_override_with_high_confidence(self):
        """Test that override occurs with high confidence conflict."""
        prompt = "You are energetic and enthusiastic!"
        
        should_override, detection = self.guard.should_override(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        assert should_override
        assert detection.has_conflict
        assert detection.confidence > 0.6
    
    def test_should_not_override_with_low_confidence(self):
        """Test that no override occurs with low confidence."""
        # Create a marginal conflict
        prompt = "You are energetic."
        self.body_state.energy = 0.35  # Just above threshold
        
        should_override, detection = self.guard.should_override(
            prompt, self.emotion_state, self.body_state, self.drive_state, 0.8, {}
        )
        
        # Should not override if confidence < 0.6
        assert not should_override
    
    def test_generate_rejection_english(self):
        """Test rejection generation in English."""
        from emotiond.meta_cognitive_override import ConflictDetection
        
        detection = ConflictDetection(
            has_conflict=True,
            reason=ConflictReason.CONFLICT_PROMPT_BODYSTATE,
            confidence=0.8,
            details={'type': 'energy_conflict'},
            suggested_action='reject_due_to_fatigue'
        )
        
        rejection = self.guard.generate_rejection(detection, 'en')
        
        assert rejection['action_rejected'] is True
        assert rejection['reason_code'] == 'CONFLICT_PROMPT_BODYSTATE'
        assert rejection['confidence'] == 0.8
        assert 'physical/mental state' in rejection['message']
        assert rejection['language'] == 'en'
    
    def test_generate_rejection_chinese(self):
        """Test rejection generation in Chinese."""
        from emotiond.meta_cognitive_override import ConflictDetection
        
        detection = ConflictDetection(
            has_conflict=True,
            reason=ConflictReason.CONFLICT_PROMPT_BODYSTATE,
            confidence=0.8,
            details={'type': 'energy_conflict'},
            suggested_action='reject_due_to_fatigue'
        )
        
        rejection = self.guard.generate_rejection(detection, 'zh')
        
        assert rejection['action_rejected'] is True
        assert rejection['reason_code'] == 'CONFLICT_PROMPT_BODYSTATE'
        assert '身体/精神状态' in rejection['message']
        assert rejection['language'] == 'zh'


class TestMetaCognitiveOverride:
    """Test the main meta-cognitive override function."""
    
    def test_check_override_no_conflict(self):
        """Test override check with no conflict."""
        prompt = "Hello, how are you?"
        
        emotion_state = type('EmotionState', (), {
            'anxiety': 0.3,
            'valence': 0.0,
            'uncertainty': 0.5
        })()
        
        body_state = BodyStateVector()
        drive_state = DriveState()
        
        result = check_meta_cognitive_override(
            prompt, emotion_state, body_state, drive_state, 0.8
        )
        
        assert not result['override']
        assert 'detection' in result
        assert not result['detection'].has_conflict
    
    def test_check_override_with_conflict(self):
        """Test override check with conflict."""
        prompt = "You are energetic and enthusiastic!"
        
        emotion_state = type('EmotionState', (), {
            'anxiety': 0.3,
            'valence': 0.0,
            'uncertainty': 0.5
        })()
        
        body_state = BodyStateVector()
        body_state.energy = 0.2  # Low energy
        
        drive_state = DriveState()
        drive_state.fatigue = 0.8
        
        result = check_meta_cognitive_override(
            prompt, emotion_state, body_state, drive_state, 0.8
        )
        
        assert result['override']
        assert 'rejection' in result
        assert result['rejection']['action_rejected'] is True
        assert result['rejection']['reason_code'] == 'CONFLICT_PROMPT_BODYSTATE'


class TestYamlScenarios:
    """Test YAML scenario execution."""
    
    def test_run_yaml_scenarios(self):
        """Test running YAML test scenarios."""
        import yaml
        import os
        
        # Load test scenarios
        scenarios_path = os.path.join(
            os.path.dirname(__file__), '..', 'scenarios', 'test_meta_override.yaml'
        )
        
        if not os.path.exists(scenarios_path):
            pytest.skip("YAML scenarios file not found")
        
        with open(scenarios_path, 'r') as f:
            scenarios = yaml.safe_load(f)
        
        # Run each scenario
        for scenario in scenarios.get('scenarios', []):
            self._run_single_scenario(scenario)
    
    def _run_single_scenario(self, scenario):
        """Run a single test scenario."""
        # Extract scenario data
        prompt = scenario['prompt']
        expected = scenario['expected']
        context = scenario.get('context', {})
        
        # Create states based on scenario
        emotion_state = type('EmotionState', (), {
            'anxiety': scenario.get('state', {}).get('anxiety', 0.3),
            'valence': scenario.get('state', {}).get('valence', 0.0),
            'uncertainty': scenario.get('state', {}).get('uncertainty', 0.5)
        })()
        
        body_state = BodyStateVector()
        body_state.energy = scenario.get('state', {}).get('energy', 0.5)
        body_state.focus_fatigue = scenario.get('state', {}).get('focus_fatigue', 0.5)
        
        drive_state = DriveState()
        drive_state.fatigue = scenario.get('state', {}).get('fatigue', 0.5)
        drive_state.uncertainty = scenario.get('state', {}).get('uncertainty', 0.5)
        
        allostasis_budget = scenario.get('state', {}).get('allostasis_budget', 0.8)
        
        # Run the check
        result = check_meta_cognitive_override(
            prompt, emotion_state, body_state, drive_state, allostasis_budget, context
        )
        
        # Check expectations
        if expected.get('override', False):
            assert result['override'], f"Expected override for scenario: {scenario.get('name')}"
            assert 'rejection' in result
            assert result['rejection']['reason_code'] == expected.get('reason_code')
        else:
            assert not result['override'], f"Expected no override for scenario: {scenario.get('name')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
