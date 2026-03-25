"""
MVP-3 C3: Explanation Consistency Tests

Tests for structured explanations (C1-C3).
"""
import pytest
import os
import sys
import tempfile
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.db import (
    init_db, get_last_decision, save_decision, 
    get_state, update_state, load_predictions
)
import emotiond.core as core
from emotiond.config import ACTION_SPACE, TEST_MODE


@pytest.fixture(autouse=True, scope="function")
def setup_test_db_sync():
    """Setup isolated test database for each test (sync wrapper)."""
    from emotiond import daemon
    
    # Reset daemon_manager state (in case previous test left it running)
    daemon.daemon_manager.running = False
    daemon.daemon_manager.loops = {}
    
    # Get or create event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_emotiond.db")
        os.environ["EMOTIOND_DB_PATH"] = db_path
        os.environ["EMOTIOND_TEST_MODE"] = "1"
        
        # Reset state BEFORE any async operations
        core.emotion_state.valence = 0.0
        core.emotion_state.arousal = 0.3
        core.emotion_state.anger = 0.0
        core.emotion_state.sadness = 0.0
        core.emotion_state.anxiety = 0.0
        core.emotion_state.joy = 0.0
        core.emotion_state.loneliness = 0.0
        core.emotion_state.social_safety = 0.6
        core.emotion_state.energy = 0.7
        core.relationship_manager.relationships = {}
        core.relationship_manager.last_actions = {}
        
        # Clear predictions
        core._predictions.clear()
        
        # Run async setup
        loop.run_until_complete(init_db())
        loop.run_until_complete(core.load_initial_state())
        
        yield db_path
        
        # Cleanup
        if "EMOTIOND_DB_PATH" in os.environ:
            del os.environ["EMOTIOND_DB_PATH"]
        if "EMOTIOND_TEST_MODE" in os.environ:
            del os.environ["EMOTIOND_TEST_MODE"]


class TestExplanationStructure:
    """C1: Test explanation structure is correct."""
    
    @pytest.mark.asyncio
    async def test_explanation_has_required_fields(self):
        """Explanation must have all required top-level fields."""
        # Setup a relationship
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        assert "emotion" in explanation, "Missing 'emotion' field"
        assert "interoception" in explanation, "Missing 'interoception' field"
        assert "relationships" in explanation, "Missing 'relationships' field"
        assert "candidates" in explanation, "Missing 'candidates' field"
        assert "selected" in explanation, "Missing 'selected' field"
    
    @pytest.mark.asyncio
    async def test_emotion_section_structure(self):
        """Emotion section must have top2 and all."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        assert "top2" in explanation["emotion"], "Missing 'top2' in emotion"
        assert "all" in explanation["emotion"], "Missing 'all' in emotion"
        assert isinstance(explanation["emotion"]["top2"], list)
        assert isinstance(explanation["emotion"]["all"], dict)
    
    @pytest.mark.asyncio
    async def test_interoception_has_safety_and_energy(self):
        """Interoception section must have social_safety and energy."""
        core.emotion_state.social_safety = 0.45
        core.emotion_state.energy = 0.6
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        assert "social_safety" in explanation["interoception"], "Missing 'social_safety'"
        assert "energy" in explanation["interoception"], "Missing 'energy'"
        assert explanation["interoception"]["social_safety"] == 0.45
        assert explanation["interoception"]["energy"] == 0.6
    
    @pytest.mark.asyncio
    async def test_relationships_for_target(self):
        """Relationships section must have correct fields for target."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.4, "grudge": 0.3, "trust": 0.2, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        rel = explanation["relationships"]
        assert rel["bond"] == 0.4
        assert rel["grudge"] == 0.3
        assert rel["trust"] == 0.2
        assert rel["repair_bank"] == 0.1


class TestTop3CandidatesMatchScoreRanking:
    """C3: Test that top 3 candidates match score ranking."""
    
    @pytest.mark.asyncio
    async def test_candidates_sorted_by_score_descending(self):
        """Candidates should be sorted by score descending."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        candidates = explanation["candidates"]
        
        # Should have at least 2 candidates
        assert len(candidates) >= 2, "Should have at least 2 candidates"
        
        # Should be sorted by score descending
        for i in range(len(candidates) - 1):
            assert candidates[i]["score"] >= candidates[i + 1]["score"], \
                "Candidates not sorted by score descending"
    
    @pytest.mark.asyncio
    async def test_candidates_have_required_fields(self):
        """Each candidate must have action, score, predicted_delta, reasons."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        candidates = explanation["candidates"]
        
        for candidate in candidates:
            assert "action" in candidate, "Missing 'action' in candidate"
            assert "score" in candidate, "Missing 'score' in candidate"
            assert "predicted_delta" in candidate, "Missing 'predicted_delta' in candidate"
            assert "reasons" in candidate, "Missing 'reasons' in candidate"
    
    @pytest.mark.asyncio
    async def test_candidates_have_valid_scores(self):
        """All candidates should have valid numeric scores."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        # Get explanation
        explanation = await core.generate_explanation("user", test_mode=True)
        candidates = explanation["candidates"]
        
        # Verify all scores are numeric and valid
        for candidate in candidates:
            assert isinstance(candidate["score"], (int, float)), \
                f"Score for {candidate['action']} is not numeric: {candidate['score']}"
            assert len(candidates) <= 3, "Should have at most 3 candidates"


class TestReasonsAreNotEmpty:
    """C3: Test that reasons are not empty."""
    
    @pytest.mark.asyncio
    async def test_candidate_reasons_not_empty(self):
        """Each candidate should have at least one reason."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        candidates = explanation["candidates"]
        
        for candidate in candidates:
            assert len(candidate["reasons"]) > 0, \
                f"Candidate {candidate['action']} has no reasons"
    
    @pytest.mark.asyncio
    async def test_selection_reasons_not_empty(self):
        """Selection should have at least one reason."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        assert len(explanation["selection_reasons"]) > 0, "No selection reasons"
    
    @pytest.mark.asyncio
    async def test_reasons_are_strings(self):
        """All reasons should be strings."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        for candidate in explanation["candidates"]:
            for reason in candidate["reasons"]:
                assert isinstance(reason, str), f"Reason is not a string: {reason}"
        
        for reason in explanation["selection_reasons"]:
            assert isinstance(reason, str), f"Selection reason is not a string: {reason}"


