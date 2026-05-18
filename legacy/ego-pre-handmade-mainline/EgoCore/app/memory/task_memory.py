"""
OpenEmotion Agent Runtime - Task Memory

Handles task goals, progress, failures, and next steps.
This is the MOST IMPORTANT memory type for task continuity.
Enables /resume to pick up where work left off.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from app.memory.memory_manager import (
    MemoryManager, MemoryEntry, MemoryType, get_memory_manager
)


class TaskMemory:
    """
    Handler for task memory.
    
    Task memory contains:
    - Task objective and goals
    - Current progress summary
    - Completed steps
    - Failed steps and errors
    - Next steps to take
    - Key decisions made during task
    
    This is CRITICAL for task continuity:
    - Enables /resume to continue work
    - Prevents repeating completed work
    - Tracks failures to avoid retrying same mistakes
    - Provides context for next session
    
    These memories have:
    - Short TTL (30 days)
    - Highest injection priority for resume
    - Stored in SQLite for fast retrieval
    """
    
    # Task memory keys
    TASK_OBJECTIVE = "objective"
    TASK_PROGRESS = "progress"
    TASK_NEXT_STEPS = "next_steps"
    TASK_FAILURES = "failures"
    TASK_DECISIONS = "decisions"
    
    def __init__(self, manager: Optional[MemoryManager] = None):
        """
        Initialize task memory handler.
        
        Args:
            manager: Memory manager instance
        """
        self._manager = manager or get_memory_manager()
    
    def save_task_memory(self,
                        task_id: str,
                        objective: str,
                        status: str,
                        progress: str,
                        next_steps: List[str],
                        failures: Optional[List[str]] = None,
                        decisions: Optional[List[str]] = None,
                        completed_steps: Optional[List[str]] = None,
                        current_step: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """
        Save task memory entry.
        
        This should be called:
        - After each step completion
        - When task is paused
        - When task fails/blocks
        - Before session ends
        
        Args:
            task_id: Task identifier
            objective: Task objective
            status: Current task status
            progress: Progress summary (human-readable)
            next_steps: List of next steps to take
            failures: List of failures/blockers encountered
            decisions: List of key decisions made
            completed_steps: List of completed step descriptions
            current_step: Current step being executed
            context: Additional context data
        
        Returns:
            Created/updated memory entry
        """
        # Check if memory already exists for this task
        existing = self.get_task_memory(task_id)
        
        metadata = {
            'task_id': task_id,
            'status': status,
            'next_steps': next_steps,
            'failures': failures or [],
            'decisions': decisions or [],
            'completed_steps': completed_steps or [],
            'current_step': current_step,
            'context': context or {}
        }
        
        # Build comprehensive content
        content_parts = [
            f"Task: {objective}",
            f"Status: {status}",
            f"Progress: {progress}"
        ]
        
        if current_step:
            content_parts.append(f"Current Step: {current_step}")
        
        if next_steps:
            content_parts.append("Next Steps:")
            for i, step in enumerate(next_steps, 1):
                content_parts.append(f"  {i}. {step}")
        
        if failures:
            content_parts.append("Failures/Blockers:")
            for f in failures:
                content_parts.append(f"  - {f}")
        
        content = "\n".join(content_parts)
        
        if existing:
            # Update existing entry
            existing.content = content
            existing.updated_at = datetime.now()
            existing.metadata.update(metadata)
            return self._manager.write(existing)
        else:
            # Create new entry directly
            import uuid
            entry = MemoryEntry(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                type=MemoryType.TASK,
                key=f"task:{task_id}",
                content=content,
                metadata=metadata
            )
            return self._manager.write(entry)
    
    def get_task_memory(self, task_id: str) -> Optional[MemoryEntry]:
        """
        Get memory for a specific task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task memory entry if found
        """
        # Use get_by_key instead of search
        return self._manager.get_by_key(f"task:{task_id}", MemoryType.TASK)
    
    def get_latest_task_memory(self) -> Optional[MemoryEntry]:
        """
        Get the most recent task memory.
        
        This is used by /resume when no specific task_id is provided.
        
        Returns:
            Latest task memory entry
        """
        return self._manager.get_latest_task_memory()
    
    def update_progress(self, task_id: str, progress: str,
                       status: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Update task progress.
        
        Args:
            task_id: Task identifier
            progress: New progress summary
            status: Optional status update
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            # Update content with new progress
            lines = task_mem.content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith("Progress:"):
                    new_lines.append(f"Progress: {progress}")
                else:
                    new_lines.append(line)
            
            task_mem.content = "\n".join(new_lines)
            task_mem.updated_at = datetime.now()
            
            if status:
                task_mem.metadata['status'] = status
            
            return self._manager.write(task_mem)
        
        return None
    
    def add_next_step(self, task_id: str, step: str) -> Optional[MemoryEntry]:
        """
        Add a next step to the task.
        
        Args:
            task_id: Task identifier
            step: Step description to add
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            next_steps = task_mem.metadata.get('next_steps', [])
            if step not in next_steps:
                next_steps.append(step)
                task_mem.metadata['next_steps'] = next_steps
                task_mem.updated_at = datetime.now()
                return self._manager.write(task_mem)
        
        return None
    
    def remove_next_step(self, task_id: str, step: str) -> Optional[MemoryEntry]:
        """
        Remove a next step (when completed).
        
        Args:
            task_id: Task identifier
            step: Step description to remove
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            next_steps = task_mem.metadata.get('next_steps', [])
            completed_steps = task_mem.metadata.get('completed_steps', [])
            
            if step in next_steps:
                next_steps.remove(step)
                completed_steps.append(step)
                
                task_mem.metadata['next_steps'] = next_steps
                task_mem.metadata['completed_steps'] = completed_steps
                task_mem.updated_at = datetime.now()
                return self._manager.write(task_mem)
        
        return None
    
    def record_failure(self, task_id: str, failure: str,
                      step: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Record a failure/blocker.
        
        This is critical for avoiding repeated mistakes.
        
        Args:
            task_id: Task identifier
            failure: Failure description
            step: Optional step that failed
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            failures = task_mem.metadata.get('failures', [])
            
            failure_entry = failure
            if step:
                failure_entry = f"[{step}] {failure}"
            
            if failure_entry not in failures:
                failures.append(failure_entry)
                task_mem.metadata['failures'] = failures
                task_mem.updated_at = datetime.now()
                return self._manager.write(task_mem)
        
        return None
    
    def record_decision(self, task_id: str, decision: str) -> Optional[MemoryEntry]:
        """
        Record a key decision made during task.
        
        Args:
            task_id: Task identifier
            decision: Decision description
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            decisions = task_mem.metadata.get('decisions', [])
            if decision not in decisions:
                decisions.append(decision)
                task_mem.metadata['decisions'] = decisions
                task_mem.updated_at = datetime.now()
                return self._manager.write(task_mem)
        
        return None
    
    def mark_completed(self, task_id: str, summary: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Mark task as completed.
        
        Args:
            task_id: Task identifier
            summary: Optional completion summary
        
        Returns:
            Updated memory entry
        """
        task_mem = self.get_task_memory(task_id)
        
        if task_mem:
            task_mem.metadata['status'] = 'completed'
            task_mem.metadata['next_steps'] = []
            
            if summary:
                task_mem.content = f"{task_mem.content}\n\nCompleted: {summary}"
            
            task_mem.updated_at = datetime.now()
            return self._manager.write(task_mem)
        
        return None
    
    def build_resume_context(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build comprehensive context for /resume.
        
        This is the KEY function for task continuity.
        
        Args:
            task_id: Specific task to resume (uses latest if not provided)
        
        Returns:
            Dict with all resume context
        """
        if task_id:
            task_mem = self.get_task_memory(task_id)
        else:
            task_mem = self.get_latest_task_memory()
        
        if not task_mem:
            return {
                'has_memory': False,
                'message': 'No task memory found. Starting fresh.'
            }
        
        metadata = task_mem.metadata
        
        resume_context = {
            'has_memory': True,
            'task_id': metadata.get('task_id'),
            'objective': None,
            'status': metadata.get('status'),
            'progress': None,
            'current_step': metadata.get('current_step'),
            'next_steps': metadata.get('next_steps', []),
            'failures': metadata.get('failures', []),
            'decisions': metadata.get('decisions', []),
            'completed_steps': metadata.get('completed_steps', []),
            'context': metadata.get('context', {}),
            'created_at': task_mem.created_at.isoformat(),
            'updated_at': task_mem.updated_at.isoformat()
        }
        
        # Parse content for objective and progress
        lines = task_mem.content.split('\n')
        for line in lines:
            if line.startswith("Task:"):
                resume_context['objective'] = line.replace("Task:", "").strip()
            elif line.startswith("Progress:"):
                resume_context['progress'] = line.replace("Progress:", "").strip()
        
        return resume_context
    
    def build_context_string(self, task_id: Optional[str] = None) -> str:
        """
        Build context string for injection into prompts.
        
        Args:
            task_id: Specific task to include
        
        Returns:
            Formatted string of task context
        """
        resume_ctx = self.build_resume_context(task_id)
        
        if not resume_ctx.get('has_memory'):
            return ""
        
        lines = ["## Task Memory (Resume Context)"]
        
        # Objective
        if resume_ctx.get('objective'):
            lines.append(f"**Objective:** {resume_ctx['objective']}")
        
        # Status
        if resume_ctx.get('status'):
            lines.append(f"**Status:** {resume_ctx['status']}")
        
        # Progress
        if resume_ctx.get('progress'):
            lines.append(f"**Progress:** {resume_ctx['progress']}")
        
        # Current step
        if resume_ctx.get('current_step'):
            lines.append(f"**Current Step:** {resume_ctx['current_step']}")
        
        # Next steps
        next_steps = resume_ctx.get('next_steps', [])
        if next_steps:
            lines.append("")
            lines.append("### Next Steps")
            for i, step in enumerate(next_steps, 1):
                lines.append(f"{i}. {step}")
        
        # Completed steps
        completed = resume_ctx.get('completed_steps', [])
        if completed:
            lines.append("")
            lines.append("### Completed Steps")
            for step in completed:
                lines.append(f"- ✅ {step}")
        
        # Failures to avoid
        failures = resume_ctx.get('failures', [])
        if failures:
            lines.append("")
            lines.append("### ⚠️ Previous Failures (Avoid Repeating)")
            for f in failures:
                lines.append(f"- {f}")
        
        # Decisions made
        decisions = resume_ctx.get('decisions', [])
        if decisions:
            lines.append("")
            lines.append("### Key Decisions Made")
            for d in decisions:
                lines.append(f"- {d}")
        
        lines.append("")
        lines.append(f"_Last updated: {resume_ctx.get('updated_at', 'unknown')}_")
        
        return "\n".join(lines)


def get_task_handler() -> TaskMemory:
    """Get task memory handler instance."""
    return TaskMemory()
