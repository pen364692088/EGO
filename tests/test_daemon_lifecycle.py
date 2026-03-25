"""
Tests for daemon lifecycle and process management
"""
import pytest
import asyncio
import signal
import tempfile
import os
from emotiond.daemon import DaemonManager
from emotiond.config import DB_PATH


class TestDaemonLifecycle:
    """Test daemon lifecycle management"""
    
    def setup_method(self):
        """Setup before each test"""
        # Use temporary database
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.original_db_path = DB_PATH
        os.environ["OPENEMOTION_DB_PATH"] = self.tmp_file.name
        self.manager = DaemonManager()
    
    def teardown_method(self):
        """Cleanup after each test"""
        # Restore original DB path
        os.environ["OPENEMOTION_DB_PATH"] = self.original_db_path
        os.unlink(self.tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_daemon_start_stop(self):
        """Test daemon can start and stop properly"""
        # Initially not running
        assert not self.manager.is_running()
        
        # Start daemon
        await self.manager.start()
        assert self.manager.is_running()
        
        # Check loop status
        status = self.manager.get_loop_status()
        assert "homeostasis" in status
        assert "consolidation" in status
        assert status["homeostasis"] == "running"
        assert status["consolidation"] == "running"
        
        # Stop daemon
        await self.manager.stop()
        assert not self.manager.is_running()
    
    @pytest.mark.asyncio
    async def test_daemon_multiple_start_calls(self):
        """Test that multiple start calls don't cause issues"""
        await self.manager.start()
        assert self.manager.is_running()
        
        # Call start again - should be idempotent
        await self.manager.start()
        assert self.manager.is_running()
        
        await self.manager.stop()
        assert not self.manager.is_running()
    
    @pytest.mark.asyncio
    async def test_daemon_multiple_stop_calls(self):
        """Test that multiple stop calls don't cause issues"""
        await self.manager.start()
        assert self.manager.is_running()
        
        await self.manager.stop()
        assert not self.manager.is_running()
        
        # Call stop again - should be idempotent
        await self.manager.stop()
        assert not self.manager.is_running()
    
    @pytest.mark.asyncio
    async def test_daemon_loop_failure_detection(self):
        """Test that daemon detects loop failures"""
        await self.manager.start()
        assert self.manager.is_running()
        
        # Simulate a loop failure by cancelling one loop
        self.manager.loops["homeostasis"].cancel()
        
        # Wait a bit for the cancellation to take effect
        await asyncio.sleep(0.1)
        
        # Check that the failed loop is detected
        status = self.manager.get_loop_status()
        assert status["homeostasis"] == "cancelled"
        
        await self.manager.stop()
    
    def test_daemon_signal_handlers(self):
        """Test signal handler setup"""
        from emotiond.daemon import setup_signal_handlers
        
        # This should not raise any exceptions
        setup_signal_handlers()
        
        # Verify signal handlers are set
        assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
        assert signal.getsignal(signal.SIGINT) is not signal.SIG_DFL
    
    @pytest.mark.asyncio
    async def test_daemon_run_function(self):
        """Test the main daemon run function"""
        from emotiond.daemon import run_daemon, daemon_manager
        
        # Start daemon in background
        task = asyncio.create_task(run_daemon())
        
        # Wait a bit for daemon to start
        await asyncio.sleep(0.1)
        
        # Should be running
        assert daemon_manager.is_running()
        
        # Stop daemon
        await daemon_manager.stop()
        
        # Wait for task to complete
        await task
        
        # Should be stopped
        assert not daemon_manager.is_running()