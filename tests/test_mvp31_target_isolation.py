"""
MVP-3.1: Target Isolation Tests

Tests that learning from target A does not affect predictions for target B.
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
    
    # Reset global state
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
    
    # Cleanup
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_target_predictions_isolated(setup_test_db):
    """Test that predictions for target A do not affect target B."""
    target_a = "user_A"
    target_b = "user_B"
    
    # Train target A with negative outcomes for 'attack'
    for _ in range(30):
        target_preds = await core.load_target_predictions_cache(target_a)
        global_pred = core._predictions.get("attack", {"social_safety_delta": -0.05, "energy_delta": -0.05})
        target_pred = target_preds.get("attack", {"social_safety_delta": 0.0, "energy_delta": 0.0, "n": 0})
        n = target_pred.get("n", 0)
        alpha = core.calculate_shrinkage_alpha(n)
        
        predicted = {"safety": global_pred["social_safety_delta"] + alpha * target_pred["social_safety_delta"],
                     "energy": global_pred["energy_delta"] + alpha * target_pred["energy_delta"]}
        observed = {"safety": -0.3, "energy": -0.2}
        
        await core.update_predictions_with_target("attack", target_a, predicted, observed, alpha)
    
    preds_a = await core.load_target_predictions_cache(target_a)
    preds_b = await core.load_target_predictions_cache(target_b)
    
    residual_a_attack = preds_a["attack"]["social_safety_delta"]
    assert residual_a_attack < -0.05, f"Expected residual for A/attack to be negative, got {residual_a_attack}"
    
    residual_b_attack = preds_b["attack"]["social_safety_delta"]
    assert abs(residual_b_attack) < 0.01, f"Expected residual for B/attack to be ~0, got {residual_b_attack}"
    
    n_a = preds_a["attack"]["n"]
    n_b = preds_b["attack"]["n"]
    assert n_a > 20, f"Expected n for A to be > 20, got {n_a}"
    assert n_b == 0, f"Expected n for B to be 0, got {n_b}"


@pytest.mark.asyncio
async def test_action_selection_differs_between_targets(setup_test_db):
    """Test that action selection differs between targets after training."""
    target_a = "user_A"
    target_b = "user_B"
    
    for _ in range(30):
        target_preds = await core.load_target_predictions_cache(target_a)
        global_pred = core._predictions.get("attack", {"social_safety_delta": -0.05, "energy_delta": -0.05})
        target_pred = target_preds.get("attack", {"social_safety_delta": 0.0, "energy_delta": 0.0, "n": 0})
        n = target_pred.get("n", 0)
        alpha = core.calculate_shrinkage_alpha(n)
        
        predicted = {"safety": global_pred["social_safety_delta"] + alpha * target_pred["social_safety_delta"],
                     "energy": global_pred["energy_delta"] + alpha * target_pred["energy_delta"]}
        observed = {"safety": -0.3, "energy": -0.2}
        
        await core.update_predictions_with_target("attack", target_a, predicted, observed, alpha)
    
    core.relationship_manager._ensure_relationship_fields(target_a)
    core.relationship_manager._ensure_relationship_fields(target_b)
    
    core.relationship_manager.relationships[target_a]["grudge"] = 0.8
    core.relationship_manager.relationships[target_b]["grudge"] = 0.8
    
    action_a, combined_a = await core.select_action_with_target(
        core.emotion_state, target_a, target_a, test_mode=True
    )
    action_b, combined_b = await core.select_action_with_target(
        core.emotion_state, target_b, target_b, test_mode=True
    )
    
    attack_score_a = combined_a["attack"]["safety"]
    attack_score_b = combined_b["attack"]["safety"]
    
    assert attack_score_a < attack_score_b, \
        f"Expected attack safety score for A ({attack_score_a}) < B ({attack_score_b})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
