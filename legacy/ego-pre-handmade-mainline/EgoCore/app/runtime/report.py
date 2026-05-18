"""
OpenEmotion Agent Runtime - Task Report Generator

Report generation with configurable LLM and prompt support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from app.storage.models import Task, TaskStatus, TaskStepStatus
from app.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """
    Task report generator with LLM support.
    
    Generates comprehensive reports using configurable prompts.
    Configuration loaded from llm.yaml and prompts.yaml.
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize report generator.
        
        Args:
            use_llm: Whether to use LLM for report generation
        """
        self.use_llm = use_llm
    
    async def generate(self, task: Task) -> str:
        """
        Generate a report for a task.
        
        Args:
            task: Task to generate report for
        
        Returns:
            Formatted report string
        """
        # Try LLM-based report first
        if self.use_llm:
            try:
                report = await self._llm_generate(task)
                if report:
                    return report
            except Exception as e:
                logger.warning(f"LLM report generation failed: {e}")
        
        # Fallback: template-based report
        return self._template_generate(task)
    
    async def _llm_generate(self, task: Task) -> Optional[str]:
        """
        Use LLM for report generation.
        
        Args:
            task: Task to generate report for
        
        Returns:
            Generated report or None if LLM not available
        """
        try:
            from app.llm_client import create_llm_client, get_prompt
        except ImportError:
            logger.debug("LLM client not available")
            return None
        
        try:
            # Get report prompt template
            prompt_template = get_prompt('report_prompt')
            
            # Format prompt with task data
            prompt = prompt_template.format(
                task_goal=task.objective,
                task_status=task.status.value,
                steps_completed=self._format_steps(task.steps),
                results=self._format_results(task.steps)
            )
            
            # Get system prompt
            system_prompt = get_prompt('system_main')
            
            # Create LLM client
            client = create_llm_client('reporting')
            
            # Call LLM
            response = await client.complete(prompt, system_prompt)
            
            # Wrap with header
            return self._wrap_report(task, response)
            
        except Exception as e:
            logger.error(f"LLM report generation error: {e}")
            return None
    
    def _template_generate(self, task: Task) -> str:
        """
        Generate report using template.
        
        Args:
            task: Task to generate report for
        
        Returns:
            Formatted report string
        """
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
    
    def _format_steps(self, steps: List[Any]) -> str:
        """Format steps for prompt."""
        if not steps:
            return "No steps defined."
        
        lines = []
        for i, step in enumerate(steps, 1):
            status = step.status.value if hasattr(step.status, 'value') else str(step.status)
            lines.append(f"{i}. {step.description} [{status}]")
        
        return "\n".join(lines)
    
    def _format_results(self, steps: List[Any]) -> str:
        """Format step results for prompt."""
        results = []
        for i, step in enumerate(steps, 1):
            if step.result:
                results.append(f"Step {i}: {step.result}")
            if step.error:
                results.append(f"Step {i} Error: {step.error}")
        
        if not results:
            return "No results yet."
        
        return "\n".join(results)
    
    def _wrap_report(self, task: Task, llm_content: str) -> str:
        """Wrap LLM-generated content with header."""
        lines = []
        lines.append(f"📊 *Task Report: {task.id}*")
        lines.append(f"📌 Status: {task.status.value.upper()}")
        lines.append("")
        lines.append(llm_content)
        return "\n".join(lines)


def create_report_generator(use_llm: bool = True) -> ReportGenerator:
    """
    Create a report generator instance.
    
    Args:
        use_llm: Whether to use LLM for report generation
    
    Returns:
        ReportGenerator instance
    """
    return ReportGenerator(use_llm=use_llm)


async def generate_task_report(task: Task, use_llm: bool = True) -> str:
    """
    Convenience function to generate a task report.
    
    Args:
        task: Task to generate report for
        use_llm: Whether to use LLM for report generation
    
    Returns:
        Formatted report string
    """
    generator = ReportGenerator(use_llm=use_llm)
    return await generator.generate(task)
