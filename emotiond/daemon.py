"""
Daemon process management and lifecycle
"""
import asyncio
import signal
import logging
import sys
import os
from typing import Dict, Any, Optional
from emotiond.core import homeostasis_loop, consolidation_loop
from emotiond.db import init_db, close_db
from emotiond.config import setup_logging

# MVP12: Feature flag for developmental cycle
ENABLE_DEVELOPMENTAL_CYCLE = os.environ.get("ENABLE_DEVELOPMENTAL_CYCLE", "true").lower() == "true"

# MVP12: Import developmental cycle daemon (conditional)
if ENABLE_DEVELOPMENTAL_CYCLE:
    try:
        from emotiond.developmental_core import create_dev_daemon, DaemonCycleConfig
        _DEV_DAEMON_AVAILABLE = True
    except ImportError:
        _DEV_DAEMON_AVAILABLE = False
        ENABLE_DEVELOPMENTAL_CYCLE = False
else:
    _DEV_DAEMON_AVAILABLE = False


class DaemonManager:
    """Manages the emotiond daemon lifecycle"""
    
    def __init__(self):
        self.loops: Dict[str, asyncio.Task] = {}
        self.running = False
        self.logger = logging.getLogger("emotiond.daemon")
        
        # MVP12: Initialize developmental cycle daemon (conditional)
        self._dev_daemon = None
        self._dev_daemon_enabled = ENABLE_DEVELOPMENTAL_CYCLE and _DEV_DAEMON_AVAILABLE
        
        if self._dev_daemon_enabled:
            try:
                self._dev_daemon = create_dev_daemon(
                    idle_threshold=60.0,
                    min_cycle_interval=30.0,
                    max_candidates_per_cycle=5,
                )
                self.logger.info("[MVP12] Developmental cycle daemon initialized")
            except Exception as e:
                self.logger.warning(f"[MVP12] Failed to initialize developmental daemon: {e}")
                self._dev_daemon_enabled = False
    
    async def start(self) -> None:
        """Start the daemon and all background loops"""
        if self.running:
            self.logger.warning("Daemon is already running")
            return
        
        self.logger.info("Starting emotiond daemon")
        
        # Initialize database
        await init_db()
        
        # Start background loops
        self.loops["homeostasis"] = asyncio.create_task(homeostasis_loop())
        self.loops["consolidation"] = asyncio.create_task(consolidation_loop())
        
        # MVP12: Start developmental cycle loop (conditional)
        if self._dev_daemon_enabled:
            self.loops["developmental_cycle"] = asyncio.create_task(
                self._developmental_cycle_loop()
            )
            self.logger.info("[MVP12] Developmental cycle loop started")
        
        self.running = True
        self.logger.info("Daemon started successfully")
    
    async def _developmental_cycle_loop(self):
        """MVP12: Background loop for developmental cycles"""
        if not self._dev_daemon:
            return
            
        while self.running:
            try:
                # Check if conditions are met for a developmental cycle
                if self._dev_daemon.should_run_cycle():
                    result = self._dev_daemon.run_developmental_cycle()
                    if result.success:
                        self.logger.info(
                            f"[MVP12] Developmental cycle {result.cycle_id} completed: "
                            f"{result.candidates_generated} candidates, "
                            f"{result.candidates_approved} approved"
                        )
                    elif result.error:
                        self.logger.warning(
                            f"[MVP12] Developmental cycle failed: {result.error}"
                        )
                
                # Sleep before next check
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                self.logger.info("[MVP12] Developmental cycle loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"[MVP12] Developmental cycle loop error: {e}")
                await asyncio.sleep(30)  # Back off on error
    
    def update_activity(self):
        """MVP12: Update activity timestamp to reset idle timer"""
        if self._dev_daemon:
            self._dev_daemon.update_activity()
    
    def get_developmental_metrics(self) -> Dict[str, Any]:
        """MVP12: Get developmental cycle metrics"""
        if self._dev_daemon:
            return self._dev_daemon.get_metrics()
        return {"enabled": False, "reason": "developmental_cycle_disabled"}
    
    def get_developmental_status(self) -> Dict[str, Any]:
        """MVP12: Get developmental cycle status for health check"""
        return {
            "feature_flag": ENABLE_DEVELOPMENTAL_CYCLE,
            "module_available": _DEV_DAEMON_AVAILABLE,
            "enabled": self._dev_daemon_enabled,
            "running": "developmental_cycle" in self.loops and not self.loops.get("developmental_cycle", asyncio.Future()).done(),
            "metrics": self.get_developmental_metrics() if self._dev_daemon_enabled else None
        }
    
    async def stop(self) -> None:
        """Gracefully stop the daemon and all background loops"""
        if not self.running:
            self.logger.warning("Daemon is not running")
            return
        
        self.logger.info("Stopping emotiond daemon")
        self.running = False
        
        # Cancel all background loops
        for name, task in self.loops.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    self.logger.debug(f"Loop {name} cancelled")
        
        # Close database connections
        await close_db()
        
        self.logger.info("Daemon stopped gracefully")
    
    def is_running(self) -> bool:
        """Check if daemon is running"""
        return self.running
    
    def get_loop_status(self) -> Dict[str, str]:
        """Get status of all background loops"""
        status = {}
        for name, task in self.loops.items():
            if task.done():
                try:
                    if task.exception():
                        status[name] = f"failed: {task.exception()}"
                    else:
                        status[name] = "completed"
                except asyncio.CancelledError:
                    status[name] = "cancelled"
            else:
                status[name] = "running"
        return status


# Global daemon manager instance
daemon_manager = DaemonManager()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger = logging.getLogger("emotiond.daemon")
        logger.info(f"Received signal {signum}, initiating shutdown")
        
        # Schedule daemon shutdown
        asyncio.create_task(daemon_manager.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def run_daemon():
    """Main daemon entry point"""
    setup_logging()
    setup_signal_handlers()
    
    logger = logging.getLogger("emotiond.daemon")
    
    try:
        await daemon_manager.start()
        
        # Keep the daemon running until stopped
        while daemon_manager.is_running():
            await asyncio.sleep(1)
            
            # Check if any loops have failed
            loop_status = daemon_manager.get_loop_status()
            for name, status in loop_status.items():
                if "failed" in status:
                    logger.error(f"Loop {name} failed: {status}")
                    await daemon_manager.stop()
                    break
        
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        await daemon_manager.stop()
        sys.exit(1)
    
    logger.info("Daemon process completed")