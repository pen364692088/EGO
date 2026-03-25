import pytest
import pytest_asyncio
from emotiond.models import Event
from emotiond.core import process_event, emotion_state
from emotiond.db import init_db
import os
import tempfile
import shutil

# Use test database
os.environ["EMOTIOND_DB_PATH"] = "/tmp/test_mvp2_1.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Setup isolated database for tests"""
    from emotiond import config, db, core
    import importlib
    
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_mvp21_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    
    # Reset global state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.relationship_manager.relationships = {}
    
    await db.init_db()
    
    yield
    
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    # Reset state after test
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.relationship_manager.relationships = {}
    
    shutil.rmtree(test_data_dir, ignore_errors=True)


class TestAuthGate:
    """MVP-2.1: World Event Auth Gate"""
    
    @pytest.mark.asyncio
    async def test_user_cannot_send_betrayal(self):
        """User source should be denied for betrayal"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "betrayal", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "denied"
        assert result["error"] == "forbidden_event_type"
        assert "betrayal" in result["reason"]
    
    @pytest.mark.asyncio
    async def test_user_cannot_send_repair_success(self):
        """User source should be denied for repair_success"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "repair_success", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "denied"
    
    @pytest.mark.asyncio
    async def test_system_can_send_betrayal(self):
        """System source should be allowed for betrayal"""
        event = Event(
            type="world_event",
            actor="system",
            target="assistant",
            meta={"subtype": "betrayal", "source": "system"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_openclaw_can_send_betrayal(self):
        """OpenClaw source should be allowed for betrayal"""
        event = Event(
            type="world_event",
            actor="openclaw",
            target="assistant",
            meta={"subtype": "betrayal", "source": "openclaw"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_user_can_send_care(self):
        """User source should be allowed for care"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_user_can_send_rejection(self):
        """User source should be allowed for rejection"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "rejection", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_user_can_send_ignored(self):
        """User source should be allowed for ignored"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "ignored", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_user_can_send_apology(self):
        """User source should be allowed for apology"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "apology", "source": "user"}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_user_can_send_time_passed(self):
        """User source should be allowed for time_passed"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "time_passed", "source": "user", "seconds": 60}
        )
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_default_source_is_user(self):
        """If no source specified, default to user (denied for betrayal)"""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "betrayal"}  # No source field
        )
        result = await process_event(event)
        
        assert result["status"] == "denied"