class TestSelectedActionHasHighestScore:
    """C3: Test that selected action has highest score."""
    
    @pytest.mark.asyncio
    async def test_selected_matches_highest_score_test_mode(self):
        """In test mode, selected should be the highest scoring action."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        candidates = explanation["candidates"]
        selected = explanation["selected"]
        
        # Selected should be first candidate (highest score in test mode)
        assert candidates[0]["action"] == selected, \
            f"Selected {selected} is not highest score {candidates[0]['action']}"
    
    @pytest.mark.asyncio
    async def test_selected_is_valid_action(self):
        """Selected action should be a valid action."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        assert explanation["selected"] in ACTION_SPACE, \
            f"Invalid action: {explanation['selected']}"
    
    @pytest.mark.asyncio
    async def test_high_grudge_favors_withdraw_or_attack(self):
        """High grudge should favor withdraw or attack actions."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.1, "grudge": 0.8, "trust": 0.0, "repair_bank": 0.0
        }
        
        explanation = await core.generate_explanation("user", test_mode=True)
        
        # With high grudge, withdraw or attack should be in top 2
        top2_actions = [c["action"] for c in explanation["candidates"][:2]]
        assert "withdraw" in top2_actions or "attack" in top2_actions, \
            f"High grudge should favor withdraw/attack, got {top2_actions}"


class TestDecisionPersistence:
    """C2: Test decision persistence."""
    
    @pytest.mark.asyncio
    async def test_save_decision_returns_id(self):
        """Saving a decision should return an ID."""
        explanation = {"selected": "approach", "emotion": {}}
        decision_id = await save_decision("approach", explanation)
        
        assert decision_id is not None
        assert isinstance(decision_id, int)
        assert decision_id > 0
    
    @pytest.mark.asyncio
    async def test_get_last_decision_returns_most_recent(self):
        """Getting last decision should return most recent."""
        # Save two decisions
        await save_decision("approach", {"selected": "approach"})
        await save_decision("withdraw", {"selected": "withdraw"})
        
        last = await get_last_decision()
        
        assert last is not None
        assert last["action"] == "withdraw"
    
    @pytest.mark.asyncio
    async def test_decision_has_timestamp(self):
        """Decision should have a timestamp."""
        await save_decision("approach", {"selected": "approach"})
        
        last = await get_last_decision()
        
        assert "created_at" in last
        assert last["created_at"] is not None
    
    @pytest.mark.asyncio
    async def test_explanation_stored_as_json(self):
        """Explanation should be stored and retrievable as JSON."""
        explanation = {
            "selected": "repair_offer",
            "emotion": {"anger": 0.1},
            "selection_reasons": ["Test reason"]
        }
        await save_decision("repair_offer", explanation)
        
        last = await get_last_decision()
        
        assert last["explanation"]["selected"] == "repair_offer"
        assert last["explanation"]["selection_reasons"] == ["Test reason"]


class TestSelectActionWithExplanation:
    """Test select_action_with_explanation function."""
    
    @pytest.mark.asyncio
    async def test_returns_action_explanation_decision_id(self):
        """Should return action, explanation, and decision_id."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        result = await core.select_action_with_explanation("user", test_mode=True)
        
        assert "action" in result
        assert "explanation" in result
        assert "decision_id" in result
        assert result["action"] in ACTION_SPACE
        assert isinstance(result["decision_id"], int)
    
    @pytest.mark.asyncio
    async def test_stores_decision_in_database(self):
        """Should store decision in database."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        result = await core.select_action_with_explanation("user", test_mode=True)
        
        # Verify decision was stored
        last = await get_last_decision()
        assert last is not None
        assert last["id"] == result["decision_id"]
    
    @pytest.mark.asyncio
    async def test_updates_relationship_last_action(self):
        """Should update relationship's last_action field."""
        core.relationship_manager.relationships["user"] = {
            "bond": 0.5, "grudge": 0.2, "trust": 0.3, "repair_bank": 0.1
        }
        
        result = await core.select_action_with_explanation("user", test_mode=True)
        
        assert core.relationship_manager.last_actions.get("user") == result["action"]


class TestAPIIntegration:
    """Test API endpoints for decisions."""
    
    @pytest.mark.asyncio
    async def test_decision_endpoint_returns_none_when_empty(self):
        """Decision endpoint should return None when no decisions."""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        
        client = TestClient(app)
        response = client.get("/decision")
        
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] is None
    
    @pytest.mark.asyncio
    async def test_decision_endpoint_returns_decision(self):
        """Decision endpoint should return decision after one is made."""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        
        # Create a decision
        await save_decision("approach", {"selected": "approach"})
        
        client = TestClient(app)
        response = client.get("/decision")
        
        assert response.status_code == 200
        data = response.json()
        # API returns action directly at top level when decision exists
        assert data["status"] == "ok"
        assert data["action"] == "approach"
