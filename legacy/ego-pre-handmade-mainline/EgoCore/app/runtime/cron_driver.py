"""
OpenEmotion Agent Runtime - Cron Recovery Driver

P2-B.3: Minimal cron driver for compensating missed heartbeat tasks.

Core responsibilities:
- Periodically scan durable task store
- Find stalled tasks (missed heartbeat)
- Perform safe one-time compensation
- Mark trigger_source=cron
- Handle missed heartbeat scenarios
- NEVER retry INTENT_MISMATCH / PATH_EXTRACTION_ERROR
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.runtime.task_runtime import TaskRuntime, get_runtime
from app.runtime.execution_result import UnifiedExecutionResult, FailureClass
from app.runtime.failure_policy import (
    get_failure_policy,
    should_cron_resume,
    can_auto_retry,
    get_background_action,
    BackgroundAction,
    is_background_blocked,
    is_false_success_failure,
)
from app.runtime.checkpoint import get_checkpoint_manager
from app.runtime.heartbeat_driver import HeartbeatDriver, get_heartbeat_driver
from app.logs.event_logger import get_event_logger, EventType


logger = logging.getLogger(__name__)


@dataclass
class CronConfig:
    """Configuration for cron recovery driver."""
    # Scan interval in seconds (less frequent than heartbeat)
    scan_interval_seconds: int = 300  # 5 minutes
    
    # Tasks older than this are considered missed-heartbeat
    missed_heartbeat_threshold_minutes: int = 10
    
    # Maximum tasks to recover per scan
    max_recovery_per_scan: int = 5
    
    # Maximum recovery attempts per task
    max_recovery_attempts: int = 2
    
    # Lease duration in seconds
    lease_duration_seconds: int = 120


class CronRecoveryDriver:
    """
    Minimal cron recovery driver for compensating missed heartbeat tasks.
    
    Key differences from heartbeat:
    - Less frequent (5 min vs 30 sec)
    - Focus on stalled/missed-heartbeat scenarios
    - More conservative retry policy
    - Never retries false-success failures
    
    Strictly follows failure_policy to prevent:
    - Retry of INTENT_MISMATCH
    - Retry of POSTCONDITION_FAILED
    - Retry of PATH_EXTRACTION_ERROR
    """
    
    def __init__(self, config: Optional[CronConfig] = None):
        self.config = config or CronConfig()
        self.task_repo = TaskRepository()
        self.runtime = get_runtime()
        
        # Recovery tracking
        self._recovery_attempts: Dict[str, int] = {}
        
        # Stop flag
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Metrics
        self._scans = 0
        self._tasks_recovered = 0
        self._recovery_blocked = 0
    
    # ========================================================================
    # Task Scanning
    # ========================================================================
    
    def find_stalled_tasks(self) -> List[Task]:
        """
        Find tasks that need cron recovery.
        
        Criteria:
        - Status is BLOCKED or RUNNING
        - No recent update (missed heartbeat window)
        - Not recently recovered
        - Failure class allows cron resume
        - NOT in WAITING_USER_INPUT state (P2-C)
        
        Returns:
            List of stalled tasks
        """
        stalled = []
        threshold = datetime.now() - timedelta(
            minutes=self.config.missed_heartbeat_threshold_minutes
        )
        
        all_tasks = self.task_repo.list_all(limit=100)
        
        for task in all_tasks:
            # Skip terminal states
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
                continue
            
            # P2-C: Skip WAITING_USER_INPUT - cron cannot resume waiting tasks
            if task.status == TaskStatus.WAITING_USER_INPUT:
                logger.debug(f"Task {task.id} is waiting for user input, skipping")
                continue
            # Skip terminal states
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
                continue
            
            # Check if task is stalled (no recent update)
            if task.updated_at and task.updated_at > threshold:
                continue
            
            # Check recovery attempts
            attempts = self._recovery_attempts.get(task.id, 0)
            if attempts >= self.config.max_recovery_attempts:
                logger.debug(f"Max recovery attempts reached: {task.id}")
                continue
            
            # Check failure class for BLOCKED tasks
            if task.status == TaskStatus.BLOCKED:
                failure_class = self._extract_failure_class(task)
                
                if failure_class:
                    # NEVER retry false-success failures
                    if is_false_success_failure(failure_class):
                        logger.info(f"Cron blocked (false-success): {task.id} - {failure_class.value}")
                        continue
                    
                    # Check cron resume policy
                    if not should_cron_resume(failure_class):
                        logger.debug(f"Cron resume blocked: {task.id} - {failure_class.value}")
                        continue
                    
                    if is_background_blocked(failure_class):
                        logger.debug(f"Background blocked: {task.id} - {failure_class.value}")
                        continue
            
            stalled.append(task)
        
        return stalled
    
    def _extract_failure_class(self, task: Task) -> Optional[FailureClass]:
        """Extract failure class from task error message."""
        if not task.error:
            return None
        
        error = task.error
        if error.startswith("[") and "]" in error:
            class_str = error[1:error.index("]")]
            try:
                return FailureClass(class_str)
            except ValueError:
                return FailureClass.UNKNOWN
        
        return FailureClass.UNKNOWN
    
    # ========================================================================
    # Recovery Execution
    # ========================================================================
    
    def recover_task(self, task: Task) -> Dict[str, Any]:
        """
        Perform one-time recovery for a stalled task.
        
        Steps:
        1. Check recovery eligibility
        2. Attempt safe compensation
        3. Update tracking
        4. Log event with trigger_source=cron
        
        Args:
            task: Task to recover
        
        Returns:
            Recovery result dict
        """
        result = {
            "task_id": task.id,
            "status": "skipped",
            "trigger_source": "cron",
            "timestamp": datetime.now().isoformat()
        }
        
        # Increment recovery attempts
        attempts = self._recovery_attempts.get(task.id, 0) + 1
        self._recovery_attempts[task.id] = attempts
        result["recovery_attempt"] = attempts
        
        if attempts > self.config.max_recovery_attempts:
            result["status"] = "max_attempts_exceeded"
            return result
        
        try:
            # For BLOCKED tasks, check if retry is allowed
            if task.status == TaskStatus.BLOCKED:
                failure_class = self._extract_failure_class(task)
                retry_count = task.metadata.get("retry_count", 0)
                
                if failure_class:
                    # NEVER retry false-success failures
                    if is_false_success_failure(failure_class):
                        result["status"] = "blocked_false_success"
                        result["failure_class"] = failure_class.value
                        result["reason"] = "Cannot auto-retry intent/postcondition failure"
                        self._recovery_blocked += 1
                        return result
                    
                    if not can_auto_retry(failure_class, retry_count):
                        result["status"] = "blocked_by_policy"
                        result["failure_class"] = failure_class.value
                        self._recovery_blocked += 1
                        return result
                
                # Reset to running for retry
                task.status = TaskStatus.RUNNING
                task.metadata["retry_count"] = retry_count + 1
                task.metadata["trigger_source"] = "cron"
                task.metadata["recovery_attempt"] = attempts
                self.task_repo.update(task)
            
            # For RUNNING tasks (stalled), try to continue
            if task.status == TaskStatus.RUNNING:
                task.metadata["trigger_source"] = "cron"
                task.metadata["recovery_attempt"] = attempts
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
                    result["status"] = "recovered_completed"
                    self._tasks_recovered += 1
                else:
                    result["status"] = "recovered_progress"
                    self._tasks_recovered += 1
            else:
                if task.status == TaskStatus.BLOCKED:
                    result["status"] = "recovered_blocked"
                elif task.status == TaskStatus.FAILED:
                    result["status"] = "recovered_failed"
                
                # Check user notification requirement
                from app.runtime.failure_policy import requires_user_notification
                if exec_result.failure_class and requires_user_notification(exec_result.failure_class):
                    result["notify_user"] = True
            
            # Save checkpoint
            get_checkpoint_manager().create_checkpoint(task)
            
            # Log event
            get_event_logger().log_event(
                EventType.TASK_PROGRESS if exec_result.success else EventType.STEP_FAILED,
                {
                    "trigger_source": "cron",
                    "recovery_attempt": attempts,
                    "step_index": task.current_step_index,
                    "exec_status": exec_result.status.value,
                    "failure_class": exec_result.failure_class.value if exec_result.failure_class else None,
                },
                task_id=task.id
            )
            
        except Exception as e:
            logger.error(f"Cron recovery error for {task.id}: {e}")
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    # ========================================================================
    # Main Loop
    # ========================================================================
    
    def scan(self) -> Dict[str, Any]:
        """
        Single cron scan.
        
        Finds stalled tasks and attempts recovery.
        
        Returns:
            Scan result summary
        """
        self._scans += 1
        
        result = {
            "scan": self._scans,
            "timestamp": datetime.now().isoformat(),
            "tasks_found": 0,
            "tasks_recovered": 0,
            "tasks": []
        }
        
        # Find stalled tasks
        tasks = self.find_stalled_tasks()
        result["tasks_found"] = len(tasks)
        
        # Clean up old recovery attempts
        self._cleanup_recovery_attempts()
        
        # Recover up to max_recovery_per_scan
        recovered = 0
        for task in tasks[:self.config.max_recovery_per_scan]:
            recovery_result = self.recover_task(task)
            result["tasks"].append(recovery_result)
            
            if "recovered" in recovery_result.get("status", ""):
                recovered += 1
        
        result["tasks_recovered"] = recovered
        
        return result
    
    def _cleanup_recovery_attempts(self) -> None:
        """Clean up old recovery attempts for completed tasks."""
        to_remove = []
        for task_id in self._recovery_attempts:
            task = self.task_repo.get(task_id)
            if not task or task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._recovery_attempts[task_id]
    
    def start(self, background: bool = True) -> None:
        """
        Start the cron recovery driver.
        
        Args:
            background: If True, run in background thread
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Cron recovery driver already running")
            return
        
        self._stop_event.clear()
        
        if background:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Cron recovery driver started in background")
        else:
            self._run_loop()
    
    def stop(self) -> None:
        """Stop the cron recovery driver."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Cron recovery driver stopped")
    
    def _run_loop(self) -> None:
        """Main run loop."""
        while not self._stop_event.is_set():
            try:
                self.scan()
            except Exception as e:
                logger.error(f"Cron scan error: {e}")
            
            # Wait for next interval
            self._stop_event.wait(self.config.scan_interval_seconds)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cron recovery driver metrics."""
        return {
            "scans": self._scans,
            "tasks_recovered": self._tasks_recovered,
            "recovery_blocked": self._recovery_blocked,
            "tracked_tasks": len(self._recovery_attempts),
            "is_running": self._thread is not None and self._thread.is_alive(),
        }


# Global instance
_cron_driver: Optional[CronRecoveryDriver] = None


def get_cron_driver(config: Optional[CronConfig] = None) -> CronRecoveryDriver:
    """Get or create global cron recovery driver instance."""
    global _cron_driver
    if _cron_driver is None:
        _cron_driver = CronRecoveryDriver(config)
    return _cron_driver


def start_cron(config: Optional[CronConfig] = None) -> CronRecoveryDriver:
    """Start the cron recovery driver."""
    driver = get_cron_driver(config)
    driver.start()
    return driver


def stop_cron() -> None:
    """Stop the cron recovery driver."""
    global _cron_driver
    if _cron_driver:
        _cron_driver.stop()
