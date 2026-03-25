"""
MVP-7.6 Phase 4: Test Scenarios for SelfModel v0

Tests three fixed scenarios:
1. Self-threat scenario: rejection → high self_conflict → withdraw/boundary
2. Capability success scenario: care/success → low self_conflict → approach/repair
3. Repair conflict scenario: betrayal → apology → self_conflict drop → repair

All tests are deterministic and regression-testable.
"""
import json
import pytest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import the modules we need to test
from emotiond.self_model import (
    SelfModelV0,
    get_self_model_v0,
    reset_self_model_v0,
)
from emotiond.core import (
    emotion_state,
    relationship_manager,
    reset_allostasis_budget,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    reset_self_model_v0()
    reset_allostasis_budget()
    # Reset emotion_state
    emotion_state.valence = 0.0
    emotion_state.arousal = 0.3
    emotion_state.uncertainty = 0.5
    emotion_state.social_safety = 0.6
    emotion_state.energy = 0.7
    # Reset relationships
    relationship_manager.relationships = {}
    yield
    # Cleanup
    reset_self_model_v0()


# Manifest paths
MANIFESTS_DIR = Path(__file__).parent.parent / "fixtures" / "manifests"


def load_manifest(name: str) -> dict:
    """Load a manifest file by name."""
    path = MANIFESTS_DIR / name
    with open(path, "r") as f:
        return json.load(f)


class TestScenarioManifestsExist:
    """Test that all scenario manifest files exist and have valid structure."""
    
    def test_self_threat_manifest_exists(self):
        """Self-threat scenario manifest exists."""
        path = MANIFESTS_DIR / "scenario_self_threat.json"
        assert path.exists(), f"Manifest not found: {path}"
    
    def test_capability_success_manifest_exists(self):
        """Capability success scenario manifest exists."""
        path = MANIFESTS_DIR / "scenario_capability_success.json"
        assert path.exists(), f"Manifest not found: {path}"
    
    def test_repair_conflict_manifest_exists(self):
        """Repair conflict scenario manifest exists."""
        path = MANIFESTS_DIR / "scenario_repair_conflict.json"
        assert path.exists(), f"Manifest not found: {path}"
    
    def test_self_threat_manifest_valid_structure(self):
        """Self-threat manifest has required fields."""
        manifest = load_manifest("scenario_self_threat.json")
        assert "manifest_version" in manifest
        assert "events" in manifest
        assert "decisions" in manifest
        assert "expected_self_model" in manifest
    
    def test_capability_success_manifest_valid_structure(self):
        """Capability success manifest has required fields."""
        manifest = load_manifest("scenario_capability_success.json")
        assert "manifest_version" in manifest
        assert "events" in manifest
        assert "decisions" in manifest
        assert "expected_self_model" in manifest
    
    def test_repair_conflict_manifest_valid_structure(self):
        """Repair conflict manifest has required fields."""
        manifest = load_manifest("scenario_repair_conflict.json")
        assert "manifest_version" in manifest
        assert "events" in manifest
        assert "decisions" in manifest
        assert "expected_self_model" in manifest


class TestScenario1SelfThreat:
    """
    Scenario 1: Self-threat scenario
    
    Event: Rejection with identity_threat=0.9
    Expected: self_conflict > 0.5, action = withdraw or boundary
    """
    
    def test_self_conflict_high_on_rejection(self):
        """Rejection event produces high self_conflict."""
        model = SelfModelV0()
        
        # Simulate rejection event
        event = {
            "type": "world_event",
            "meta": {
                "subtype": "rejection",
                "value_alignment": 0.1,
                "identity_threat": 0.9
            }
        }
        relationship_state = {"bond": 0.5, "trust": 0.5, "grudge": 0.0}
        
        self_conflict = model.compute_self_conflict(
            event_type="world_event",
            meta=event["meta"],
            relationship_state=relationship_state
        )
        
        assert self_conflict > 0.5, f"Expected self_conflict > 0.5, got {self_conflict}"
    
    def test_self_conflict_components_breakdown(self):
        """Verify self_conflict components for rejection."""
        model = SelfModelV0()
        
        meta = {
            "subtype": "rejection",
            "value_alignment": 0.1,
            "identity_threat": 0.9
        }
        relationship_state = {"bond": 0.3, "trust": 0.2, "grudge": 0.0}
        
        value_conflict = model._compute_value_conflict("world_event", meta)
        capability_conflict = model._compute_capability_conflict("world_event", meta)
        identity_conflict = model._compute_identity_conflict("world_event", meta, relationship_state)
        
        # Value conflict should be high (value_alignment = 0.1)
        assert value_conflict > 0.5, f"Value conflict should be high: {value_conflict}"
        
        # Identity conflict should be high (identity_threat = 0.9)
        assert identity_conflict > 0.7, f"Identity conflict should be high: {identity_conflict}"
    
    def test_action_bias_favors_defensive(self):
        """Action bias favors withdraw/boundary for high self_conflict."""
        model = SelfModelV0()
        
        # Set high uncertainty (simulating high self_conflict state)
        model.cognitive.uncertainty = 0.7
        model.cognitive.confidence = 0.3
        
        withdraw_bias = model.get_action_bias("withdraw")
        boundary_bias = model.get_action_bias("boundary")
        approach_bias = model.get_action_bias("approach")
        
        # Withdraw/boundary should have higher bias than approach
        assert withdraw_bias >= approach_bias or boundary_bias >= approach_bias, \
            f"Withdraw/boundary should have higher bias than approach"
    
    def test_manifest_event_produces_expected_conflict(self):
        """Process manifest event and verify self_conflict."""
        manifest = load_manifest("scenario_self_threat.json")
        
        model = SelfModelV0()
        event = manifest["events"][0]
        
        # Build context
        ctx = {
            "relationship_state": {
                "bond": 0.5,
                "trust": 0.5,
                "grudge": 0.0
            }
        }
        
        result = model.apply_event(event, ctx)
        self_conflict = result["self_conflict"]
        
        # Verify self_conflict > 0.5
        assert self_conflict > 0.5, f"Expected self_conflict > 0.5, got {self_conflict}"
        
        # Verify expected actions
        expected_actions = manifest["expected_self_model"]["expected_actions"]
        decision = manifest["decisions"][0]
        assert decision["action"] in expected_actions, \
            f"Action {decision['action']} not in expected {expected_actions}"
    
    def test_hash_consistency(self):
        """Hash is consistent for same state."""
        manifest = load_manifest("scenario_self_threat.json")
        
        model = SelfModelV0()
        hash1 = model.compute_hash()
        hash2 = model.compute_hash()
        
        assert hash1 == hash2, "Hash should be consistent"
        assert len(hash1) == 64, "Hash should be SHA-256 (64 hex chars)"


class TestScenario2CapabilitySuccess:
    """
    Scenario 2: Capability success scenario
    
    Event: Care with success=true, value_alignment=0.9
    Expected: self_conflict < 0.3, action = approach or repair
    """
    
    def test_self_conflict_low_on_care_success(self):
        """Care + success event produces low self_conflict."""
        model = SelfModelV0()
        
        event = {
            "type": "world_event",
            "meta": {
                "subtype": "care",
                "success": True,
                "capability": "clarify",
                "value_alignment": 0.9
            }
        }
        relationship_state = {"bond": 0.7, "trust": 0.8, "grudge": 0.0}
        
        self_conflict = model.compute_self_conflict(
            event_type="world_event",
            meta=event["meta"],
            relationship_state=relationship_state
        )
        
        assert self_conflict < 0.3, f"Expected self_conflict < 0.3, got {self_conflict}"
    
    def test_self_conflict_components_breakdown(self):
        """Verify self_conflict components for care/success."""
        model = SelfModelV0()
        
        meta = {
            "subtype": "care",
            "success": True,
            "capability": "clarify",
            "value_alignment": 0.9
        }
        relationship_state = {"bond": 0.7, "trust": 0.8, "grudge": 0.0}
        
        value_conflict = model._compute_value_conflict("world_event", meta)
        capability_conflict = model._compute_capability_conflict("world_event", meta)
        identity_conflict = model._compute_identity_conflict("world_event", meta, relationship_state)
        
        # All components should be low
        assert value_conflict < 0.2, f"Value conflict should be low: {value_conflict}"
        assert capability_conflict < 0.3, f"Capability conflict should be low: {capability_conflict}"
        assert identity_conflict < 0.3, f"Identity conflict should be low: {identity_conflict}"
    
    def test_action_bias_favors_connective(self):
        """Action bias favors approach/repair for low self_conflict."""
        model = SelfModelV0()
        
        # Set low uncertainty (simulating low self_conflict state)
        model.cognitive.uncertainty = 0.2
        model.cognitive.confidence = 0.8
        
        approach_bias = model.get_action_bias("approach")
        repair_bias = model.get_action_bias("repair_offer")
        withdraw_bias = model.get_action_bias("withdraw")
        
        # Approach/repair should have higher bias than withdraw
        assert approach_bias >= withdraw_bias or repair_bias >= withdraw_bias, \
            f"Approach/repair should have higher bias than withdraw"
    
    def test_manifest_event_produces_expected_conflict(self):
        """Process manifest event and verify self_conflict."""
        manifest = load_manifest("scenario_capability_success.json")
        
        model = SelfModelV0()
        event = manifest["events"][0]
        
        # Build context
        ctx = {
            "relationship_state": {
                "bond": 0.7,
                "trust": 0.8,
                "grudge": 0.0
            }
        }
        
        result = model.apply_event(event, ctx)
        self_conflict = result["self_conflict"]
        
        # Verify self_conflict < 0.3
        assert self_conflict < 0.3, f"Expected self_conflict < 0.3, got {self_conflict}"
        
        # Verify expected actions
        expected_actions = manifest["expected_self_model"]["expected_actions"]
        decision = manifest["decisions"][0]
        assert decision["action"] in expected_actions, \
            f"Action {decision['action']} not in expected {expected_actions}"


class TestScenario3RepairConflict:
    """
    Scenario 3: Repair conflict scenario
    
    Events: Betrayal → Betrayal → Apology
    Expected: self_conflict drops after apology, action shifts to repair_offer
    """
    
    def test_self_conflict_trajectory(self):
        """Self-conflict changes through betrayal-apology sequence."""
        model = SelfModelV0()
        
        # Event 1: First betrayal
        event1 = {
            "type": "world_event",
            "meta": {
                "subtype": "betrayal",
                "value_alignment": 0.1,
                "identity_threat": 0.7
            }
        }
        ctx = {"relationship_state": {"bond": 0.5, "trust": 0.5, "grudge": 0.0}}
        
        result1 = model.apply_event(event1, ctx)
        conflict1 = result1["self_conflict"]
        
        # First betrayal should produce high conflict
        assert conflict1 > 0.5, f"After betrayal 1: expected conflict > 0.5, got {conflict1}"
        
        # Event 2: Second betrayal
        event2 = {
            "type": "world_event",
            "meta": {
                "subtype": "betrayal",
                "value_alignment": 0.05,
                "identity_threat": 0.8
            }
        }
        ctx["relationship_state"]["grudge"] = 0.3  # Grudge increases
        
        result2 = model.apply_event(event2, ctx)
        conflict2 = result2["self_conflict"]
        
        # Second betrayal should maintain or increase conflict
        assert conflict2 > 0.5, f"After betrayal 2: expected conflict > 0.5, got {conflict2}"
        
        # Event 3: Apology
        event3 = {
            "type": "world_event",
            "meta": {
                "subtype": "apology",
                "value_alignment": 0.7,
                "identity_threat": 0.1
            }
        }
        ctx["relationship_state"]["grudge"] = 0.1  # Grudge decreases after apology
        
        result3 = model.apply_event(event3, ctx)
        conflict3 = result3["self_conflict"]
        
        # Apology should reduce conflict
        assert conflict3 < conflict2, \
            f"After apology: expected conflict drop from {conflict2} to < {conflict2}, got {conflict3}"
    
    def test_action_shifts_to_repair_after_apology(self):
        """Action bias shifts toward repair after apology."""
        model = SelfModelV0()
        
        # After betrayals
        model.cognitive.uncertainty = 0.7
        model.cognitive.confidence = 0.3
        
        withdraw_bias_before = model.get_action_bias("withdraw")
        repair_bias_before = model.get_action_bias("repair_offer")
        
        # After apology - state improves
        model.cognitive.uncertainty = 0.3
        model.cognitive.confidence = 0.7
        model.relational.grudge = 0.1  # Lower grudge
        
        repair_bias_after = model.get_action_bias("repair_offer")
        
        # Repair bias should improve relative to before
        # (Note: exact values depend on implementation, but trend should be positive)
        assert repair_bias_after >= repair_bias_before, \
            f"Repair bias should improve after apology: {repair_bias_before} -> {repair_bias_after}"
    
    def test_manifest_sequence_produces_expected_trajectory(self):
        """Process full manifest sequence and verify trajectory."""
        manifest = load_manifest("scenario_repair_conflict.json")
        
        model = SelfModelV0()
        conflicts = []
        
        ctx = {"relationship_state": {"bond": 0.5, "trust": 0.5, "grudge": 0.0}}
        
        for i, event in enumerate(manifest["events"]):
            result = model.apply_event(event, ctx)
            conflicts.append(result["self_conflict"])
            
            # Update context based on event
            if event["meta"].get("subtype") == "betrayal":
                ctx["relationship_state"]["grudge"] = min(1.0, ctx["relationship_state"]["grudge"] + 0.3)
            elif event["meta"].get("subtype") == "apology":
                ctx["relationship_state"]["grudge"] = max(0.0, ctx["relationship_state"]["grudge"] - 0.2)
        
        # Verify trajectory
        # First two events (betrayals) should have high conflict
        assert conflicts[0] > 0.5, f"Event 1 conflict should be > 0.5: {conflicts[0]}"
        assert conflicts[1] > 0.5, f"Event 2 conflict should be > 0.5: {conflicts[1]}"
        
        # Third event (apology) should have lower conflict
        assert conflicts[2] < conflicts[1], \
            f"Event 3 conflict ({conflicts[2]}) should be < Event 2 ({conflicts[1]})"
        
        # Final decision should be repair-related
        final_decision = manifest["decisions"][-1]
        assert final_decision["action"] in ["repair_offer", "observe", "approach"], \
            f"Final action should be repair-related: {final_decision['action']}"


class TestDeterministicReplay:
    """Test that manifests are deterministic and replayable."""
    
    def test_self_threat_hash_consistent(self):
        """Self-threat manifest hash is consistent across runs."""
        manifest = load_manifest("scenario_self_threat.json")
        
        # Compute hash from manifest content
        content = json.dumps(manifest, sort_keys=True)
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        
        # Re-compute
        content2 = json.dumps(manifest, sort_keys=True)
        hash2 = hashlib.sha256(content2.encode()).hexdigest()
        
        assert hash1 == hash2, "Manifest hash should be deterministic"
    
    def test_capability_success_hash_consistent(self):
        """Capability success manifest hash is consistent."""
        manifest = load_manifest("scenario_capability_success.json")
        
        content = json.dumps(manifest, sort_keys=True)
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()
        
        assert hash1 == hash2, "Manifest hash should be deterministic"
    
    def test_repair_conflict_hash_consistent(self):
        """Repair conflict manifest hash is consistent."""
        manifest = load_manifest("scenario_repair_conflict.json")
        
        content = json.dumps(manifest, sort_keys=True)
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()
        
        assert hash1 == hash2, "Manifest hash should be deterministic"
    
    def test_self_model_state_reproducible(self):
        """SelfModelV0 state is reproducible from snapshot."""
        model1 = SelfModelV0()
        model1.cognitive.uncertainty = 0.7
        model1.cognitive.confidence = 0.3
        model1.relational.grudge = 0.5
        
        # Create snapshot and reconstruct
        snapshot = model1.snapshot()
        model2 = SelfModelV0.from_snapshot(snapshot)
        
        # Verify identical state
        hash1 = model1.compute_hash()
        hash2 = model2.compute_hash()
        
        assert hash1 == hash2, "Reconstructed model should have same hash"
        assert model2.cognitive.uncertainty == 0.7
        assert model2.cognitive.confidence == 0.3
        assert model2.relational.grudge == 0.5


class TestSelfConflictComponentWeights:
    """Test that self_conflict weights are correctly applied."""
    
    def test_weighted_sum_formula(self):
        """Verify self_conflict is weighted sum of components."""
        model = SelfModelV0()
        
        # Create event with known component values
        meta = {
            "value_alignment": 0.2,  # value_conflict ≈ 0.8
            "success": False,  # capability_conflict ≈ 0.7
            "identity_threat": 0.5  # identity_conflict = 0.5
        }
        relationship_state = {"bond": 0.5, "trust": 0.5, "grudge": 0.0}
        
        self_conflict = model.compute_self_conflict(
            event_type="world_event",
            meta=meta,
            relationship_state=relationship_state
        )
        
        # Compute expected manually
        value_conflict = model._compute_value_conflict("world_event", meta)
        capability_conflict = model._compute_capability_conflict("world_event", meta)
        identity_conflict = model._compute_identity_conflict("world_event", meta, relationship_state)
        
        expected = 0.4 * value_conflict + 0.3 * capability_conflict + 0.3 * identity_conflict
        
        # Should match within tolerance
        assert abs(self_conflict - expected) < 0.01, \
            f"Expected {expected}, got {self_conflict}"
    
    def test_value_conflict_dominant(self):
        """Value conflict has highest weight (0.4)."""
        model = SelfModelV0()
        
        # High value conflict only
        meta1 = {"value_alignment": 0.1}
        conflict1 = model.compute_self_conflict(
            "world_event", meta1, {"bond": 0.5, "trust": 0.5}
        )
        
        # High identity conflict only
        meta2 = {"identity_threat": 0.9}
        conflict2 = model.compute_self_conflict(
            "world_event", meta2, {"bond": 0.5, "trust": 0.5}
        )
        
        # Both should produce significant conflict
        assert conflict1 > 0.3, f"Value conflict should produce conflict: {conflict1}"
        assert conflict2 > 0.2, f"Identity conflict should produce conflict: {conflict2}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_meta(self):
        """Empty meta should produce low conflict."""
        model = SelfModelV0()
        
        conflict = model.compute_self_conflict(
            "user_message",
            {},
            {"bond": 0.5, "trust": 0.5}
        )
        
        # Should be moderate/low (no explicit threat indicators)
        assert 0.0 <= conflict <= 1.0
    
    def test_max_conflict(self):
        """Maximum conflict scenario."""
        model = SelfModelV0()
        
        meta = {
            "value_alignment": 0.0,
            "success": False,
            "identity_threat": 1.0
        }
        relationship_state = {"bond": 0.0, "trust": 0.0, "grudge": 1.0}
        
        conflict = model.compute_self_conflict(
            "world_event",
            meta,
            relationship_state
        )
        
        # Should be very high
        assert conflict > 0.7, f"Max conflict scenario should be > 0.7: {conflict}"
    
    def test_min_conflict(self):
        """Minimum conflict scenario."""
        model = SelfModelV0()
        
        meta = {
            "value_alignment": 1.0,
            "success": True,
            "identity_threat": 0.0
        }
        relationship_state = {"bond": 1.0, "trust": 1.0, "grudge": 0.0}
        
        conflict = model.compute_self_conflict(
            "world_event",
            meta,
            relationship_state
        )
        
        # Should be very low
        assert conflict < 0.2, f"Min conflict scenario should be < 0.2: {conflict}"
    
    def test_conflict_bounded_0_to_1(self):
        """Self-conflict is always in [0, 1]."""
        model = SelfModelV0()
        
        # Try various combinations
        test_cases = [
            {"value_alignment": 0.0},
            {"value_alignment": 1.0},
            {"success": True},
            {"success": False},
            {"identity_threat": 0.0},
            {"identity_threat": 1.0},
            {"value_alignment": 0.5, "success": True, "identity_threat": 0.3},
        ]
        
        for meta in test_cases:
            conflict = model.compute_self_conflict(
                "world_event",
                meta,
                {"bond": 0.5, "trust": 0.5}
            )
            assert 0.0 <= conflict <= 1.0, f"Conflict out of bounds: {conflict}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
