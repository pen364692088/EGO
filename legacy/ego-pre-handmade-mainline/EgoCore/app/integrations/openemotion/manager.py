"""
OpenEmotion Integration - Manager

Manages OpenEmotion process lifecycle:
- Auto-start on EgoCore startup
- Health monitoring
- Restart on failure
- Graceful shutdown
"""

import logging
import subprocess
import time
import os
import signal
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import threading

from app.integrations.openemotion.client import (
    OpenEmotionClient,
    OpenEmotionClientConfig,
    get_openemotion_client,
)


logger = logging.getLogger(__name__)


@dataclass
class OpenEmotionManagerConfig:
    """Configuration for OpenEmotion manager."""
    enabled: bool = True
    auto_start: bool = True
    host: str = "127.0.0.1"
    port: int = 18080
    healthcheck_timeout_ms: int = 1000
    restart_on_failure: bool = True
    max_restart_attempts: int = 3
    restart_delay_seconds: int = 5
    # Path to OpenEmotion executable/script
    openemotion_path: Optional[str] = None
    openemotion_args: Optional[list] = None


class OpenEmotionManager:
    """
    Manages OpenEmotion process lifecycle.
    
    Responsibilities:
    - Start OpenEmotion process
    - Health monitoring
    - Restart on failure
    - Graceful shutdown
    
    Safety:
    - OpenEmotion failure does NOT crash EgoCore
    - All operations have timeouts
    - Process is properly cleaned up on shutdown
    """
    
    def __init__(self, config: Optional[OpenEmotionManagerConfig] = None):
        self.config = config or OpenEmotionManagerConfig()
        self._process: Optional[subprocess.Popen] = None
        self._client = OpenEmotionClient(OpenEmotionClientConfig(
            host=self.config.host,
            port=self.config.port,
            healthcheck_timeout_ms=self.config.healthcheck_timeout_ms,
        ))
        self._restart_attempts = 0
        self._last_health_check: Optional[datetime] = None
        self._healthy = False
        self._lock = threading.Lock()
    
    @property
    def is_running(self) -> bool:
        """Check if OpenEmotion process is running."""
        if self._process is None:
            return False
        return self._process.poll() is None
    
    @property
    def is_healthy(self) -> bool:
        """Check if OpenEmotion is healthy."""
        return self._healthy
    
    def start(self) -> tuple[bool, str]:
        """
        Start OpenEmotion process.
        
        Returns:
            Tuple of (success, message)
        """
        if not self.config.enabled:
            return False, "OpenEmotion is not enabled"
        
        with self._lock:
            if self.is_running:
                logger.info("OpenEmotion already running")
                return True, "Already running"
            
            # Find OpenEmotion executable
            openemotion_path = self._find_openemotion()
            if not openemotion_path:
                logger.warning("OpenEmotion not found, running in degraded mode")
                self._healthy = False
                return False, "OpenEmotion not found"
            
            # Start process
            try:
                args = self.config.openemotion_args or []
                cmd = [openemotion_path] + args
                
                logger.info(f"Starting OpenEmotion: {openemotion_path}")
                
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,  # Don't inherit signals
                )
                
                # Wait for process to start
                time.sleep(1)
                
                # Check if still running
                if not self.is_running:
                    return False, "OpenEmotion failed to start"
                
                logger.info("OpenEmotion process started")
                return True, "Started"
                
            except Exception as e:
                logger.error(f"Failed to start OpenEmotion: {e}")
                self._healthy = False
                return False, str(e)
    
    def stop(self) -> None:
        """Stop OpenEmotion process gracefully."""
        with self._lock:
            if self._process is None:
                return
            
            logger.info("Stopping OpenEmotion")
            
            try:
                # Send SIGTERM
                self._process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill
                    logger.warning("OpenEmotion did not stop gracefully, killing")
                    self._process.kill()
                    self._process.wait(timeout=5)
                
                logger.info("OpenEmotion stopped")
                
            except Exception as e:
                logger.error(f"Error stopping OpenEmotion: {e}")
            
            finally:
                self._process = None
                self._healthy = False
    
    def health_check(self) -> tuple[bool, str]:
        """
        Check OpenEmotion health.
        
        Returns:
            Tuple of (healthy, message)
        """
        if not self.config.enabled:
            return False, "Not enabled"
        
        self._last_health_check = datetime.now()
        
        success, status, fallback = self._client.health()
        
        if success and status:
            self._healthy = status.healthy
            self._restart_attempts = 0  # Reset on successful health check
            
            if status.healthy:
                return True, f"Healthy (version: {status.version or 'unknown'})"
            else:
                return False, "Unhealthy"
        
        # Health check failed
        self._healthy = False
        
        if fallback:
            # Try to restart if configured
            if self.config.restart_on_failure and self._restart_attempts < self.config.max_restart_attempts:
                logger.info(f"Attempting restart ({self._restart_attempts + 1}/{self.config.max_restart_attempts})")
                self._restart_attempts += 1
                
                self.stop()
                time.sleep(self.config.restart_delay_seconds)
                self.start()
            
            return False, fallback.message
        
        return False, "Unknown error"
    
    def _find_openemotion(self) -> Optional[str]:
        """
        Find OpenEmotion executable.
        
        Looks in:
        1. Config path
        2. Same directory as EgoCore
        3. PATH
        """
        # Check config path
        if self.config.openemotion_path:
            if os.path.exists(self.config.openemotion_path):
                return self.config.openemotion_path
        
        # Check relative to EgoCore
        base_dir = Path(__file__).parent.parent.parent.parent
        candidates = [
            base_dir / "OpenEmotion" / "emotiond",
            base_dir / "openemotion" / "emotiond",
            base_dir / "emotiond",
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        
        # Check PATH
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(path_dir) / "emotiond"
            if candidate.exists():
                return str(candidate)
        
        return None
    
    def ensure_running(self) -> tuple[bool, str]:
        """
        Ensure OpenEmotion is running and healthy.
        
        This is the main entry point for startup.
        
        Returns:
            Tuple of (healthy, message)
        """
        if not self.config.enabled:
            return False, "Not enabled"
        
        if not self.is_running:
            if self.config.auto_start:
                success, message = self.start()
                if not success:
                    return False, f"Failed to start: {message}"
            else:
                return False, "Not running and auto_start disabled"
        
        # Health check
        return self.health_check()


# ============================================================================
# Global Instance
# ============================================================================

_manager: Optional[OpenEmotionManager] = None


def get_openemotion_manager(config: Optional[OpenEmotionManagerConfig] = None) -> OpenEmotionManager:
    """Get or create global OpenEmotion manager."""
    global _manager
    if _manager is None:
        _manager = OpenEmotionManager(config)
    return _manager
