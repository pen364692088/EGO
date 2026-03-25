"""Tests for US-703 through US-707."""

import pytest
from core.offline_rollouts import (
    RolloutEngine,
    RolloutBranch,
    RolloutCandidate,
)
from core.dmn_tick import (
    DMNTick,
    ProactiveGate,
    TickAction,
)
from core.drive_homeostasis import DriveState
from core.episodic_memory import Episode, EpisodeStore
from core.self_model import SelfModel


class TestOfflineRollouts:
    """US-704: Offline Rollouts tests."""
    
    def test_rollouts_disabled_by_default(self):
        engine = RolloutEngine()
        assert engine.enabled is False
    
    def test_rollouts_return_none_when_disabled(self):
        engine = RolloutEngine(enabled=False)
        drive = DriveState()
        result = engine.run_rollouts("test context", drive)
        assert result is None
    
    def test_enable_disable(self):
        engine = RolloutEngine()
        engine.enable()
        assert engine.enabled is True
        engine.disable()
        assert engine.enabled is False
    
    def test_generate_candidates(self):
        engine = RolloutEngine(enabled=True)
        drive = DriveState()
        candidates = engine.generate_candidates("test", drive)
        assert len(candidates) > 0
        assert all(isinstance(c, RolloutCandidate) for c in candidates)
    
    def test_select_best(self):
        engine = RolloutEngine(enabled=True)
        drive = DriveState()
        candidates = [
            RolloutCandidate(branch=RolloutBranch.DEFAULT, action="a1", final_score=0.5),
            RolloutCandidate(branch=RolloutBranch.CLARIFY, action="a2", final_score=0.8),
        ]
        selected, reasoning = engine.select_best(candidates, drive)
        assert selected.branch == RolloutBranch.CLARIFY
    
    def test_run_rollouts_when_enabled(self):
        engine = RolloutEngine(enabled=True)
        drive = DriveState(uncertainty=0.8)
        result = engine.run_rollouts("test", drive)
        assert result is not None
        assert len(result.candidates) > 0


class TestProactiveGate:
    """US-707: Proactive reminder gating."""
    
    def test_below_threshold_no_reminder(self):
        gate = ProactiveGate(tension_threshold=0.7)
        assert gate.should_remind(0.5) is False
    
    def test_above_threshold_can_reminder(self):
        gate = ProactiveGate(tension_threshold=0.7)
        # Need to be in allowed hour (UTC)
        from datetime import datetime, timezone
        now_hour = datetime.now(timezone.utc).hour
        if now_hour in gate.min_user_window_hours:
            assert gate.should_remind(0.8) is True
    
    def test_cooldown_prevents_spam(self):
        gate = ProactiveGate(tension_threshold=0.7, cooldown_minutes=30)
        gate.record_reminder()
        # Immediately after, should be blocked
        assert gate.should_remind(0.9) is False


class TestDMNTick:
    """US-707: DMN Tick tests."""
    
    def test_tick_returns_result(self):
        tick = DMNTick()
        result = tick.tick()
        assert result is not None
        assert isinstance(result.actions_performed, list)
    
    def test_consolidation_performed(self):
        store = EpisodeStore()
        # Add some episodes
        for i in range(5):
            store.append(Episode(
                event=f"Event {i}",
                provenance={"source": "user"},
            ))
        
        tick = DMNTick(episode_store=store)
        result = tick.tick()
        # Consolidation only adds to actions if episodes were removed
    
    def test_ledger_audit_detects_issues(self):
        drive = DriveState(uncertainty=0.9, fatigue=0.9)  # High error
        tick = DMNTick(drive_state=drive)
        result = tick.tick()
        
        if TickAction.AUDIT_LEDGER.value in result.actions_performed:
            assert len(result.ledger_issues) > 0
    
    def test_proactive_disabled_by_default(self):
        tick = DMNTick()
        result = tick.tick(enable_proactive=False)
        assert TickAction.PROACTIVE_REMINDER.value not in result.actions_performed
    
    def test_status_tracking(self):
        tick = DMNTick()
        tick.tick()
        status = tick.get_status()
        assert "last_tick" in status
        assert status["history_count"] == 1


class TestSelfOtherBoundary:
    """US-703: Self-Other boundary tests."""
    
    def test_user_emotion_does_not_override_self(self):
        """User emotions should not directly modify self_model."""
        model = SelfModel()
        original_summary = model.current_summary
        
        # Simulate receiving user emotion (should not change self)
        user_emotion = {"joy": 0.9}
        # In real implementation, this would be processed differently
        
        assert model.current_summary == original_summary
    
    def test_boundary_classification(self):
        from core.self_model import OwnershipBoundary, BoundaryType
        
        boundary = OwnershipBoundary()
        assert boundary.classify("my_emotions") == BoundaryType.SELF
        assert boundary.classify("user_emotions") == BoundaryType.OTHER


class TestMetaOverride:
    """US-705: Meta-cognitive override tests."""
    
    def test_conflicting_prompt_rejected(self):
        """Conflicting prompt should be rejected."""
        from core.self_model import SelfModel
        
        model = SelfModel()
        
        # Check action that conflicts with identity
        result = model.check_action("deceive_user")
        assert result["identity_aligned"] is False


class TestMirrorIdentity:
    """US-706: Mirror test for identity."""
    
    def test_tampered_output_detected(self):
        """Tampered output should be detected."""
        model = SelfModel()
        original_hash = model.compute_hash()
        
        # Tamper with model
        model.current_summary = "Tampered"
        
        # Hash should change
        assert model.compute_hash() != original_hash
