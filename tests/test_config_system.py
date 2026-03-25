"""
Tests for environment configuration system
"""
import os
import pytest
from emotiond.config import DB_PATH, PORT, HOST, K_AROUSAL, DISABLE_CORE


class TestEnvironmentConfiguration:
    """Test environment variable configuration"""
    
    def test_default_db_path(self):
        """Test default DB_PATH when environment variable is not set"""
        # Ensure environment variable is not set
        if "EMOTIOND_DB_PATH" in os.environ:
            del os.environ["EMOTIOND_DB_PATH"]
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DB_PATH == "./data/emotiond.db"
    
    def test_custom_db_path(self):
        """Test custom DB_PATH from environment variable"""
        os.environ["EMOTIOND_DB_PATH"] = "/custom/path/emotiond.db"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DB_PATH == "/custom/path/emotiond.db"
        
        # Clean up
        del os.environ["EMOTIOND_DB_PATH"]
    
    def test_default_port(self):
        """Test default PORT when environment variable is not set"""
        # Ensure environment variable is not set
        if "EMOTIOND_PORT" in os.environ:
            del os.environ["EMOTIOND_PORT"]
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.PORT == 18080
    
    def test_custom_port(self):
        """Test custom PORT from environment variable"""
        os.environ["EMOTIOND_PORT"] = "8080"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.PORT == 8080
        
        # Clean up
        del os.environ["EMOTIOND_PORT"]
    
    def test_default_host(self):
        """Test default HOST when environment variable is not set"""
        # Ensure environment variable is not set
        if "EMOTIOND_HOST" in os.environ:
            del os.environ["EMOTIOND_HOST"]
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.HOST == "127.0.0.1"
    
    def test_custom_host(self):
        """Test custom HOST from environment variable"""
        os.environ["EMOTIOND_HOST"] = "0.0.0.0"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.HOST == "0.0.0.0"
        
        # Clean up
        del os.environ["EMOTIOND_HOST"]
    
    def test_default_k_arousal(self):
        """Test default K_AROUSAL when environment variable is not set"""
        # Ensure environment variable is not set
        if "EMOTIOND_K_AROUSAL" in os.environ:
            del os.environ["EMOTIOND_K_AROUSAL"]
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.K_AROUSAL == 2.0
    
    def test_custom_k_arousal(self):
        """Test custom K_AROUSAL from environment variable"""
        os.environ["EMOTIOND_K_AROUSAL"] = "3.5"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.K_AROUSAL == 3.5
        
        # Clean up
        del os.environ["EMOTIOND_K_AROUSAL"]
    
    def test_disable_core_false_by_default(self):
        """Test DISABLE_CORE is False when environment variable is not set"""
        # Ensure environment variable is not set
        if "EMOTIOND_DISABLE_CORE" in os.environ:
            del os.environ["EMOTIOND_DISABLE_CORE"]
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is False
    
    def test_disable_core_true_with_1(self):
        """Test DISABLE_CORE is True when environment variable is '1'"""
        os.environ["EMOTIOND_DISABLE_CORE"] = "1"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is True
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
    
    def test_disable_core_true_with_true(self):
        """Test DISABLE_CORE is True when environment variable is 'true'"""
        os.environ["EMOTIOND_DISABLE_CORE"] = "true"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is True
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
    
    def test_disable_core_true_with_yes(self):
        """Test DISABLE_CORE is True when environment variable is 'yes'"""
        os.environ["EMOTIOND_DISABLE_CORE"] = "yes"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is True
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
    
    def test_disable_core_true_with_on(self):
        """Test DISABLE_CORE is True when environment variable is 'on'"""
        os.environ["EMOTIOND_DISABLE_CORE"] = "on"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is True
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
    
    def test_disable_core_false_with_other_values(self):
        """Test DISABLE_CORE is False when environment variable has other values"""
        os.environ["EMOTIOND_DISABLE_CORE"] = "false"
        
        # Reload config to get fresh values
        from importlib import reload
        from emotiond import config
        reload(config)
        
        assert config.DISABLE_CORE is False
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]


