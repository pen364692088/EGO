"""
OpenEmotion Agent Runtime - Heartbeat Driver

P2-B.2: Minimal heartbeat driver for background task progression.

Core responsibilities:
- Scan resumable tasks
- Acquire lease/lock
- Execute next step via execute_next_step_unified()
- Write back state/checkpoint/event
- Mark trigger_source=heartbeat
- Strictly follow failure_policy
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field
import logging

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.runtime.task_runtime import TaskRuntime, get_runtime
from app.runtime.execution_result import UnifiedExecutionResult, FailureClass
from app.runtime.failure_policy import (
    get_failure_policy,
    should_heartbeat_resume,
    can_auto_retry,
    get_background_action,
    BackgroundAction,
    is_background_blocked,
)
from app.runtime.checkpoint import get_checkpoint_manager
from app.logs.event_logger import get_event_logger, EventType


logger = logging.getLogger(__name__)


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat driver."""
    # Scan interval in seconds
    scan_interval_seconds: int = 30
    
    # Maximum concurrent tasks to process
    max_concurrent_tasks: int = 3
    
    # Lease duration in seconds (prevent double execution)
    lease_duration_seconds: int = 60
    
    # Maximum retries per step
    max_step_retries: int = 3
    
    # Tasks older than this are considered stalled
    stalled_threshold_minutes: int = 5


