"""
OpenEmotion Agent Runtime - Resume Driver

P2-C.5: Resumes tasks after user confirmation.

Core responsibilities:
- Write user_decision event
- Update task state
- Restore from checkpoint
- Continue unified execution chain
- Do NOT create new task
- Still go through preflight/unified result/postcondition
"""

from datetime import datetime
from typing import Optional, Dict, Any
import logging

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.runtime.task_runtime import TaskRuntime, get_runtime
from app.runtime.approval_policy import ApprovalRequest, ApprovalType
from app.runtime.checkpoint import get_checkpoint_manager
from app.runtime.execution_result import UnifiedExecutionResult
from app.logs.event_logger import get_event_logger, EventType


logger = logging.getLogger(__name__)


class ResumeDriver:
    """
    Resumes tasks after user confirmation.
    
    Key rules:
    - Do NOT create new task
    - Resume from checkpoint
    - Continue unified execution chain
    - Go through preflight/unified result/postcondition
    """
    
    def __init__(
        self,
        task_repo: Optional[TaskRepository] = None,
        runtime: Optional[TaskRuntime] = None,
    ):
        self.task_repo = task_repo or TaskRepository()
        self.runtime = runtime or get_runtime()
    
    def resume_with_decision(
        self,
        task_id: str,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resume a task with a user decision.
        
        Steps:
        1. Load task from repo
        2. Validate task is in waiting state
        3. Write user_decision event
        4. Update task with decision
        5. Restore from checkpoint
        6. Transition to RUNNING
        7. Continue execution
        
        Args:
            task_id: Task to resume
            decision: User's decision dict
        
        Returns:
            Result dict with resume status
        """
        result = {
            "task_id": task_id,
            "success": False,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Load task
        task = self.task_repo.get(task_id)
        if not task:
            result["error"] = f"Task not found: {task_id}"
            return result
        
        # Validate state
        if task.status != TaskStatus.WAITING_USER_INPUT:
            result["error"] = f"Task is not waiting: {task.status.value}"
            result["current_status"] = task.status.value
            return result
        
        # Validate decision
        if not decision.get("is_valid"):
            result["error"] = "Invalid decision"
            result["decision_error"] = decision.get("error")
            return result
        
        # Parse waiting request
        if not task.waiting_request:
            result["error"] = "No waiting request on task"
            return result
        
        try:
            request = ApprovalRequest.from_dict(task.waiting_request)
        except Exception as e:
            result["error"] = f"Failed to parse waiting request: {e}"
            return result
        
        # Write user_decision event
        get_event_logger().log_event(
            EventType.TASK_PROGRESS,
            {
                "event_type": "user_decision",
                "decision": decision,
                "waiting_reason": task.waiting_reason,
            },
            task_id=task_id,
        )
        
        # Update task with decision
        task.user_decision = decision
        task.updated_at = datetime.now()
        
        # Check if user rejected
        if decision.get("approved") is False:
            # User rejected, fail the task
            task.status = TaskStatus.FAILED
            task.error = "[user_rejected] 用户拒绝了操作"
            self.task_repo.update(task)
            
            # Save checkpoint
            get_checkpoint_manager().create_checkpoint(task)
            
            result["success"] = True
            result["action"] = "rejected"
            result["message"] = "操作已取消"
            return result
        
        # User approved, continue execution
        # Update task metadata with clarified values
        if decision.get("clarified_path"):
            task.metadata["clarified_path"] = decision["clarified_path"]
        
        if decision.get("selected_option") is not None:
            task.metadata["selected_option"] = decision["selected_option"]
            if decision.get("selected_value"):
                task.metadata["selected_value"] = decision["selected_value"]
        
        # Transition to RUNNING
        task.status = TaskStatus.RUNNING
        task.waiting_reason = None
        task.waiting_request = None
        self.task_repo.update(task)
        
        # Log resume
        logger.info(f"Task {task_id} resumed with decision")
        
        # Continue execution
        try:
            # If we need to apply clarified values, update current step
            current_step = task.current_step
            if current_step and decision.get("clarified_path"):
                # Update step description with clarified path
                current_step.description = current_step.description.replace(
                    "需要指定路径",
                    decision["clarified_path"]
                )
            
            # Execute next step
            task, exec_result = self.runtime.execute_next_step_unified(task_id)
            
            result["success"] = True
            result["action"] = "resumed"
            result["exec_status"] = exec_result.status.value
            result["exec_success"] = exec_result.success
            
            if task.status == TaskStatus.COMPLETED:
                result["message"] = "任务已完成"
            elif task.status == TaskStatus.WAITING_USER_INPUT:
                result["message"] = "需要进一步确认"
                result["new_waiting_request"] = task.waiting_request
            elif task.status == TaskStatus.BLOCKED:
                result["message"] = f"任务阻塞: {task.error}"
            elif task.status == TaskStatus.FAILED:
                result["message"] = f"任务失败: {task.error}"
            else:
                result["message"] = "任务继续执行中"
            
        except Exception as e:
            logger.error(f"Resume execution failed: {e}")
            result["error"] = str(e)
            result["action"] = "resume_failed"
        
        return result
    
    def resume_from_checkpoint(self, task_id: str) -> Dict[str, Any]:
        """
        Resume a task from its last checkpoint.
        
        Used when decision was already processed but task needs to continue.
        
        Args:
            task_id: Task to resume
        
        Returns:
            Result dict
        """
        result = {
            "task_id": task_id,
            "success": False,
        }
        
        # Load task
        task = self.task_repo.get(task_id)
        if not task:
            result["error"] = f"Task not found: {task_id}"
            return result
        
        # Load checkpoint
        checkpoint = get_checkpoint_manager().load_checkpoint(task_id)
        if not checkpoint:
            result["error"] = "No checkpoint found"
            return result
        
        # Restore state from checkpoint
        task.current_step_index = checkpoint.get("current_step_index", 0)
        
        # Transition to RUNNING
        task.status = TaskStatus.RUNNING
        self.task_repo.update(task)
        
        # Execute next step
        try:
            task, exec_result = self.runtime.execute_next_step_unified(task_id)
            
            result["success"] = True
            result["exec_status"] = exec_result.status.value
            
        except Exception as e:
            result["error"] = str(e)
        
        return result


# ============================================================================
# High-level functions
# ============================================================================

def resume_task_with_user_reply(
    task_id: str,
    user_reply: str,
    decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resume a task with a user reply.
    
    Convenience function that combines binding and resume.
    
    Args:
        task_id: Task to resume
        user_reply: User's reply text
        decision: Optional pre-parsed decision
    
    Returns:
        Result dict
    """
    driver = ResumeDriver()
    
    # If decision not provided, parse it
    if decision is None:
        task_repo = TaskRepository()
        task = task_repo.get(task_id)
        
        if not task or not task.waiting_request:
            return {
                "success": False,
                "error": "Task not found or no waiting request",
            }
        
        from app.runtime.approval_policy import ApprovalRequest, parse_user_decision
        request = ApprovalRequest.from_dict(task.waiting_request)
        decision = parse_user_decision(user_reply, request)
        decision["timestamp"] = datetime.now().isoformat()
    
    return driver.resume_with_decision(task_id, decision)


# ============================================================================
# Global instance
# ============================================================================

_driver: Optional[ResumeDriver] = None


def get_resume_driver() -> ResumeDriver:
    """Get or create global resume driver."""
    global _driver
    if _driver is None:
        _driver = ResumeDriver()
    return _driver
