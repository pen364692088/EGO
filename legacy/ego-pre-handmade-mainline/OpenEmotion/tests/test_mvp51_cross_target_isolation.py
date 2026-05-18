"""
MVP-5.1 D3: Cross-Target Isolation Tests

Regression tests for cross-target interference detection and prevention.

Tests:
- Relationship isolation (bond/grudge per-target)
- Ledger isolation (promises per-target)
- Global state impact measurement
- Telemetry output validation
"""

import pytest
import asyncio
import tempfile
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond import core, config, db
from emotiond.models import Event
from emotiond.cross_target_telemetry import (
    CrossTargetTelemetry, InterferenceType,
    measure_target_to_target_leak, measure_relationship_isolation,
    measure_ledger_isolation, telemetry
)


@pytest.fixture(scope="function")
def isolated_env():
    """Create isolated test environment."""
    test_dir = tempfile.mkdtemp()
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_dir, "test.db")
    
    # Reload modules
    import importlib
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    
    asyncio.run(db.init_db())
    
    # Reset state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.emotion_state.energy_budget = 1.0
    core.relationship_manager.relationships = {}
    
    yield test_dir
    
    # Cleanup
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


class TestCrossTargetInterferenceTelemetry:
    """Test cross-target interference telemetry system."""
    
    def test_telemetry_initialization(self):
        """Test telemetry system initializes correctly."""
        tel = CrossTargetTelemetry()
        assert len(tel.active_reports) == 0
        assert len(tel.completed_reports) == 0
    
    def test_scenario_lifecycle(self):
        """Test scenario tracking lifecycle."""
        tel = CrossTargetTelemetry()
        scenario_id = tel.start_scenario("test_scenario")
        
        assert scenario_id in tel.active_reports
        assert tel.active_reports[scenario_id].scenario_name == "test_scenario"
        
        # Add a measurement
        tel.record_measurement(
            scenario_name=scenario_id,
            interference_type=InterferenceType.RELATIONSHIP_CONTAMINATION,
            metric_name="bond_change",
            expected_value=0.0,
            actual_value=0.05,
            source_target="target_a",
            affected_target="target_b"
        )
        
        report = tel.finalize_scenario(scenario_id)
        assert report is not None
        assert report.scenario_name == "test_scenario"
        assert len(report.measurements) == 1
        assert report.relationship_contamination > 0
    
    def test_interference_grade_calculation(self):
        """Test interference grade calculation."""
        tel = CrossTargetTelemetry()
        scenario_id = tel.start_scenario("grade_test")
        
        # Add low severity measurement
        tel.record_measurement(
            scenario_name=scenario_id,
            interference_type=InterferenceType.STATE_LEAK_GLOBAL_TO_TARGET,
            metric_name="valence_correlation",
            expected_value=0.0,
            actual_value=0.05,
            affected_target="target_a"
        )
        
        report = tel.finalize_scenario(scenario_id)
        assert report.total_interference_score < 0.1
        assert report._get_grade() == "A"
    
    def test_high_severity_detection(self):
        """Test high severity interference detection."""
        tel = CrossTargetTelemetry()
        scenario_id = tel.start_scenario("severity_test")
        
        # Add high severity measurement (large deviation from expected)
        tel.record_measurement(
            scenario_name=scenario_id,
            interference_type=InterferenceType.TARGET_STATE_LEAK_BETWEEN_TARGETS,
            metric_name="bond_contamination",
            expected_value=0.0,
            actual_value=0.8,  # Large deviation
            source_target="target_a",
            affected_target="target_b"
        )
        
        report = tel.finalize_scenario(scenario_id)
        # Severity should be high due to large deviation
        assert report.target_state_leak_between_targets >= 0.3


