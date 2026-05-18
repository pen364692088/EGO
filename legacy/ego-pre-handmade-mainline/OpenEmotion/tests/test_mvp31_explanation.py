"""
MVP-3.1: Explanation Consistency Tests

Tests for explanation structure and numerical consistency.
"""
import pytest
import pytest_asyncio
import os
import tempfile
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond import db, core, config
import importlib


@pytest_asyncio.fixture
async def setup_test_db():
    """Setup a fresh test database for each test."""
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_mvp31_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_TEST_MODE"] = "1"
    
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}
    core._target_predictions = {}
    core._predictions = {}
    
    await db.init_db()
    await core.load_initial_state()
    
    yield test_data_dir
    
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_explanation_contains_target_id(setup_test_db):
    """Explanation should include target_id."""
    target = "test_user"
    target_id = "client_A"
    
    explanation = await core.generate_explanation_v31(target, target_id, test_mode=True)
    
    assert "target_id" in explanation
    assert explanation["target_id"] == target_id


@pytest.mark.asyncio
async def test_explanation_contains_alpha(setup_test_db):
    """Each candidate should include alpha value."""
    target = "test_user"
    target_id = "client_A"
    
    for _ in range(10):
        target_preds = await core.load_target_predictions_cache(target_id)
        global_pred = core._predictions.get("attack", {"social_safety_delta": -0.05, "energy_delta": -0.05})
        target_pred = target_preds.get("attack", {"social_safety_delta": 0.0, "energy_delta": 0.0, "n": 0})
        n = target_pred.get("n", 0)
        alpha = core.calculate_shrinkage_alpha(n)
        
        predicted = {"safety": 0.0, "energy": 0.0}
        observed = {"safety": 0.1, "energy": 0.05}
        
        await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha)
    
    explanation = await core.generate_explanation_v31(target, target_id, test_mode=True)
    
    for candidate in explanation["candidates"]:
        assert "alpha" in candidate
        assert 0.0 <= candidate["alpha"] < 1.0


@pytest.mark.asyncio
async def test_explanation_prediction_consistency(setup_test_db):
    """Test that predicted_total == predicted_global + alpha * predicted_residual."""
    target = "test_user"
    target_id = "client_A"
    
    for _ in range(15):
        target_preds = await core.load_target_predictions_cache(target_id)
        global_pred = core._predictions.get("attack", {"social_safety_delta": -0.05, "energy_delta": -0.05})
        target_pred = target_preds.get("attack", {"social_safety_delta": 0.0, "energy_delta": 0.0, "n": 0})
        n = target_pred.get("n", 0)
        alpha = core.calculate_shrinkage_alpha(n)
        
        predicted = {"safety": 0.0, "energy": 0.0}
        observed = {"safety": -0.1, "energy": -0.05}
        
        await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha)
    
    explanation = await core.generate_explanation_v31(target, target_id, test_mode=True)
    
    for candidate in explanation["candidates"]:
        alpha = candidate["alpha"]
        global_safety = candidate["predicted_global"]["safety"]
        global_energy = candidate["predicted_global"]["energy"]
        residual_safety = candidate["predicted_residual"]["safety"]
        residual_energy = candidate["predicted_residual"]["energy"]
        total_safety = candidate["predicted_total"]["safety"]
        total_energy = candidate["predicted_total"]["energy"]
        
        expected_safety = global_safety + alpha * residual_safety
        expected_energy = global_energy + alpha * residual_energy
        
        assert abs(total_safety - expected_safety) < 0.001, \
            f"Safety mismatch for {candidate['action']}: {total_safety} != {global_safety} + {alpha} * {residual_safety}"
        
        assert abs(total_energy - expected_energy) < 0.001, \
            f"Energy mismatch for {candidate['action']}: {total_energy} != {global_energy} + {alpha} * {residual_energy}"


@pytest.mark.asyncio
async def test_explanation_candidates_sorted_by_score(setup_test_db):
    """Candidates should be sorted by score (highest first)."""
    target = "test_user"
    
    explanation = await core.generate_explanation_v31(target, target, test_mode=True)
    
    scores = [c["score"] for c in explanation["candidates"]]
    assert scores == sorted(scores, reverse=True), \
        f"Candidates not sorted by score: {scores}"


@pytest.mark.asyncio
async def test_explanation_contains_all_required_fields(setup_test_db):
    """Explanation should contain all required top-level fields."""
    target = "test_user"
    
    explanation = await core.generate_explanation_v31(target, target, test_mode=True)
    
    required_fields = ["emotion", "interoception", "relationships", "target_id", "candidates", "selected", "selection_reasons"]
    
    for field in required_fields:
        assert field in explanation, f"Missing required field: {field}"


@pytest.mark.asyncio
async def test_explanation_candidate_fields(setup_test_db):
    """Each candidate should have all required MVP-3.1 fields."""
    target = "test_user"
    
    explanation = await core.generate_explanation_v31(target, target, test_mode=True)
    
    required_candidate_fields = [
        "action", "score", "alpha",
        "predicted_global", "predicted_residual", "predicted_total",
        "reasons"
    ]
    
    for candidate in explanation["candidates"]:
        for field in required_candidate_fields:
            assert field in candidate, f"Candidate missing field: {field}"
        
        for pred_type in ["predicted_global", "predicted_residual", "predicted_total"]:
            assert "safety" in candidate[pred_type], f"{pred_type} missing safety"
            assert "energy" in candidate[pred_type], f"{pred_type} missing energy"


@pytest.mark.asyncio
async def test_select_action_with_explanation_v31(setup_test_db):
    """Test the main entry point returns correct structure."""
    target = "test_user"
    target_id = "client_B"
    
    result = await core.select_action_with_explanation_v31(target, target_id, test_mode=True)
    
    assert "action" in result
    assert "explanation" in result
    assert "decision_id" in result
    assert "target_id" in result
    
    assert result["target_id"] == target_id
    assert result["action"] in core.ACTION_SPACE
    assert result["decision_id"] > 0


@pytest.mark.asyncio
async def test_selected_action_matches_top_candidate(setup_test_db):
    """Selected action should match the top candidate (in test mode)."""
    target = "test_user"
    
    explanation = await core.generate_explanation_v31(target, target, test_mode=True)
    
    assert explanation["selected"] == explanation["candidates"][0]["action"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
