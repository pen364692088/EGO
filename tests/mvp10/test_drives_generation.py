"""
T10 - Drives Generation Tests

Tests for the Drives module:
- DriveType enum
- Drives class: maintain drive levels, generate candidates
- State delta logging
"""
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.drives import (
    DriveType, DriveLevel, DriveCandidate, Drives, drives_from_valence,
)


class TestDriveType:
    """Test DriveType enum."""
    
    def test_drive_types_exist(self):
        """Test that all required drive types exist."""
        assert DriveType.COMPETENCE.value == "competence"
        assert DriveType.COHERENCE.value == "coherence"
        assert DriveType.EFFICIENCY.value == "efficiency"
        assert DriveType.SAFETY.value == "safety"
        assert DriveType.CURIOSITY.value == "curiosity"
    
    def test_drive_type_count(self):
        """Test that there are exactly 5 drive types."""
        assert len(DriveType) == 5


class TestDriveLevel:
    """Test DriveLevel dataclass."""
    
    def test_drive_level_creation(self):
        """Test creating a DriveLevel."""
        level = DriveLevel(drive_type=DriveType.COMPETENCE, level=0.5)
        assert level.drive_type == DriveType.COMPETENCE
        assert level.level == 0.5
        assert level.last_updated > 0
    
    def test_drive_level_to_dict(self):
        """Test DriveLevel serialization."""
        level = DriveLevel(drive_type=DriveType.SAFETY, level=0.3)
        d = level.to_dict()
        
        assert d["drive_type"] == "safety"
        assert d["level"] == 0.3
        assert "last_updated" in d
    
    def test_drive_level_from_dict(self):
        """Test DriveLevel deserialization."""
        d = {"drive_type": "curiosity", "level": 0.7, "last_updated": 12345.0}
        level = DriveLevel.from_dict(d)
        
        assert level.drive_type == DriveType.CURIOSITY
        assert level.level == 0.7
        assert level.last_updated == 12345.0


class TestDriveCandidate:
    """Test DriveCandidate dataclass."""
    
    def test_candidate_creation(self):
        """Test creating a DriveCandidate."""
        candidate = DriveCandidate(
            id="test_candidate",
            drive_type=DriveType.COMPETENCE,
            score=0.8,
            description="Fix the bug",
            meta={"urgency": 0.5},
        )
        assert candidate.id == "test_candidate"
        assert candidate.drive_type == DriveType.COMPETENCE
        assert candidate.score == 0.8
    
    def test_candidate_to_dict(self):
        """Test DriveCandidate serialization."""
        candidate = DriveCandidate(
            id="test",
            drive_type=DriveType.CURIOSITY,
            score=0.5,
            description="Explore",
        )
        d = candidate.to_dict()
        
        assert d["id"] == "test"
        assert d["drive_type"] == "curiosity"
        assert d["score"] == 0.5


