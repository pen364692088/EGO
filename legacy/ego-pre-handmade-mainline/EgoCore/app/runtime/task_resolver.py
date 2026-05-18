"""
OpenEmotion Agent Runtime - Unified Task Resolver

Provides unified task resolution for continue, resume, and run operations.
Ensures scope isolation and consistent behavior across all entry points.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.command_router import CommandContext


class ResolverSource(str, Enum):
    """Source of task resolution."""
    EXPLICIT_ID = "explicit_id"        # User provided task_id explicitly
    ACTIVE_SCOPE = "active_scope"       # Active task in current scope
    RECENT_SCOPE = "recent_scope"       # Most recent task in scope
    RESUMABLE_SCOPE = "resumable_scope" # Resumable task in scope
    CHECKPOINT = "checkpoint"           # From checkpoint recovery
    MEMORY = "memory"                   # From task memory
    NONE = "none"                       # No task found


@dataclass
class ResolverResult:
    """Result of task resolution."""
    
    task: Optional[Task]
    source: ResolverSource
    scope_key: Optional[str]
    error: Optional[str] = None
    
    # Diagnostic fields
    checked_scopes: list = None
    checked_tasks: int = 0
    
    def __post_init__(self):
        if self.checked_scopes is None:
            self.checked_scopes = []
    
    @property
    def found(self) -> bool:
        """Whether a task was found."""
        return self.task is not None


class UnifiedTaskResolver:
    """
    Unified task resolver for all continue/resume/run operations.
    
    Ensures:
    - Scope isolation (no cross-chat/cross-user binding)
    - Consistent resolution priority across all entry points
    - Clear error messages when no task found
    """
    
    def __init__(self, task_repo: Optional[TaskRepository] = None):
        """
        Initialize resolver.
        
        Args:
            task_repo: Task repository (creates new if not provided)
        """
        self.task_repo = task_repo or TaskRepository()
    
    def resolve(
        self,
        ctx: CommandContext,
        explicit_task_id: Optional[str] = None,
        intent: str = "continue"
    ) -> ResolverResult:
        """
        Resolve task for continue/resume/run operations.
        
        Resolution priority:
        1. Explicit task_id (if provided)
        2. Active task in current scope (running/planning)
        3. Resumable task in current scope (paused/blocked)
        4. Most recent incomplete task in scope
        5. No task found
        
        Args:
            ctx: Command context with chat_id, user_id
            explicit_task_id: Explicitly provided task ID
            intent: Operation intent (continue, resume, run)
        
        Returns:
            ResolverResult with task and resolution details
        """
        # Build scope key
        scope_key = self._build_scope_key(ctx)
        checked_scopes = []
        checked_tasks = 0
        
        # 1. Check explicit task_id
        if explicit_task_id:
            task = self.task_repo.get(explicit_task_id)
            if task:
                # Verify scope matches (security check)
                if task.scope_key and task.scope_key != scope_key:
                    return ResolverResult(
                        task=None,
                        source=ResolverSource.NONE,
                        scope_key=scope_key,
                        error=f"Task {explicit_task_id} belongs to different scope"
                    )
                return ResolverResult(
                    task=task,
                    source=ResolverSource.EXPLICIT_ID,
                    scope_key=scope_key,
                    checked_scopes=[scope_key],
                    checked_tasks=1
                )
        
        checked_scopes.append(scope_key)
        
        # 2. Check active task in scope
        task = self.task_repo.get_active_for_scope(scope_key)
        checked_tasks += 1
        if task:
            return ResolverResult(
                task=task,
                source=ResolverSource.ACTIVE_SCOPE,
                scope_key=scope_key,
                checked_scopes=checked_scopes,
                checked_tasks=checked_tasks
            )
        
        # 3. Check resumable task in scope
        task = self.task_repo.get_resumable_for_scope(scope_key)
        checked_tasks += 1
        if task:
            return ResolverResult(
                task=task,
                source=ResolverSource.RESUMABLE_SCOPE,
                scope_key=scope_key,
                checked_scopes=checked_scopes,
                checked_tasks=checked_tasks
            )
        
        # 4. Check recent incomplete tasks in scope
        tasks = self.task_repo.list_incomplete_for_scope(scope_key)
        checked_tasks += len(tasks)
        if tasks:
            # Return the most recent one
            return ResolverResult(
                task=tasks[0],
                source=ResolverSource.RECENT_SCOPE,
                scope_key=scope_key,
                checked_scopes=checked_scopes,
                checked_tasks=checked_tasks
            )
        
        # 5. No task found
        return ResolverResult(
            task=None,
            source=ResolverSource.NONE,
            scope_key=scope_key,
            error=self._build_no_task_message(intent, scope_key),
            checked_scopes=checked_scopes,
            checked_tasks=checked_tasks
        )
    
    def resolve_for_continue(self, ctx: CommandContext) -> ResolverResult:
        """
        Resolve task for 'continue' natural language intent.
        
        Args:
            ctx: Command context
        
        Returns:
            ResolverResult
        """
        return self.resolve(ctx, intent="continue")
    
    def resolve_for_resume(self, ctx: CommandContext, task_id: Optional[str] = None) -> ResolverResult:
        """
        Resolve task for '/resume' command.
        
        Args:
            ctx: Command context
            task_id: Optional explicit task ID
        
        Returns:
            ResolverResult
        """
        return self.resolve(ctx, explicit_task_id=task_id, intent="resume")
    
    def resolve_for_run(self, ctx: CommandContext, task_id: Optional[str] = None) -> ResolverResult:
        """
        Resolve task for '/run' command.
        
        Args:
            ctx: Command context
            task_id: Optional explicit task ID
        
        Returns:
            ResolverResult
        """
        return self.resolve(ctx, explicit_task_id=task_id, intent="run")
    
    def get_active_for_context(self, ctx: CommandContext) -> Optional[Task]:
        """
        Get active task for a context (for status checks).
        
        Args:
            ctx: Command context
        
        Returns:
            Active task if exists, None otherwise
        """
        scope_key = self._build_scope_key(ctx)
        return self.task_repo.get_active_for_scope(scope_key)
    
    def list_tasks_for_scope(self, scope_key: str, limit: int = 20) -> list:
        """
        List all tasks for a scope.
        
        Args:
            scope_key: Scope key to filter by
            limit: Maximum number of tasks to return
        
        Returns:
            List of tasks in the scope
        """
        # Get incomplete tasks first (more relevant)
        incomplete = self.task_repo.list_incomplete_for_scope(scope_key)
        
        # Get recent tasks (includes completed)
        recent = self.task_repo.list_recent_for_scope(scope_key, limit=limit)
        
        # Merge and deduplicate
        seen_ids = set()
        result = []
        
        for task in incomplete:
            if task.id not in seen_ids:
                seen_ids.add(task.id)
                result.append(task)
        
        for task in recent:
            if task.id not in seen_ids and len(result) < limit:
                seen_ids.add(task.id)
                result.append(task)
        
        return result[:limit]
    
    def _build_scope_key(self, ctx: CommandContext) -> str:
        """
        Build scope key from command context.
        
        Args:
            ctx: Command context
        
        Returns:
            Scope key string
        """
        chat_id = ctx.chat_id or "unknown"
        user_id = ctx.user_id or "unknown"
        return f"tg:{chat_id}:{user_id}"
    
    def _build_no_task_message(self, intent: str, scope_key: str) -> str:
        """
        Build error message when no task found.
        
        Args:
            intent: Operation intent
            scope_key: Scope that was checked
        
        Returns:
            Error message
        """
        if intent == "continue":
            return "📋 当前没有可继续的任务。\n\n你可以直接告诉我你需要做什么。"
        elif intent == "resume":
            return "📋 当前没有可恢复的任务。\n\n使用 /tasks 查看所有任务。"
        elif intent == "run":
            return "📋 当前没有活动任务。\n\n使用 /new 创建新任务。"
        else:
            return f"📋 当前没有任务。"


# Global resolver instance
_resolver: Optional[UnifiedTaskResolver] = None


def get_resolver() -> UnifiedTaskResolver:
    """Get or create global resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = UnifiedTaskResolver()
    return _resolver


def resolve_task_for_continue(ctx: CommandContext) -> ResolverResult:
    """Convenience function for continue resolution."""
    return get_resolver().resolve_for_continue(ctx)


def resolve_task_for_resume(ctx: CommandContext, task_id: Optional[str] = None) -> ResolverResult:
    """Convenience function for resume resolution."""
    return get_resolver().resolve_for_resume(ctx, task_id)


def resolve_task_for_run(ctx: CommandContext, task_id: Optional[str] = None) -> ResolverResult:
    """Convenience function for run resolution."""
    return get_resolver().resolve_for_run(ctx, task_id)