@dataclass
class TaskLease:
    """Lease for preventing concurrent execution."""
    task_id: str
    acquired_at: datetime
    expires_at: datetime
    holder: str  # heartbeat, cron, or foreground
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class HeartbeatDriver:
    """
    Minimal heartbeat driver for background task progression.
    
    Strictly follows failure_policy to prevent:
    - Auto-retry of INTENT_MISMATCH failures
    - Auto-retry of POSTCONDITION_FAILED failures
    - Auto-retry of PATH_EXTRACTION_ERROR failures
    """
    
    def __init__(self, config: Optional[HeartbeatConfig] = None):
        self.config = config or HeartbeatConfig()
        self.task_repo = TaskRepository()
        self.runtime = get_runtime()
        
        # Lease management
        self._leases: Dict[str, TaskLease] = {}
        self._lease_lock = threading.Lock()
        
        # Stop flag for graceful shutdown
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Metrics
        self._ticks = 0
        self._tasks_processed = 0
        self._tasks_completed = 0
        self._tasks_blocked = 0
    
    # ========================================================================
    # Lease Management
    # ========================================================================
    
    def acquire_lease(self, task_id: str, holder: str = "heartbeat") -> bool:
        """
        Acquire a lease for a task.
        
        Args:
            task_id: Task to lease
            holder: Lease holder identifier
        
        Returns:
            True if lease acquired, False if already leased
        """
        with self._lease_lock:
            now = datetime.now()
            
            # Check existing lease
            existing = self._leases.get(task_id)
            if existing and not existing.is_expired():
                logger.debug(f"Lease held by {existing.holder}: {task_id}")
                return False
            
            # Acquire new lease
            self._leases[task_id] = TaskLease(
                task_id=task_id,
                acquired_at=now,
                expires_at=now + timedelta(seconds=self.config.lease_duration_seconds),
                holder=holder
            )
            logger.debug(f"Lease acquired: {task_id} by {holder}")
            return True
    
    def release_lease(self, task_id: str) -> None:
        """Release a task lease."""
        with self._lease_lock:
            if task_id in self._leases:
                del self._leases[task_id]
                logger.debug(f"Lease released: {task_id}")
    
    def is_leased(self, task_id: str) -> bool:
        """Check if a task is currently leased."""
        with self._lease_lock:
            lease = self._leases.get(task_id)
            return lease is not None and not lease.is_expired()
    
    def clear_expired_leases(self) -> int:
        """Clear expired leases and return count."""
        with self._lease_lock:
            expired = [
                task_id for task_id, lease in self._leases.items()
                if lease.is_expired()
            ]
            for task_id in expired:
                del self._leases[task_id]
            return len(expired)
    
    # ========================================================================
    # Task Scanning
    # ========================================================================
    
    def scan_resumable_tasks(self) -> list[Task]:
        """
        Scan for tasks that can be resumed by heartbeat.
        
        Criteria:
        - Status is BLOCKED or RUNNING (stalled)
        - Not currently leased
        - Failure class allows heartbeat resume
        - Not a "false success" failure
        - NOT in WAITING_USER_INPUT state (P2-C)
        
        Returns:
            List of resumable tasks
        """
        resumable = []
        
        # Get all non-terminal tasks
        all_tasks = self.task_repo.list_all(limit=100)
        
        for task in all_tasks:
            # Skip terminal states
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
                continue
            
            # P2-C: Skip WAITING_USER_INPUT - heartbeat cannot resume waiting tasks
            if task.status == TaskStatus.WAITING_USER_INPUT:
                logger.debug(f"Task {task.id} is waiting for user input, skipping")
                continue
            
            # Skip if already leased
            if self.is_leased(task.id):
                continue
            
            # Check if blocked with resumable failure
            if task.status == TaskStatus.BLOCKED:
                # Extract failure class from error
                failure_class = self._extract_failure_class(task)
                
                if failure_class:
                    # Check failure policy
                    if not should_heartbeat_resume(failure_class):
                        logger.debug(f"Heartbeat resume blocked for {task.id}: {failure_class.value}")
                        continue
                    
                    if is_background_blocked(failure_class):
                        logger.debug(f"Background blocked for {task.id}: {failure_class.value}")
                        continue
            
            # Check for stalled running tasks
            if task.status == TaskStatus.RUNNING:
                if self._is_task_stalled(task):
                    logger.info(f"Found stalled task: {task.id}")
                else:
                    continue
            
            resumable.append(task)
        
        return resumable
    
    def _extract_failure_class(self, task: Task) -> Optional[FailureClass]:
        """Extract failure class from task error message."""
        if not task.error:
            return None
        
        # Parse error format: "[failure_class] message"
        error = task.error
        if error.startswith("[") and "]" in error:
            class_str = error[1:error.index("]")]
            try:
                return FailureClass(class_str)
            except ValueError:
                return FailureClass.UNKNOWN
        
        return FailureClass.UNKNOWN
    
    def _is_task_stalled(self, task: Task) -> bool:
        """Check if a running task is stalled (no recent update)."""
        if not task.updated_at:
            return True
        
        threshold = timedelta(minutes=self.config.stalled_threshold_minutes)
        return datetime.now() - task.updated_at > threshold
    
    # ========================================================================
    # Task Execution
    # ========================================================================
    
    def process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a single task with heartbeat driver.
        
        Steps:
        1. Acquire lease
        2. Execute next step
        3. Write checkpoint
        4. Log event with trigger_source=heartbeat
        5. Release lease
        
        Args:
            task: Task to process
        
        Returns:
            Processing result dict
        """
        result = {
            "task_id": task.id,
            "status": "skipped",
            "trigger_source": "heartbeat",
            "timestamp": datetime.now().isoformat()
        }
        
        # Acquire lease
        if not self.acquire_lease(task.id, "heartbeat"):
            result["reason"] = "Could not acquire lease"
            return result
        
        try:
            # Ensure task is in running state
            if task.status == TaskStatus.BLOCKED:
                # Check if retry is allowed
                failure_class = self._extract_failure_class(task)
                retry_count = task.metadata.get("retry_count", 0)
                
                if failure_class and not can_auto_retry(failure_class, retry_count):
                    result["status"] = "blocked_by_policy"
                    result["failure_class"] = failure_class.value
                    result["reason"] = "Failure class does not allow auto-retry"
                    self._tasks_blocked += 1
                    return result
                
                # Reset to running for retry
                task.status = TaskStatus.RUNNING
                task.metadata["retry_count"] = retry_count + 1
                task.metadata["trigger_source"] = "heartbeat"
                self.task_repo.update(task)
            
            # Execute next step
            task, exec_result = self.runtime.execute_next_step_unified(task.id)
            
            result["exec_status"] = exec_result.status.value
            result["success"] = exec_result.success
            
            if exec_result.failure_class:
                result["failure_class"] = exec_result.failure_class.value
            
            # Determine result status
            if exec_result.success:
                if task.status == TaskStatus.COMPLETED:
                    result["status"] = "completed"
                    self._tasks_completed += 1
                else:
                    result["status"] = "progress"
            else:
                if task.status == TaskStatus.BLOCKED:
                    result["status"] = "blocked"
                elif task.status == TaskStatus.FAILED:
                    result["status"] = "failed"
                    self._tasks_blocked += 1
                
                # Check if we should notify user
                from app.runtime.failure_policy import requires_user_notification
                if exec_result.failure_class and requires_user_notification(exec_result.failure_class):
                    result["notify_user"] = True
                    result["manual_hint"] = get_background_action(exec_result.failure_class).value
            
            # Save checkpoint
            get_checkpoint_manager().create_checkpoint(task)
            
            # Log event
            get_event_logger().log_event(
                EventType.TASK_PROGRESS if exec_result.success else EventType.STEP_FAILED,
                {
                    "trigger_source": "heartbeat",
                    "step_index": task.current_step_index,
                    "exec_status": exec_result.status.value,
                    "failure_class": exec_result.failure_class.value if exec_result.failure_class else None,
                },
                task_id=task.id
            )
            
            self._tasks_processed += 1
            
        except Exception as e:
            logger.error(f"Heartbeat process error for {task.id}: {e}")
            result["status"] = "error"
            result["error"] = str(e)
        
        finally:
            self.release_lease(task.id)
        
        return result
    
    # ========================================================================
    # Main Loop
    # ========================================================================
    
    def tick(self) -> Dict[str, Any]:
        """
        Single heartbeat tick.
        
        Scans for resumable tasks and processes them.
        
        Returns:
            Tick result summary
        """
        self._ticks += 1
        
        result = {
            "tick": self._ticks,
            "timestamp": datetime.now().isoformat(),
            "tasks_scanned": 0,
            "tasks_processed": 0,
            "tasks": []
        }
        
        # Clear expired leases
        expired = self.clear_expired_leases()
        if expired > 0:
            logger.debug(f"Cleared {expired} expired leases")
        
        # Scan for resumable tasks
        tasks = self.scan_resumable_tasks()
        result["tasks_scanned"] = len(tasks)
        
        # Process up to max_concurrent_tasks
        processed = 0
        for task in tasks[:self.config.max_concurrent_tasks]:
            task_result = self.process_task(task)
            result["tasks"].append(task_result)
            if task_result.get("status") not in ("skipped", "blocked_by_policy"):
                processed += 1
        
        result["tasks_processed"] = processed
        
        return result
    
    def start(self, background: bool = True) -> None:
        """
        Start the heartbeat driver.
        
        Args:
            background: If True, run in background thread
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Heartbeat driver already running")
            return
        
        self._stop_event.clear()
        
        if background:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Heartbeat driver started in background")
        else:
            self._run_loop()
    
    def stop(self) -> None:
        """Stop the heartbeat driver."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat driver stopped")
    
    def _run_loop(self) -> None:
        """Main run loop."""
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Heartbeat tick error: {e}")
            
            # Wait for next interval
            self._stop_event.wait(self.config.scan_interval_seconds)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get heartbeat driver metrics."""
        return {
            "ticks": self._ticks,
            "tasks_processed": self._tasks_processed,
            "tasks_completed": self._tasks_completed,
            "tasks_blocked": self._tasks_blocked,
            "active_leases": len(self._leases),
            "is_running": self._thread is not None and self._thread.is_alive(),
        }


# Global instance
_driver: Optional[HeartbeatDriver] = None


def get_heartbeat_driver(config: Optional[HeartbeatConfig] = None) -> HeartbeatDriver:
    """Get or create global heartbeat driver instance."""
    global _driver
    if _driver is None:
        _driver = HeartbeatDriver(config)
    return _driver


def start_heartbeat(config: Optional[HeartbeatConfig] = None) -> HeartbeatDriver:
    """Start the heartbeat driver."""
    driver = get_heartbeat_driver(config)
    driver.start()
    return driver


def stop_heartbeat() -> None:
    """Stop the heartbeat driver."""
    global _driver
    if _driver:
        _driver.stop()