class TestDrives:
    """Test Drives class."""
    
    def test_drives_initialization(self):
        """Test default Drives initialization."""
        drives = Drives()
        
        # All drive types should be initialized
        for dt in DriveType:
            assert dt in drives.levels
            assert drives.levels[dt].level == 0.5  # Default level
    
    def test_drives_custom_initialization(self):
        """Test Drives initialization with custom levels."""
        drives = Drives(
            initial_levels={
                DriveType.COMPETENCE: 0.3,
                DriveType.SAFETY: 0.8,
            }
        )
        
        assert drives.get_level(DriveType.COMPETENCE) == 0.3
        assert drives.get_level(DriveType.SAFETY) == 0.8
        assert drives.get_level(DriveType.CURIOSITY) == 0.5  # Default
    
    def test_set_level(self):
        """Test setting drive level."""
        drives = Drives()
        
        delta = drives.set_level(DriveType.COMPETENCE, 0.2, "test_reason")
        
        assert drives.get_level(DriveType.COMPETENCE) == 0.2
        assert delta["before"] == 0.5
        assert delta["after"] == 0.2
        assert delta["reason"] == "test_reason"
    
    def test_set_level_clamping(self):
        """Test that set_level clamps values to [0, 1]."""
        drives = Drives()
        
        drives.set_level(DriveType.COMPETENCE, 1.5)
        assert drives.get_level(DriveType.COMPETENCE) == 1.0
        
        drives.set_level(DriveType.COMPETENCE, -0.5)
        assert drives.get_level(DriveType.COMPETENCE) == 0.0
    
    def test_update_from_outcome_success(self):
        """Test updating drives after success outcome."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.5, "init")
        
        deltas = drives.update_from_outcome("success", {})
        
        # Success should increase competence
        assert drives.get_level(DriveType.COMPETENCE) > 0.5
        assert len(deltas) >= 1
    
    def test_update_from_outcome_fail(self):
        """Test updating drives after failure outcome."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.5, "init")
        drives.set_level(DriveType.CURIOSITY, 0.5, "init")
        
        deltas = drives.update_from_outcome("fail", {})
        
        # Failure should decrease competence
        assert drives.get_level(DriveType.COMPETENCE) < 0.5
        # Failure should increase curiosity (need to learn)
        assert drives.get_level(DriveType.CURIOSITY) > 0.5
    
    def test_update_from_outcome_fail_high_risk(self):
        """Test updating drives after high-risk failure."""
        drives = Drives()
        drives.set_level(DriveType.SAFETY, 0.5, "init")
        
        drives.update_from_outcome("fail", {"risk_level": "high"})
        
        # High-risk failure should decrease safety
        assert drives.get_level(DriveType.SAFETY) < 0.5
    
    def test_generate_candidates_low_drives(self):
        """Test generating candidates when drives are low."""
        drives = Drives()
        
        # Set competence to low value
        drives.set_level(DriveType.COMPETENCE, 0.1, "test")
        
        candidates = drives.generate_candidates()
        
        # Should generate candidates for low competence
        competence_candidates = [c for c in candidates if c.drive_type == DriveType.COMPETENCE]
        assert len(competence_candidates) > 0
        
        # Candidates should have non-zero scores
        for c in competence_candidates:
            assert c.score > 0
    
    def test_generate_candidates_normal_drives(self):
        """Test generating candidates when drives are normal."""
        drives = Drives()
        
        # All drives at 0.5 (default), which is above most thresholds
        candidates = drives.generate_candidates()
        
        # Fewer candidates when drives are satisfied
        assert len(candidates) <= 3  # Curiosity threshold is 0.5, so may have some
    
    def test_generate_candidates_sorted_by_score(self):
        """Test that candidates are sorted by score."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.1, "test")
        drives.set_level(DriveType.SAFETY, 0.1, "test")
        
        candidates = drives.generate_candidates()
        
        # Should be sorted by score descending
        for i in range(len(candidates) - 1):
            assert candidates[i].score >= candidates[i + 1].score
    
    def test_generate_candidates_context_modifiers(self):
        """Test that context modifies candidate scores."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.1, "test")
        
        candidates_normal = drives.generate_candidates({})
        candidates_failure = drives.generate_candidates({"has_failure": True})
        
        # With failure context, competence candidates should be boosted
        comp_normal = [c for c in candidates_normal if c.drive_type == DriveType.COMPETENCE]
        comp_failure = [c for c in candidates_failure if c.drive_type == DriveType.COMPETENCE]
        
        if comp_normal and comp_failure:
            # Failure context should boost scores
            assert comp_failure[0].score >= comp_normal[0].score
    
    def test_get_low_drives(self):
        """Test identifying low drives."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.1, "test")
        drives.set_level(DriveType.SAFETY, 0.8, "test")
        
        low_drives = drives.get_low_drives()
        
        assert DriveType.COMPETENCE in low_drives
        assert DriveType.SAFETY not in low_drives
    
    def test_state_delta_log(self):
        """Test state delta logging."""
        drives = Drives()
        
        drives.set_level(DriveType.COMPETENCE, 0.3, "test1")
        drives.set_level(DriveType.SAFETY, 0.7, "test2")
        
        log = drives.get_state_delta_log()
        
        assert len(log) == 2
        assert log[0]["reason"] == "test1"
        assert log[1]["reason"] == "test2"
        
        drives.clear_state_delta_log()
        assert len(drives.get_state_delta_log()) == 0
    
    def test_drives_serialization(self):
        """Test Drives serialization."""
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.3, "test")
        
        d = drives.to_dict()
        
        assert "levels" in d
        assert "thresholds" in d
        assert d["levels"]["competence"]["level"] == 0.3
        
        restored = Drives.from_dict(d)
        assert restored.get_level(DriveType.COMPETENCE) == 0.3


class TestDrivesFromValence:
    """Test drives_from_valence function."""
    
    def test_positive_valence(self):
        """Test that positive valence produces higher competence."""
        levels_pos = drives_from_valence(0.5)
        levels_neg = drives_from_valence(-0.5)
        
        # Positive valence should produce higher competence
        assert levels_pos[DriveType.COMPETENCE] > levels_neg[DriveType.COMPETENCE]
        
        # Negative valence should produce higher curiosity
        assert levels_neg[DriveType.CURIOSITY] > levels_pos[DriveType.CURIOSITY]
    
    def test_neutral_valence(self):
        """Test neutral valence produces moderate levels."""
        levels = drives_from_valence(0.0)
        
        # All levels should be in reasonable range
        for level in levels.values():
            assert 0.2 <= level <= 0.8
    
    def test_valence_range(self):
        """Test that function handles full valence range."""
        for v in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            levels = drives_from_valence(v)
            
            # All levels should be in [0, 1]
            for level in levels.values():
                assert 0.0 <= level <= 1.0


class TestDrivesIntegration:
    """Integration tests for Drives module."""
    
    def test_full_workflow(self):
        """Test full workflow: init → update → generate → serialize."""
        drives = Drives()
        
        # Initial state
        assert drives.get_level(DriveType.COMPETENCE) == 0.5
        
        # Simulate failure outcome (competence drops by 0.15, from 0.5 to 0.35)
        drives.update_from_outcome("fail", {"risk_level": "medium"})
        
        # Check competence decreased
        assert drives.get_level(DriveType.COMPETENCE) < 0.5
        
        # Set competence to be below threshold to ensure candidates are generated
        drives.set_level(DriveType.COMPETENCE, 0.2, "ensure_below_threshold")
        
        # Generate candidates
        candidates = drives.generate_candidates({"has_failure": True})
        assert len(candidates) > 0
        
        # Check state delta logged
        log = drives.get_state_delta_log()
        assert len(log) > 0
        
        # Serialize and restore
        restored = Drives.from_dict(drives.to_dict())
        assert restored.get_level(DriveType.COMPETENCE) == drives.get_level(DriveType.COMPETENCE)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
