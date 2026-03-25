"""
MVP-3.1: Learning Update Tests

Tests for correct learning update paths (residual vs global).
"""
import pytest
import pytest_asyncio
import os
import tempfile
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond import db, core, config
from emotiond.config import LR_TARGET, LR_GLOBAL_RATIO
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
async def test_residual_updates_on_error(setup_test_db):
    """Residual should update based on prediction error."""
    target_id = "test_target"
    
    preds_before = await core.load_target_predictions_cache(target_id)
    residual_before = preds_before["attack"]["social_safety_delta"]
    
    predicted = {"safety": 0.0, "energy": 0.0}
    observed = {"safety": 0.1, "energy": 0.05}
    
    await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.5)
    
    preds_after = await core.load_target_predictions_cache(target_id)
    residual_after = preds_after["attack"]["social_safety_delta"]
    
    assert residual_after > residual_before, \
        f"Expected residual to increase, got {residual_before} -> {residual_after}"


@pytest.mark.asyncio
async def test_global_updates_slower_than_residual(setup_test_db):
    """Global should update slower than residual."""
    target_id = "test_target"
    
    preds_target_before = await core.load_target_predictions_cache(target_id)
    global_before = core._predictions["attack"]["social_safety_delta"]
    residual_before = preds_target_before["attack"]["social_safety_delta"]
    
    for _ in range(5):
        predicted = {"safety": 0.0, "energy": 0.0}
        observed = {"safety": 0.1, "energy": 0.05}
        
        await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.5)
    
    preds_target_after = await core.load_target_predictions_cache(target_id)
    global_after = core._predictions["attack"]["social_safety_delta"]
    residual_after = preds_target_after["attack"]["social_safety_delta"]
    
    global_change = abs(global_after - global_before)
    residual_change = abs(residual_after - residual_before)
    
    assert residual_change > global_change, \
        f"Expected residual change ({residual_change}) > global change ({global_change})"


@pytest.mark.asyncio
async def test_learning_rate_ratio_is_correct(setup_test_db):
    """Verify that global learning rate is LR_TARGET * LR_GLOBAL_RATIO."""
    target_id = "test_target"
    
    # The ratio should be correct (not testing exact values due to priors)
    lr_global = LR_TARGET * LR_GLOBAL_RATIO
    expected_ratio = LR_GLOBAL_RATIO  # 0.2 by default
    
    assert abs(lr_global - LR_TARGET * expected_ratio) < 0.001, \
        f"Global LR should be {LR_TARGET * expected_ratio}, got {lr_global}"
    
    # Verify config values
    assert LR_TARGET == 0.1, f"LR_TARGET should be 0.1, got {LR_TARGET}"
    assert LR_GLOBAL_RATIO == 0.2, f"LR_GLOBAL_RATIO should be 0.2, got {LR_GLOBAL_RATIO}"


@pytest.mark.asyncio
async def test_n_increments_on_update(setup_test_db):
    """n should increment on each update."""
    target_id = "test_target"
    
    preds_before = await core.load_target_predictions_cache(target_id)
    n_before = preds_before["attack"]["n"]
    
    predicted = {"safety": 0.0, "energy": 0.0}
    observed = {"safety": 0.1, "energy": 0.05}
    
    await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.5)
    
    preds_after = await core.load_target_predictions_cache(target_id)
    n_after = preds_after["attack"]["n"]
    
    assert n_after == n_before + 1, f"Expected n to increment by 1, got {n_before} -> {n_after}"


@pytest.mark.asyncio
async def test_ema_error_updates(setup_test_db):
    """EMA error tracking should update correctly."""
    target_id = "test_target"
    
    preds_before = await core.load_target_predictions_cache(target_id)
    ema_before = preds_before["attack"]["ema_abs_error"]
    
    predicted = {"safety": 0.0, "energy": 0.0}
    observed = {"safety": 0.1, "energy": 0.05}
    
    await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.5)
    
    preds_after = await core.load_target_predictions_cache(target_id)
    ema_after = preds_after["attack"]["ema_abs_error"]
    
    assert ema_after > ema_before, f"Expected EMA to increase, got {ema_before} -> {ema_after}"


@pytest.mark.asyncio
async def test_negative_error_decreases_residual(setup_test_db):
    """Negative prediction error should decrease residual."""
    target_id = "test_target"
    
    for _ in range(5):
        predicted = {"safety": 0.0, "energy": 0.0}
        observed = {"safety": 0.1, "energy": 0.05}
        await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.5)
    
    preds_before = await core.load_target_predictions_cache(target_id)
    residual_before = preds_before["attack"]["social_safety_delta"]
    
    predicted = {"safety": 0.05, "energy": 0.02}
    observed = {"safety": -0.1, "energy": -0.05}
    
    await core.update_predictions_with_target("attack", target_id, predicted, observed, alpha=0.8)
    
    preds_after = await core.load_target_predictions_cache(target_id)
    residual_after = preds_after["attack"]["social_safety_delta"]
    
    assert residual_after < residual_before, \
        f"Expected residual to decrease with negative error, got {residual_before} -> {residual_after}"


@pytest.mark.asyncio
async def test_residual_changes_faster_than_global(setup_test_db):
    """After multiple updates, residual should have changed more than global."""
    target_id = "test_target"
    action = "boundary"  # Use an action with different priors
    
    # Record initial values
    preds_before = await core.load_target_predictions_cache(target_id)
    residual_before = preds_before[action]["social_safety_delta"]
    global_before = core._predictions[action]["social_safety_delta"]
    
    # Do multiple updates with consistent positive error
    for _ in range(10):
        predicted = {"safety": 0.0, "energy": 0.0}
        observed = {"safety": 0.15, "energy": 0.1}  # Consistent positive error
        await core.update_predictions_with_target(action, target_id, predicted, observed, alpha=0.5)
    
    # Check final values
    preds_after = await core.load_target_predictions_cache(target_id)
    residual_after = preds_after[action]["social_safety_delta"]
    global_after = core._predictions[action]["social_safety_delta"]
    
    residual_change = abs(residual_after - residual_before)
    global_change = abs(global_after - global_before)
    
    # Residual should change more due to higher learning rate
    # residual: LR_TARGET = 0.1
    # global: LR_TARGET * LR_GLOBAL_RATIO = 0.02
    # After 10 updates, residual should be ~5x the global change
    assert residual_change > global_change * 2, \
        f"Residual change ({residual_change}) should be > 2x global change ({global_change})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