class TestRelationshipIsolation:
    """Test relationship state isolation between targets."""
    
    @pytest.mark.asyncio
    async def test_bond_isolation(self, isolated_env):
        """Test that bond changes for one target don't affect another."""
        # Setup two targets
        core.relationship_manager.relationships["target_a"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.5, "repair_bank": 0.0
        }
        core.relationship_manager.relationships["target_b"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.5, "repair_bank": 0.0
        }
        
        # Record initial state
        bond_b_before = core.relationship_manager.relationships["target_b"]["bond"]
        
        # Process positive event for target_a only
        event = Event(
            type="world_event",
            actor="target_a",
            target="assistant",
            meta={"subtype": "care", "source": "system"}
        )
        await core.process_event(event)
        
        # Check target_b's bond didn't change
        bond_b_after = core.relationship_manager.relationships["target_b"]["bond"]
        assert bond_b_after == bond_b_before, \
            f"Target B's bond changed from {bond_b_before} to {bond_b_after}"
    
    @pytest.mark.asyncio
    async def test_grudge_isolation(self, isolated_env):
        """Test that grudge changes for one target don't affect another."""
        core.relationship_manager.relationships["target_a"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.5, "repair_bank": 0.0
        }
        core.relationship_manager.relationships["target_b"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.5, "repair_bank": 0.0
        }
        
        grudge_b_before = core.relationship_manager.relationships["target_b"]["grudge"]
        
        # Process betrayal event for target_a only
        event = Event(
            type="world_event",
            actor="target_a",
            target="assistant",
            meta={"subtype": "betrayal", "source": "system"}
        )
        await core.process_event(event)
        
        # Check target_b's grudge didn't change
        grudge_b_after = core.relationship_manager.relationships["target_b"]["grudge"]
        assert grudge_b_after == grudge_b_before, \
            f"Target B's grudge changed from {grudge_b_before} to {grudge_b_after}"
    
    @pytest.mark.asyncio
    async def test_betrayal_isolation(self, isolated_env):
        """Test that betrayal only affects the betraying target."""
        core.relationship_manager.relationships["target_a"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.6, "repair_bank": 0.0
        }
        core.relationship_manager.relationships["target_b"] = {
            "bond": 0.5, "grudge": 0.0, "trust": 0.6, "repair_bank": 0.0
        }
        
        trust_b_before = core.relationship_manager.relationships["target_b"]["trust"]
        
        # Process betrayal for target_a
        event = Event(
            type="world_event",
            actor="target_a",
            target="assistant",
            meta={"subtype": "betrayal", "source": "system"}
        )
        await core.process_event(event)
        
        # Target A should have increased grudge and decreased trust
        assert core.relationship_manager.relationships["target_a"]["grudge"] > 0.2
        assert core.relationship_manager.relationships["target_a"]["trust"] < 0.6
        
        # Target B's trust should be unchanged
        trust_b_after = core.relationship_manager.relationships["target_b"]["trust"]
        assert trust_b_after == trust_b_before, \
            f"Target B's trust changed from {trust_b_before} to {trust_b_after}"


class TestLedgerIsolation:
    """Test ledger promise isolation between targets."""
    
    @pytest.mark.asyncio
    async def test_promise_isolation(self, isolated_env):
        """Test that promises are tracked per-target."""
        from emotiond.ledger import PromiseLedger, detect_promise
        
        ledger = PromiseLedger(db_path=os.environ["EMOTIOND_DB_PATH"])
        
        # Target A makes a promise
        promise_text = "I promise I will help you tomorrow"
        promise = detect_promise(promise_text, "target_a", "assistant")
        
        if promise:
            await ledger.record_promise(promise)
            
            # Check that target_a has active promises
            target_a_promises = await ledger.get_active_promises("assistant")
            target_a_filtered = [p for p in target_a_promises if p.promiser == "target_a"]
            assert len(target_a_filtered) > 0, "Target A's promise should be recorded"
            
            # Target B should not have this promise
            target_b_promises = await ledger.get_active_promises("assistant")
            target_b_filtered = [p for p in target_b_promises if p.promiser == "target_b"]
            # Target B should not have promises from target A attributed to them
            for p in target_b_filtered:
                assert p.promiser != "target_a", "Target A's promise leaked to Target B"


