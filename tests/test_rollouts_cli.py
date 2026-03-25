"""Tests for US-705: Offline Rollouts CLI parameter."""

import os
import pytest
from unittest.mock import patch


class TestRolloutsCLI:
    """US-705: --enable-rollouts CLI parameter tests."""
    
    def test_rollouts_disabled_by_default(self):
        """Rollouts should be disabled by default."""
        from emotiond.config import is_rollouts_enabled
        
        # Ensure env var is not set
        original = os.environ.pop("EMOTIOND_ENABLE_ROLLOUTS", None)
        try:
            # Reload the function to pick up current env
            import importlib
            import emotiond.config as config
            importlib.reload(config)
            
            assert config.is_rollouts_enabled() is False
        finally:
            if original:
                os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = original
    
    def test_rollouts_enabled_with_env(self):
        """Rollouts should be enabled with EMOTIOND_ENABLE_ROLLOUTS=1."""
        original = os.environ.get("EMOTIOND_ENABLE_ROLLOUTS")
        try:
            os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = "1"
            
            import importlib
            import emotiond.config as config
            importlib.reload(config)
            
            assert config.is_rollouts_enabled() is True
        finally:
            if original:
                os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = original
            else:
                os.environ.pop("EMOTIOND_ENABLE_ROLLOUTS", None)
    
    def test_rollouts_disabled_with_env_false(self):
        """Rollouts should be disabled with EMOTIOND_ENABLE_ROLLOUTS=false."""
        original = os.environ.get("EMOTIOND_ENABLE_ROLLOUTS")
        try:
            os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = "false"
            
            import importlib
            import emotiond.config as config
            importlib.reload(config)
            
            assert config.is_rollouts_enabled() is False
        finally:
            if original:
                os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = original
            else:
                os.environ.pop("EMOTIOND_ENABLE_ROLLOUTS", None)
    
    def test_cli_enable_rollouts_flag(self):
        """CLI --enable-rollouts flag should set env var."""
        from emotiond.main import parse_args
        
        # Test default
        with patch('sys.argv', ['main.py']):
            args = parse_args()
            assert args.enable_rollouts is False
        
        # Test with flag
        with patch('sys.argv', ['main.py', '--enable-rollouts']):
            args = parse_args()
            assert args.enable_rollouts is True
    
    def test_core_rollout_engine_disabled_by_default(self):
        """Core RolloutEngine should be disabled by default."""
        from core.offline_rollouts import RolloutEngine
        
        engine = RolloutEngine()
        assert engine.enabled is False
    
    def test_dmn_tick_rollouts_disabled_by_default(self):
        """DMNTick should have rollouts disabled by default."""
        from core.dmn_tick import DMNTick, TickAction
        
        tick = DMNTick()
        result = tick.tick()  # Default enable_rollouts=False
        
        # Rollouts should not be performed
        assert TickAction.RUN_ROLLOUTS.value not in result.actions_performed
    
    def test_equivalence_when_disabled(self):
        """Behavior should be equivalent to baseline when rollouts disabled."""
        from core.offline_rollouts import RolloutEngine
        from core.drive_homeostasis import DriveState
        
        engine = RolloutEngine(enabled=False)
        drive = DriveState()
        
        # run_rollouts should return None when disabled
        result = engine.run_rollouts("test context", drive)
        assert result is None