class TestCoreDisableFunctionality:
    """Test core disable functionality integration"""
    
    @pytest.mark.asyncio
    async def test_core_disabled_no_emotion_updates(self):
        """Test that emotion updates don't occur when core is disabled"""
        # Set environment variable to disable core
        os.environ["EMOTIOND_DISABLE_CORE"] = "1"
        
        # Reload config and core to get fresh values
        from importlib import reload
        from emotiond import config, core
        reload(config)
        reload(core)
        
        # Create a test event
        from emotiond.models import Event
        event = Event(type="user_message", actor="user", target="user", text="This is a positive message")
        
        # Get initial state
        initial_valence = core.emotion_state.valence
        initial_arousal = core.emotion_state.arousal
        
        # Process event
        actual_valence_change = core.emotion_state.update_from_event(event)
        
        # Verify no changes occurred
        assert actual_valence_change == 0.0
        assert core.emotion_state.valence == initial_valence
        assert core.emotion_state.arousal == initial_arousal
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
        reload(config)
        reload(core)
    
    @pytest.mark.asyncio
    async def test_core_disabled_no_homeostasis_drift(self):
        """Test that homeostasis drift doesn't occur when core is disabled"""
        # Set environment variable to disable core
        os.environ["EMOTIOND_DISABLE_CORE"] = "1"
        
        # Reload config and core to get fresh values
        from importlib import reload
        from emotiond import config, core
        reload(config)
        reload(core)
        
        # Get initial state
        initial_valence = core.emotion_state.valence
        initial_arousal = core.emotion_state.arousal
        initial_subjective_time = core.emotion_state.subjective_time
        
        # Apply homeostasis drift
        core.emotion_state.apply_homeostasis_drift(1.0)
        
        # Verify no changes occurred
        assert core.emotion_state.valence == initial_valence
        assert core.emotion_state.arousal == initial_arousal
        assert core.emotion_state.subjective_time == initial_subjective_time
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
        reload(config)
        reload(core)
    
    @pytest.mark.asyncio
    async def test_core_disabled_no_relationship_updates(self):
        """Test that relationship updates don't occur when core is disabled"""
        # Set environment variable to disable core
        os.environ["EMOTIOND_DISABLE_CORE"] = "1"
        
        # Reload config and core to get fresh values
        from importlib import reload
        from emotiond import config, core
        reload(config)
        reload(core)
        
        # Create a test event
        from emotiond.models import Event
        event = Event(type="user_message", actor="user", target="user", text="This is a positive message")
        
        # Get initial relationship state
        initial_relationships = dict(core.relationship_manager.relationships)
        
        # Update relationship from event
        core.relationship_manager.update_from_event(event)
        
        # Verify no changes occurred
        assert core.relationship_manager.relationships == initial_relationships
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
        reload(config)
        reload(core)
    
    @pytest.mark.asyncio
    async def test_core_disabled_no_consolidation_drift(self):
        """Test that consolidation drift doesn't occur when core is disabled"""
        # Set environment variable to disable core
        os.environ["EMOTIOND_DISABLE_CORE"] = "1"
        
        # Reload config and core to get fresh values
        from importlib import reload
        from emotiond import config, core
        reload(config)
        reload(core)
        
        # Add a test relationship
        core.relationship_manager.relationships["test_user"] = {"bond": 0.5, "grudge": 0.3}
        
        # Get initial relationship state
        initial_bond = core.relationship_manager.relationships["test_user"]["bond"]
        initial_grudge = core.relationship_manager.relationships["test_user"]["grudge"]
        
        # Apply consolidation drift
        core.relationship_manager.apply_consolidation_drift()
        
        # Verify no changes occurred
        assert core.relationship_manager.relationships["test_user"]["bond"] == initial_bond
        assert core.relationship_manager.relationships["test_user"]["grudge"] == initial_grudge
        
        # Clean up
        del os.environ["EMOTIOND_DISABLE_CORE"]
        reload(config)
        reload(core)


class TestMainEntryPoint:
    """Test main entry point configuration"""
    
    def test_main_imports_config(self):
        """Test that main.py imports and uses config values"""
        import emotiond.main
        
        # Verify main module can be imported and uses config
        assert hasattr(emotiond.main, 'HOST')
        assert hasattr(emotiond.main, 'PORT')
        
        # These should match the config values
        from emotiond.config import HOST, PORT
        assert emotiond.main.HOST == HOST
        assert emotiond.main.PORT == PORT