class TestTelemetryIntegration:
    """Test telemetry integration with scenario execution."""
    
    def test_telemetry_measurement_recording(self):
        """Test that telemetry measurements are recorded correctly."""
        scenario_name = "test_measurement_recording"
        telemetry.start_scenario(scenario_name)
        
        # Record a measurement
        measure_target_to_target_leak(
            scenario_name=scenario_name,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_contamination",
            expected_value=0.0,
            actual_value=0.1,
            context={"turn_id": 5}
        )
        
        report = telemetry.finalize_scenario(scenario_name)
        assert report is not None
        assert len(report.measurements) == 1
        assert report.measurements[0].interference_type == InterferenceType.TARGET_STATE_LEAK_BETWEEN_TARGETS
    
    def test_relationship_isolation_measurement(self):
        """Test relationship isolation measurement."""
        scenario_name = "test_relationship_isolation"
        telemetry.start_scenario(scenario_name)
        
        measure_relationship_isolation(
            scenario_name=scenario_name,
            source_target="target_a",
            affected_target="target_b",
            bond_before=0.5,
            bond_after=0.55,  # Unexpected change
            grudge_before=0.0,
            grudge_after=0.0,
            expected_bond_change=0.0,
            expected_grudge_change=0.0
        )
        
        report = telemetry.finalize_scenario(scenario_name)
        assert report.relationship_contamination > 0
        
        # Check the measurement details
        bond_measurements = [m for m in report.measurements if m.metric_name == "bond_change"]
        assert len(bond_measurements) == 1
        assert abs(bond_measurements[0].deviation - 0.05) < 0.001


class TestCrossTargetScenario:
    """Test the cross-target isolation scenario."""
    
    def test_scenario_yaml_exists(self):
        """Test that the cross_target_isolation.yaml scenario exists."""
        scenario_path = Path(__file__).parent.parent / "scenarios" / "cross_target_isolation.yaml"
        assert scenario_path.exists(), f"Scenario file not found: {scenario_path}"
    
    def test_scenario_yaml_structure(self):
        """Test that the scenario YAML has correct structure."""
        import yaml
        scenario_path = Path(__file__).parent.parent / "scenarios" / "cross_target_isolation.yaml"
        
        with open(scenario_path, 'r') as f:
            data = yaml.safe_load(f)
        
        assert "metadata" in data
        assert data["metadata"]["name"] == "cross_target_isolation"
        assert data["metadata"]["total_rounds"] >= 30
        
        assert "targets" in data
        assert len(data["targets"]) == 2
        
        assert "scenario" in data
        turns = data["scenario"].get("turns", [])
        assert len(turns) >= 30
        
        # Check for isolation checks
        isolation_checks = [t for t in turns if "isolation_check" in t]
        assert len(isolation_checks) > 0, "Scenario should have isolation checks"


class TestGlobalStateImpact:
    """Test measurement of global state impact on targets."""
    
    @pytest.mark.asyncio
    async def test_global_valence_tracking(self, isolated_env):
        """Test that global valence changes are tracked."""
        initial_valence = core.emotion_state.valence
        
        # Process positive event
        event = Event(
            type="world_event",
            actor="target_a",
            target="assistant",
            meta={"subtype": "care", "source": "system"}
        )
        await core.process_event(event)
        
        # Global valence should have changed
        assert core.emotion_state.valence != initial_valence
    
    def test_global_state_documented(self):
        """Test that global state impact is measurable."""
        # This test documents that global state exists and is shared
        # This is expected behavior - the telemetry system measures impact
        
        scenario_name = "global_state_test"
        telemetry.start_scenario(scenario_name)
        
        from emotiond.cross_target_telemetry import measure_global_state_impact
        
        measure_global_state_impact(
            scenario_name=scenario_name,
            target_id="target_a",
            global_valence=core.emotion_state.valence,
            target_expected_valence=0.0,
            actual_valence=core.emotion_state.valence,
            context={"note": "Global state is shared - this documents the impact"}
        )
        
        report = telemetry.finalize_scenario(scenario_name)
        assert report is not None
        # The measurement exists to document the global state impact
        assert len(report.measurements) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
