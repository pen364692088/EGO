"""
OpenEmotion Agent Runtime - Task Planner

Task decomposition planner with configurable LLM and prompt support.
"""

import re
from typing import List, Optional
from app.storage.models import Task, TaskStep
from app.logger import get_logger

logger = get_logger(__name__)


class TaskPlanner:
    """
    Task planner that decomposes objectives into steps.
    
    Supports two modes:
    1. LLM-based planning (when configured)
    2. Heuristic-based planning (fallback/default)
    
    Configuration is loaded from llm.yaml and prompts.yaml.
    """
    
    # Keywords that suggest multi-step tasks
    MULTI_STEP_KEYWORDS = [
        "and then", "after that", "followed by", "next",
        "first", "second", "third", "finally",
        "step by step", "步骤", "然后", "接着", "最后"
    ]
    
    # Delimiters for splitting steps
    STEP_DELIMITERS = [
        r'\n\d+\.\s*',      # Numbered lists (1. 2. 3.)
        r'\n[-•]\s*',       # Bullet points
        r'\n\*\s*',         # Asterisk bullets
        r'\s+->\s+',        # Arrow notation
        r'\s+=>\s+',        # Double arrow
        r'\s+then\s+',      # Then keyword
        r'。\s*',            # Chinese period
        r';\s*',            # Semicolon
    ]
    
    @classmethod
    def plan(cls, objective: str, memory_context: str = "", use_llm: bool = True) -> List[str]:
        """
        Decompose an objective into steps.
        
        Args:
            objective: Task objective/description
            memory_context: Context from memory (for LLM planning)
            use_llm: Whether to use LLM for planning (falls back to heuristics)
        
        Returns:
            List of step descriptions
        """
        if use_llm:
            try:
                steps = cls._llm_plan(objective, memory_context)
                if steps:
                    return steps
            except Exception as e:
                logger.warning(f"LLM planning failed, falling back to heuristics: {e}")
        
        # Fallback to heuristic planning
        return cls._heuristic_plan(objective)
    
    @classmethod
    def _llm_plan(cls, objective: str, memory_context: str = "") -> Optional[List[str]]:
        """
        Use LLM for task planning.
        
        Args:
            objective: Task objective
            memory_context: Context from memory
        
        Returns:
            List of steps or None if LLM not available
        """
        try:
            from app.llm_client import create_llm_client, get_prompt
        except ImportError:
            logger.debug("LLM client not available, using heuristic planning")
            return None
        
        try:
            # Get planner prompt template
            prompt_template = get_prompt('planner_prompt')
            
            # Format prompt with context
            prompt = prompt_template.format(
                task_goal=objective,
                memory_context=memory_context or "No relevant memory context available."
            )
            
            # Get system prompt
            system_prompt = get_prompt('system_main')
            
            # Create LLM client for planning
            client = create_llm_client('planning')
            
            # Call LLM (sync wrapper for async)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If already in async context, create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        client.complete(prompt, system_prompt)
                    )
                    response = future.result()
            else:
                response = loop.run_until_complete(
                    client.complete(prompt, system_prompt)
                )
            
            # Parse LLM response into steps
            steps = cls._parse_llm_response(response)
            
            if steps:
                logger.info(f"LLM planning generated {len(steps)} steps")
                return steps
            
        except Exception as e:
            logger.error(f"LLM planning error: {e}")
        
        return None
    
    @classmethod
    def _parse_llm_response(cls, response: str) -> List[str]:
        """
        Parse LLM response into step list.
        
        Args:
            response: Raw LLM response
        
        Returns:
            List of step descriptions
        """
        # Try numbered list pattern
        numbered = cls._try_numbered_list(response)
        if numbered:
            return numbered
        
        # Try bullet points
        bullets = cls._try_bullet_list(response)
        if bullets:
            return bullets
        
        # Try line separation
        lines = cls._try_line_separation(response)
        if lines and len(lines) > 1:
            return lines
        
        # Fallback: treat entire response as single step
        if response.strip():
            return [response.strip()]
        
        return []
    
    @classmethod
    def _heuristic_plan(cls, objective: str) -> List[str]:
        """
        Decompose objective using heuristics.
        
        Args:
            objective: Task objective
        
        Returns:
            List of step descriptions
        """
        # Check if objective contains multi-step indicators
        if cls._is_multi_step(objective):
            steps = cls._decompose(objective)
        else:
            # Single-step task
            steps = [objective]
        
        return steps
    
    @classmethod
    def create_steps(cls, task: Task, memory_context: str = "", use_llm: bool = True) -> List[TaskStep]:
        """
        Create task steps from planning.
        
        Args:
            task: Task to create steps for
            memory_context: Context from memory
            use_llm: Whether to use LLM for planning
        
        Returns:
            List of TaskStep objects
        """
        step_descriptions = cls.plan(task.objective, memory_context, use_llm)
        steps = []
        
        for i, desc in enumerate(step_descriptions):
            step = TaskStep.create(
                task_id=task.id,
                description=desc.strip(),
                order=i
            )
            steps.append(step)
        
        return steps
    
    @classmethod
    def _is_multi_step(cls, objective: str) -> bool:
        """
        Check if objective suggests multiple steps.
        
        Args:
            objective: Task objective
        
        Returns:
            True if multi-step indicators found
        """
        objective_lower = objective.lower()
        
        # Check for multi-step keywords
        for keyword in cls.MULTI_STEP_KEYWORDS:
            if keyword.lower() in objective_lower:
                return True
        
        # Check for numbered lists
        if re.search(r'\d+\.\s+\w', objective):
            return True
        
        # Check for bullet points
        if re.search(r'[-•*]\s+\w', objective):
            return True
        
        # Check for newlines (suggests multiple items)
        if objective.count('\n') >= 1:
            return True
        
        return False
    
    @classmethod
    def _decompose(cls, objective: str) -> List[str]:
        """
        Decompose objective into steps using various strategies.
        
        Args:
            objective: Task objective
        
        Returns:
            List of step descriptions
        """
        steps = []
        
        # Try numbered list pattern first
        numbered = cls._try_numbered_list(objective)
        if numbered:
            return numbered
        
        # Try bullet points
        bullets = cls._try_bullet_list(objective)
        if bullets:
            return bullets
        
        # Try newline separation
        lines = cls._try_line_separation(objective)
        if lines:
            return lines
        
        # Try keyword-based splitting
        keyword_steps = cls._try_keyword_split(objective)
        if keyword_steps:
            return keyword_steps
        
        # Fallback: single step
        return [objective]
    
    @classmethod
    def _try_numbered_list(cls, text: str) -> Optional[List[str]]:
        """Try to extract numbered list items."""
        pattern = r'\d+\.\s*(.+?)(?=\n\d+\.|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            return [m.strip() for m in matches if m.strip()]
        return None
    
    @classmethod
    def _try_bullet_list(cls, text: str) -> Optional[List[str]]:
        """Try to extract bullet list items."""
        pattern = r'[-•*]\s*(.+?)(?=\n[-•*]|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            return [m.strip() for m in matches if m.strip()]
        return None
    
    @classmethod
    def _try_line_separation(cls, text: str) -> Optional[List[str]]:
        """Try to split by newlines."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(lines) > 1:
            return lines
        return None
    
    @classmethod
    def _try_keyword_split(cls, text: str) -> Optional[List[str]]:
        """Try to split by multi-step keywords."""
        for keyword in cls.MULTI_STEP_KEYWORDS:
            if keyword.lower() in text.lower():
                parts = re.split(re.escape(keyword), text, flags=re.IGNORECASE)
                if len(parts) > 1:
                    return [p.strip() for p in parts if p.strip()]
        return None


def plan_task(objective: str, memory_context: str = "", use_llm: bool = True) -> List[str]:
    """
    Convenience function to plan a task.
    
    Args:
        objective: Task objective
        memory_context: Context from memory
        use_llm: Whether to use LLM for planning
    
    Returns:
        List of step descriptions
    """
    return TaskPlanner.plan(objective, memory_context, use_llm)


def create_task_steps(task: Task, memory_context: str = "", use_llm: bool = True) -> List[TaskStep]:
    """
    Convenience function to create steps for a task.
    
    Args:
        task: Task to create steps for
        memory_context: Context from memory
        use_llm: Whether to use LLM for planning
    
    Returns:
        List of TaskStep objects
    """
    return TaskPlanner.create_steps(task, memory_context, use_llm)
