"""
OpenEmotion Agent Runtime - Task Runtime

Core task execution engine with state management.
"""

from datetime import datetime
from typing import Optional, List, Callable, Any

from app.storage.models import Task, TaskStep, TaskStatus, TaskStepStatus
from app.storage.repositories import TaskRepository, TaskStepRepository
from app.runtime.state_machine import StateMachine, InvalidStateTransition, transition_to
from app.runtime.planner import TaskPlanner
from app.runtime.checkpoint import get_checkpoint_manager
from app.tools import get_registry
from app.config import get_config
from app.logs.event_logger import get_event_logger, EventType
from app.memory.task_memory import get_task_handler
from app.runtime.execution_result import (
    UnifiedExecutionResult, ExecutionStatus, FailureClass,
    ExecutionEvidence, RetryHint, classify_error, should_retry
)
from app.runtime.tool_doctor import run_preflight, get_doctor
from app.runtime.intent_mapper import parse_intent, OperationType
from app.runtime.postcondition import validate_postcondition
# P2-A.2: Intent mapping and postcondition validation
from app.runtime.intent_mapper import parse_intent, OperationType, OperationIntent
from app.runtime.postcondition import validate_postcondition, get_postcondition_validator


# Legacy ExecutionResult - kept for backward compatibility
# New code should use UnifiedExecutionResult
class ExecutionResult:
    """
    Legacy result of step execution.
    
    DEPRECATED: Use UnifiedExecutionResult instead.
    This class provides backward compatibility.
    """
    def __init__(self, success: bool, output: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.output = output
        self.error = error
    
    @classmethod
    def from_unified(cls, result: UnifiedExecutionResult) -> "ExecutionResult":
        """Convert from UnifiedExecutionResult."""
        return cls(
            success=result.success,
            output=result.output,
            error=result.error
        )
    
    def to_unified(self) -> UnifiedExecutionResult:
        """Convert to UnifiedExecutionResult."""
        if self.success:
            return UnifiedExecutionResult.success_result(
                summary="Step completed",
                output=self.output
            )
        else:
            return UnifiedExecutionResult.failure_result(
                summary=self.error or "Step failed",
                failure_class=FailureClass.UNKNOWN
            )


class TaskRuntime:
    """
    Task execution runtime.
    
    Handles:
    - Task creation and planning
    - State transitions
    - Step execution
    - Progress tracking
    """
    
    def __init__(self, task_repo: Optional[TaskRepository] = None,
                 step_repo: Optional[TaskStepRepository] = None):
        """
        Initialize task runtime.
        
        Args:
            task_repo: Task repository (creates new if not provided)
            step_repo: Step repository (creates new if not provided)
        """
        self.task_repo = task_repo or TaskRepository()
        self.step_repo = step_repo or TaskStepRepository()
        
        # Step executor (can be customized)
        self._step_executor: Optional[Callable[[TaskStep], ExecutionResult]] = None
    
    def set_step_executor(self, executor: Callable[[TaskStep], ExecutionResult]) -> None:
        """
        Set custom step executor.
        
        Args:
            executor: Function that executes a step and returns result
        """
        self._step_executor = executor
    
    def create_task(self, objective: str, chat_id: Optional[str] = None,
                    user_id: Optional[str] = None, scope_key: Optional[str] = None) -> Task:
        """
        Create a new task with optional scope.
        
        Args:
            objective: Task objective/description
            chat_id: Chat/conversation identifier
            user_id: User identifier
            scope_key: Combined scope key
        
        Returns:
            Created task
        """
        # Create task object with scope
        task = Task.create(objective, chat_id=chat_id, user_id=user_id, scope_key=scope_key)
        
        # Save to database
        self.task_repo.create(task)
        
        # Log task created event
        get_event_logger().log_event(
            EventType.TASK_CREATED,
            {"objective": objective, "scope_key": scope_key},
            task_id=task.id
        )
        
        # Create initial checkpoint
        get_checkpoint_manager().create_checkpoint(task)
        
        return task
    
    def plan_task(self, task_id: str) -> Task:
        """
        Plan a task (decompose into steps).
        
        Args:
            task_id: Task identifier
        
        Returns:
            Updated task with steps
        
        Raises:
            ValueError: If task not found or invalid state
        """
        # Load task
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Validate state transition
        transition_to(task.status, TaskStatus.PLANNING)
        
        # Update status to planning
        task.status = TaskStatus.PLANNING
        self.task_repo.update(task)
        
        # Generate steps
        steps = TaskPlanner.create_steps(task)
        
        # Save steps
        for step in steps:
            self.step_repo.create(step)
            task.steps.append(step)
        
        # Update task with steps count
        self.task_repo.update(task)
        
        return task
    
    def start_task(self, task_id: str) -> Task:
        """
        Start task execution.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Updated task
        
        Raises:
            ValueError: If task not found or invalid state
        """
        # Load task
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Validate transition
        transition_to(task.status, TaskStatus.RUNNING)
        
        # Update status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.task_repo.update(task)
        
        return task
    
    def execute_next_step(self, task_id: str) -> tuple[Task, ExecutionResult]:
        """
        Execute the next step in a task.
        
        DEPRECATED: Use execute_next_step_unified instead.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Tuple of (updated task, execution result)
        """
        task, unified = self.execute_next_step_unified(task_id)
        return task, ExecutionResult.from_unified(unified)
    
    def execute_next_step_unified(self, task_id: str) -> tuple[Task, UnifiedExecutionResult]:
        """
        Execute the next step in a task with unified result model.
        
        This is the main execution path that returns UnifiedExecutionResult
        with full diagnostic information (status, failure_class, retry_hint, etc.)
        
        Args:
            task_id: Task identifier
        
        Returns:
            Tuple of (updated task, unified execution result)
        
        Raises:
            ValueError: If task not found, no steps, or invalid state
        """
        # Load task
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Check if running
        if task.status != TaskStatus.RUNNING:
            raise ValueError(f"Task is not running: {task.status.value}")
        
        # Get current step
        current_step = task.current_step
        if not current_step:
            # No more steps - complete the task
            self._complete_task(task)
            return task, UnifiedExecutionResult.success_result(
                summary="All steps completed",
                output="All steps completed"
            )
        
        # Log step started
        get_event_logger().log_event(
            EventType.STEP_STARTED,
            {"step_id": current_step.id, "description": current_step.description},
            task_id=task.id
        )
        
        # Execute step (returns UnifiedExecutionResult)
        result = self._execute_step_unified(current_step)
        
        # Update step status based on unified result
        if result.success:
            current_step.status = TaskStepStatus.COMPLETED
            current_step.completed_at = datetime.now()
            current_step.result = result.output
            
            # Log step completed
            get_event_logger().log_event(
                EventType.STEP_COMPLETED,
                {"step_id": current_step.id, "output_preview": result.output[:100] if result.output else None},
                task_id=task.id
            )
            
            # Move to next step
            task.current_step_index += 1
            
            # Check if all steps done
            if task.current_step_index >= len(task.steps):
                self._complete_task(task)
            else:
                # Save checkpoint after each step
                get_checkpoint_manager().create_checkpoint(task)
        else:
            # Handle failure based on failure_class
            current_step.status = TaskStepStatus.FAILED
            current_step.error = result.error
            
            # Determine task status based on failure_class and retry_hint
            if result.is_retryable and result.retry_hint:
                # Transient failure - keep in BLOCKED for retry
                task.status = TaskStatus.BLOCKED
                task.error = f"[{result.failure_class.value if result.failure_class else 'unknown'}] {result.summary}"
            elif result.failure_class == FailureClass.SAFETY_BLOCK:
                # Safety blocked - keep in BLOCKED
                task.status = TaskStatus.BLOCKED
                task.error = f"[safety_block] {result.summary}"
            else:
                # Terminal failure
                task.status = TaskStatus.FAILED
                task.error = f"[{result.failure_class.value if result.failure_class else 'unknown'}] {result.summary}"
            
            # Log step failed with failure_class
            get_event_logger().log_event(
                EventType.STEP_FAILED,
                {
                    "step_id": current_step.id,
                    "error": result.error,
                    "failure_class": result.failure_class.value if result.failure_class else "unknown",
                    "retryable": result.is_retryable
                },
                task_id=task.id
            )
        
        # Update task in repository
        self.task_repo.update(task)
        self.step_repo.update(current_step)
        
        # Save task memory with failure context
        self._save_task_memory(task, result.success, result.error)
        
        return task, result
    
    def pause_task(self, task_id: str) -> Task:
        """
        Pause a running task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Updated task
        
        Raises:
            ValueError: If task not found or invalid state
        """
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        transition_to(task.status, TaskStatus.PAUSED)
        
        task.status = TaskStatus.PAUSED
        self.task_repo.update(task)
        
        # Save task memory when paused (T4)
        self._save_task_memory(task, success=True, note="Task paused")
        
        return task
    
    def resume_task(self, task_id: str) -> Task:
        """
        Resume a paused task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Updated task
        
        Raises:
            ValueError: If task not found or invalid state
        """
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        transition_to(task.status, TaskStatus.RUNNING)
        
        task.status = TaskStatus.RUNNING
        self.task_repo.update(task)
        
        # Save task memory when resumed (T4)
        self._save_task_memory(task, success=True, note="Task resumed")
        
        return task
    
    def get_resume_context(self, task_id: Optional[str] = None) -> dict:
        """
        Get resume context from task memory.
        
        Args:
            task_id: Optional specific task ID
        
        Returns:
            Resume context dict
        """
        task_memory = get_task_handler()
        return task_memory.build_resume_context(task_id)
    
    def abort_task(self, task_id: str) -> Task:
        """
        Abort a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Updated task
        
        Raises:
            ValueError: If task not found or invalid state
        """
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        transition_to(task.status, TaskStatus.ABORTED)
        
        task.status = TaskStatus.ABORTED
        task.completed_at = datetime.now()
        self.task_repo.update(task)
        
        return task
    
    def retry_step(self, task_id: str) -> tuple[Task, ExecutionResult]:
        """
        Retry the last failed step.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Tuple of (updated task, execution result)
        
        Raises:
            ValueError: If task not found or no failed step
        """
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        if task.status != TaskStatus.BLOCKED:
            raise ValueError(f"Task is not blocked: {task.status.value}")
        
        # Get failed step
        current_step = task.current_step
        if not current_step or current_step.status != TaskStepStatus.FAILED:
            raise ValueError("No failed step to retry")
        
        # Reset step
        current_step.status = TaskStepStatus.PENDING
        current_step.error = None
        current_step.started_at = None
        current_step.completed_at = None
        self.step_repo.update(current_step)
        
        # Set task to running
        task.status = TaskStatus.RUNNING
        task.error = None
        self.task_repo.update(task)
        
        # Execute step
        return self.execute_next_step(task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task if found, None otherwise
        """
        return self.task_repo.get(task_id)
    
    def get_active_task(self) -> Optional[Task]:
        """
        Get the currently active task.
        
        Returns:
            Active task if exists, None otherwise
        """
        return self.task_repo.get_active()
    
    def list_tasks(self, limit: int = 100) -> List[Task]:
        """
        List all tasks.
        
        Args:
            limit: Maximum number of tasks to return
        
        Returns:
            List of tasks
        """
        return self.task_repo.list_all(limit=limit)
    
    def _execute_step(self, step: TaskStep) -> ExecutionResult:
        """
        Execute a step with unified result model.
        
        DEPRECATED: Use _execute_step_unified instead.
        
        Args:
            step: Step to execute
        
        Returns:
            ExecutionResult (legacy wrapper)
        """
        unified_result = self._execute_step_unified(step)
        return ExecutionResult.from_unified(unified_result)
    
    def _execute_step_unified(self, step: TaskStep) -> UnifiedExecutionResult:
        """
        Execute a step and return UnifiedExecutionResult.
        
        This is the main execution path that returns full diagnostic information.
        
        Args:
            step: Step to execute
        
        Returns:
            UnifiedExecutionResult with status, failure_class, retry_hint, etc.
        """
        # Update step status
        step.status = TaskStepStatus.RUNNING
        step.started_at = datetime.now()
        self.step_repo.update(step)
        
        # Execute
        if self._step_executor:
            legacy_result = self._step_executor(step)
            # Convert to unified if needed
            if isinstance(legacy_result, UnifiedExecutionResult):
                return legacy_result
            else:
                return legacy_result.to_unified()
        else:
            # Default executor with unified result model
            return self._default_executor_unified(step)
    
    def _default_executor_unified(self, step: TaskStep) -> UnifiedExecutionResult:
        """
        Default step executor with intent mapping and postcondition validation.
        
        P2-A.2: Uses IntentMapper to correctly parse user intent and 
        PostconditionValidator to verify execution matches intent.
        
        This prevents "fake completed" scenarios where:
        - Tool executes successfully
        - But actual result doesn't match user's goal
        """
        step_desc = step.description
        evidence = ExecutionEvidence(
            operation="step_execution",
            step_id=step.id
        )
        
        try:
            tool_registry = get_registry()
            config = get_config()
            
            # Check for time query (no tool needed)
            if '时间' in step_desc or 'time' in step_desc or 'date' in step_desc or '日期' in step_desc:
                from datetime import datetime as dt
                now = dt.now()
                return UnifiedExecutionResult.success_result(
                    summary="时间查询成功",
                    output=f"当前系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n日期: {now.strftime('%Y年%m月%d日')}\n星期: {['一','二','三','四','五','六','日'][now.weekday()]}",
                    evidence=evidence
                )
            
            # P2-A.2: Use IntentMapper to parse the operation intent
            intent = parse_intent(step_desc)
            
            # Log intent parsing result
            evidence.additional_data["intent"] = intent.to_dict()
            
            # Route based on operation type
            if intent.operation == OperationType.LIST_DIR:
                return self._execute_list_dir(intent, tool_registry, evidence)
            
            elif intent.operation == OperationType.READ_FILE:
                return self._execute_read_file(intent, tool_registry, evidence)
            
            elif intent.operation == OperationType.WRITE_FILE:
                return self._execute_write_file(intent, tool_registry, evidence)
            
            elif intent.operation == OperationType.MKDIR:
                return self._execute_mkdir(intent, tool_registry, evidence)
            
            elif intent.operation == OperationType.EXISTS:
                return self._execute_exists(intent, tool_registry, evidence)
            
            # Fallback: Try shell command detection (legacy)
            step_desc_lower = step_desc.lower()
            if 'run' in step_desc_lower or 'execute' in step_desc_lower or '执行' in step_desc_lower:
                import re
                cmd_match = re.search(r'`([^`]+)`|"([^"]+)"', step_desc)
                if cmd_match:
                    cmd = cmd_match.group(1) or cmd_match.group(2)
                    return self._execute_shell_command(cmd, tool_registry, evidence)
            
            # Fallback: Try LLM for complex queries
            try:
                from app.llm_client import get_llm_client
                llm = get_llm_client()
                
                system_prompt = config.get_prompt('executor_prompt') or "你是一个AI助手，帮助用户完成任务。"
                response = llm.generate(step_desc, system_prompt=system_prompt)
                
                return UnifiedExecutionResult.success_result(
                    summary="LLM 响应成功",
                    output=response.content,
                    evidence=evidence
                )
            except Exception as llm_err:
                failure_class = classify_error(llm_err)
                retry_hint = should_retry(failure_class)
                return UnifiedExecutionResult.failure_result(
                    summary=f"LLM 调用失败: {str(llm_err)[:50]}",
                    failure_class=failure_class,
                    user_safe_message="无法获取 AI 响应，请稍后重试",
                    retry_hint=retry_hint,
                    evidence=evidence
                )
                
        except Exception as e:
            failure_class = classify_error(e)
            return UnifiedExecutionResult.failure_result(
                summary=f"执行失败: {str(e)}",
                failure_class=failure_class,
                user_safe_message=f"执行遇到问题: {str(e)[:100]}",
                evidence=evidence
            )
    
    def _execute_list_dir(
        self, 
        intent: OperationIntent, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute LIST_DIR operation with postcondition validation."""
        target_path = intent.target_path
        
        if not target_path:
            return UnifiedExecutionResult.failure_result(
                summary="无法解析目标目录路径",
                failure_class=FailureClass.PATH_EXTRACTION_ERROR,
                user_safe_message="请指定要查看的目录路径",
                evidence=evidence
            )
        
        # Preflight check
        preflight_result = run_preflight("file", {
            "operation": "list",
            "path": target_path
        })
        
        if not preflight_result.success:
            return preflight_result
        
        # Execute tool
        result = tool_registry.execute("file", {
            "operation": "list",
            "path": target_path
        })
        
        # Build initial result
        if result.success:
            tool_result = UnifiedExecutionResult.success_result(
                summary=f"目录列表获取成功: {target_path}",
                output=result.output[:1000] if result.output else "目录为空",
                evidence=evidence
            )
        else:
            tool_result = UnifiedExecutionResult.failure_result(
                summary=f"目录列表获取失败: {target_path}",
                failure_class=FailureClass.TOOL_ERROR,
                user_safe_message=f"无法列出目录: {result.error}",
                next_action="检查目录路径是否正确",
                evidence=evidence
            )
        
        # P2-A.2: Postcondition validation
        return validate_postcondition(intent, target_path, tool_result)
    
    def _execute_read_file(
        self, 
        intent: OperationIntent, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute READ_FILE operation with postcondition validation."""
        target_path = intent.target_path
        
        if not target_path:
            return UnifiedExecutionResult.failure_result(
                summary="无法解析目标文件路径",
                failure_class=FailureClass.PATH_EXTRACTION_ERROR,
                user_safe_message="请指定要读取的文件路径",
                evidence=evidence
            )
        
        # Preflight check
        preflight_result = run_preflight("file", {
            "operation": "read",
            "path": target_path
        })
        
        if not preflight_result.success:
            return preflight_result
        
        # Execute tool
        result = tool_registry.execute("file", {
            "operation": "read",
            "path": target_path
        })
        
        # Build initial result
        if result.success:
            tool_result = UnifiedExecutionResult.success_result(
                summary=f"文件读取成功: {target_path}",
                output=result.output[:2000] if result.output else "文件为空",
                evidence=evidence
            )
        else:
            tool_result = UnifiedExecutionResult.failure_result(
                summary=f"文件读取失败: {target_path}",
                failure_class=FailureClass.TOOL_ERROR,
                user_safe_message=f"无法读取文件: {result.error}",
                next_action="检查文件路径是否正确",
                evidence=evidence
            )
        
        # P2-A.2: Postcondition validation
        return validate_postcondition(intent, target_path, tool_result)
    
    def _execute_write_file(
        self, 
        intent: OperationIntent, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute WRITE_FILE operation with postcondition validation."""
        target_path = intent.target_path
        content = intent.content or ""  # Empty content for file creation
        
        if not target_path:
            return UnifiedExecutionResult.failure_result(
                summary="无法解析目标文件路径",
                failure_class=FailureClass.PATH_EXTRACTION_ERROR,
                user_safe_message="请指定要创建的文件路径",
                evidence=evidence
            )
        
        # Check if parent directory exists
        import os
        parent_dir = os.path.dirname(target_path)
        if parent_dir and not os.path.exists(parent_dir):
            return UnifiedExecutionResult.failure_result(
                summary=f"父目录不存在: {parent_dir}",
                failure_class=FailureClass.NOT_FOUND,
                user_safe_message=f"无法创建文件，因为目录不存在: {parent_dir}",
                next_action="请先创建目录，或确认路径正确",
                evidence=evidence
            )
        
        # Preflight check
        preflight_result = run_preflight("file", {
            "operation": "write",
            "path": target_path,
            "content": content
        })
        
        if not preflight_result.success:
            return preflight_result
        
        # Execute tool
        result = tool_registry.execute("file", {
            "operation": "write",
            "path": target_path,
            "content": content
        })
        
        # Build initial result
        if result.success:
            tool_result = UnifiedExecutionResult.success_result(
                summary=f"文件创建成功: {target_path}",
                output=f"已创建文件: {target_path}",
                evidence=evidence
            )
        else:
            tool_result = UnifiedExecutionResult.failure_result(
                summary=f"文件创建失败: {target_path}",
                failure_class=FailureClass.TOOL_ERROR,
                user_safe_message=f"无法创建文件: {result.error}",
                next_action="检查文件路径和权限",
                evidence=evidence
            )
        
        # P2-A.2: Postcondition validation - verify file exists
        return validate_postcondition(intent, target_path, tool_result)
    
    def _execute_mkdir(
        self, 
        intent: OperationIntent, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute MKDIR operation with postcondition validation."""
        target_path = intent.target_path
        
        if not target_path:
            return UnifiedExecutionResult.failure_result(
                summary="无法解析目标目录路径",
                failure_class=FailureClass.PATH_EXTRACTION_ERROR,
                user_safe_message="请指定要创建的目录路径",
                evidence=evidence
            )
        
        # Preflight check
        preflight_result = run_preflight("file", {
            "operation": "mkdir",
            "path": target_path
        })
        
        if not preflight_result.success:
            return preflight_result
        
        # Execute tool (use shell for mkdir)
        import os
        try:
            os.makedirs(target_path, exist_ok=True)
            tool_result = UnifiedExecutionResult.success_result(
                summary=f"目录创建成功: {target_path}",
                output=f"已创建目录: {target_path}",
                evidence=evidence
            )
        except Exception as e:
            tool_result = UnifiedExecutionResult.failure_result(
                summary=f"目录创建失败: {target_path}",
                failure_class=FailureClass.TOOL_ERROR,
                user_safe_message=f"无法创建目录: {str(e)}",
                next_action="检查目录路径和权限",
                evidence=evidence
            )
        
        # P2-A.2: Postcondition validation - verify directory exists
        return validate_postcondition(intent, target_path, tool_result)
    
    def _execute_exists(
        self, 
        intent: OperationIntent, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute EXISTS operation."""
        target_path = intent.target_path
        
        if not target_path:
            return UnifiedExecutionResult.failure_result(
                summary="无法解析目标路径",
                failure_class=FailureClass.PATH_EXTRACTION_ERROR,
                user_safe_message="请指定要检查的路径",
                evidence=evidence
            )
        
        import os
        exists = os.path.exists(target_path)
        
        if exists:
            is_dir = os.path.isdir(target_path)
            type_str = "目录" if is_dir else "文件"
            return UnifiedExecutionResult.success_result(
                summary=f"路径存在: {target_path}",
                output=f"{type_str}存在: {target_path}",
                evidence=evidence
            )
        else:
            return UnifiedExecutionResult.failure_result(
                summary=f"路径不存在: {target_path}",
                failure_class=FailureClass.NOT_FOUND,
                user_safe_message=f"路径不存在: {target_path}",
                evidence=evidence
            )
    
    def _execute_shell_command(
        self, 
        cmd: str, 
        tool_registry, 
        evidence: ExecutionEvidence
    ) -> UnifiedExecutionResult:
        """Execute a shell command with preflight checks."""
        # Preflight check for shell
        preflight_result = run_preflight("shell", {"command": cmd})
        
        if not preflight_result.success:
            # Safety block
            return UnifiedExecutionResult.blocked_result(
                summary=f"命令被安全检查拦截: {cmd[:30]}...",
                failure_class=preflight_result.failure_class or FailureClass.SAFETY_BLOCK,
                reason=preflight_result.user_safe_message,
                next_action="如需执行危险操作，请使用 /confirm 确认",
                evidence=evidence
            )
        
        # Execute tool
        result = tool_registry.execute("shell", {"command": cmd})
        
        if result.success:
            return UnifiedExecutionResult.success_result(
                summary=f"命令执行成功: {cmd[:30]}...",
                output=result.output[:500],
                evidence=evidence
            )
        else:
            failure_class = classify_error(Exception(result.error))
            retry_hint = should_retry(failure_class)
            return UnifiedExecutionResult.failure_result(
                summary=f"命令执行失败: {cmd[:30]}...",
                failure_class=failure_class,
                user_safe_message=f"命令执行失败: {result.error[:100] if result.error else 'Unknown error'}",
                retry_hint=retry_hint,
                evidence=evidence
            )
    
    def _default_executor(self, step: TaskStep) -> ExecutionResult:
        """
        Default step executor (legacy wrapper).
        
        DEPRECATED: Use _default_executor_unified instead.
        """
        unified = self._default_executor_unified(step)
        return ExecutionResult.from_unified(unified)
    
    def _complete_task(self, task: Task) -> None:
        """Mark task as completed."""
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        self.task_repo.update(task)
        
        # Log task completed event
        get_event_logger().log_event(
            EventType.TASK_COMPLETED,
            {"objective": task.objective, "total_steps": len(task.steps)},
            task_id=task.id
        )
        
        # Save final checkpoint
        get_checkpoint_manager().create_checkpoint(task, {"final": True})
    
    def generate_report(self, task_id: str) -> str:
        """
        Generate a detailed diagnostic report for a task.
        
        Includes failure classification, retry hints, and next actions.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Report string with diagnostic information
        """
        task = self.task_repo.get(task_id)
        if not task:
            return f"Task not found: {task_id}"
        
        # Get task memory for additional context
        try:
            task_memory = get_task_handler()
            memory_ctx = task_memory.build_resume_context(task_id)
        except Exception:
            memory_ctx = {}
        
        # Build report
        lines = []
        lines.append(f"📊 *Task Report: {task.id}*")
        lines.append("")
        lines.append(f"🎯 *Objective:* {task.objective}")
        lines.append(f"📌 *Status:* {task.status.value.upper()}")
        lines.append(f"📅 *Created:* {task.created_at.strftime('%Y-%m-%d %H:%M')}")
        
        if task.started_at:
            lines.append(f"🚀 *Started:* {task.started_at.strftime('%Y-%m-%d %H:%M')}")
        
        if task.completed_at:
            lines.append(f"✅ *Completed:* {task.completed_at.strftime('%Y-%m-%d %H:%M')}")
        
        # Progress
        completed, total = task.progress
        progress_pct = task.progress_percentage
        lines.append("")
        lines.append(f"📈 *Progress:* {completed}/{total} steps ({progress_pct:.0f}%)")
        
        # Diagnostic section for non-completed tasks
        if task.status in (TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.PAUSED):
            lines.append("")
            lines.append("🔍 *Diagnostics:*")
            
            # Failure information from memory
            failures = memory_ctx.get('failures', [])
            if failures:
                lines.append(f"❌ *Last Failure:* {failures[-1][:100] if failures else 'N/A'}")
            
            # Blocker
            if task.error:
                lines.append(f"🚫 *Blocker:* {task.error[:100]}")
            
            # Next steps from memory
            next_steps = memory_ctx.get('next_steps', [])
            if next_steps:
                lines.append(f"💡 *Suggested Actions:*")
                for i, step in enumerate(next_steps[:3], 1):
                    lines.append(f"   {i}. {step}")
            
            # Retry recommendation based on status
            if task.status == TaskStatus.BLOCKED:
                lines.append(f"🔄 *Retry:* Use /retry to attempt again")
            elif task.status == TaskStatus.PAUSED:
                lines.append(f"▶️ *Resume:* Use /resume to continue")
            elif task.status == TaskStatus.FAILED:
                lines.append(f"⚠️ *Status:* Task failed, check error above")
        
        # Steps
        if task.steps:
            lines.append("")
            lines.append("*Steps:*")
            for i, step in enumerate(task.steps):
                status_emoji = {
                    TaskStepStatus.PENDING: "⏳",
                    TaskStepStatus.RUNNING: "▶️",
                    TaskStepStatus.COMPLETED: "✅",
                    TaskStepStatus.FAILED: "❌",
                    TaskStepStatus.SKIPPED: "⏭️"
                }.get(step.status, "❓")
                
                current = " *" if i == task.current_step_index else ""
                lines.append(f"  {status_emoji} {i+1}. {step.description}{current}")
                
                if step.result:
                    lines.append(f"     Result: {step.result[:100]}")
                if step.error:
                    lines.append(f"     Error: {step.error}")
        
        # Current step
        current = task.current_step
        if current and task.status == TaskStatus.RUNNING:
            lines.append("")
            lines.append(f"🔄 *Current Step:* {current.description}")
        
        # Next step
        next_idx = task.current_step_index
        if next_idx < len(task.steps):
            next_step = task.steps[next_idx]
            lines.append("")
            lines.append(f"⏭️ *Next Step:* {next_step.description}")
        
        # Error
        if task.error:
            lines.append("")
            lines.append(f"❌ *Error:* {task.error}")
        
        return "\n".join(lines)
    
    def _save_task_memory(self, task: Task, success: bool,
                          error: Optional[str] = None,
                          note: Optional[str] = None) -> None:
        """
        Save task memory for continuity.
        
        This is called after step execution, pause, and resume
        to enable /resume to pick up where work left off.
        
        Args:
            task: Task object
            success: Whether the operation was successful
            error: Error message if failed
            note: Optional note (e.g., "Task paused", "Task resumed")
        """
        try:
            task_memory = get_task_handler()
            
            # Build progress summary
            completed, total = task.progress
            progress_pct = task.progress_percentage
            progress = f"{completed}/{total} steps ({progress_pct:.0f}%)"
            if note:
                progress = f"{progress} - {note}"
            
            # Build next steps list
            next_steps = []
            for i in range(task.current_step_index, len(task.steps)):
                step = task.steps[i]
                if step.status == TaskStepStatus.PENDING:
                    next_steps.append(step.description)
            
            # Build completed steps list
            completed_steps = []
            for step in task.steps:
                if step.status == TaskStepStatus.COMPLETED:
                    completed_steps.append(step.description)
            
            # Build failures list
            failures = []
            if error:
                failures.append(error)
            # Include any previous failures from task
            if task.error:
                failures.append(task.error)
            
            # Determine current step
            current_step = None
            if task.current_step and task.current_step.status == TaskStepStatus.RUNNING:
                current_step = task.current_step.description
            
            # Build context
            context = {
                'chat_id': task.chat_id,
                'user_id': task.user_id,
                'scope_key': task.scope_key
            }
            
            # Save to task memory
            task_memory.save_task_memory(
                task_id=task.id,
                objective=task.objective,
                status=task.status.value,
                progress=progress,
                next_steps=next_steps,
                failures=failures if failures else None,
                completed_steps=completed_steps,
                current_step=current_step,
                context=context
            )
            
        except Exception as e:
            # Log error but don't fail the operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save task memory: {str(e)}")


# Convenience functions
_runtime: Optional[TaskRuntime] = None


def get_runtime() -> TaskRuntime:
    """Get or create global runtime instance."""
    global _runtime
    if _runtime is None:
        _runtime = TaskRuntime()
    return _runtime
