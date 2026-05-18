"""
Test FastAPI service configuration and health endpoint
"""
import pytest
from fastapi.testclient import TestClient
from emotiond.api import app
from emotiond.config import HOST, PORT


class TestFastAPIService:
    """Test FastAPI service configuration and endpoints"""
    
    def test_fastapi_service_configuration(self):
        """Test that FastAPI service is configured correctly"""
        # Verify service binds to localhost only
        assert HOST == "127.0.0.1"
        assert PORT == 18080
        
        # Verify app title and version
        assert app.title == "OpenEmotion Daemon"
        assert app.version == "0.1.0"
    
    def test_health_endpoint_returns_ok(self):
        """Test GET /health endpoint returns service status"""
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "ts" in data
        assert data["ok"] is True
        assert isinstance(data["ts"], str)
        
        # Check that ts is a valid ISO timestamp
        import datetime
        parsed_time = datetime.datetime.fromisoformat(data["ts"])
        assert isinstance(parsed_time, datetime.datetime)
    
    def test_service_binds_local_only(self):
        """Test that service only binds to localhost"""
        # This is verified through the config.py settings
        # HOST should be 127.0.0.1, not 0.0.0.0
        assert HOST == "127.0.0.1"
    
    def test_environment_variable_configuration(self):
        """Test that environment variables are respected"""
        import os
        from importlib import reload
        
        # Test with custom environment variables
        os.environ["EMOTIOND_HOST"] = "127.0.0.1"
        os.environ["EMOTIOND_PORT"] = "18080"
        
        # Reload config to pick up environment variables
        from emotiond import config
        reload(config)
        
        assert config.HOST == "127.0.0.1"
        assert config.PORT == 18080
        
        # Clean up
        del os.environ["EMOTIOND_HOST"]
        del os.environ["EMOTIOND_PORT"]
        reload(config)
    
    def test_all_endpoints_exist(self):
        """Test that all required endpoints exist"""
        # Initialize database first
        import asyncio
        from emotiond.db import init_db
        
        async def setup_db():
            await init_db()
        
        asyncio.run(setup_db())
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test event endpoint
        response = client.post("/event", json={
            "type": "user_message",
            "actor": "user",
            "target": "assistant",
            "text": "Hello"
        })
        assert response.status_code == 200
        
        # Test plan endpoint
        response = client.post("/plan", json={
            "user_id": "user",
            "user_text": "How are you?"
        })
        assert response.status_code == 200