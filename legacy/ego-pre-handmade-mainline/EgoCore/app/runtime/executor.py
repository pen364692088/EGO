"""
OpenEmotion Agent Runtime - Task Executor

Step execution with configurable LLM and prompt support.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from app.storage.models import TaskStep
from app.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of step execution."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    tool_used: Optional[str] = None
    tool_result: Optional[Any] = None


class StepExecutor:
    """
    Task step executor with LLM support.
    
    Executes steps using available tools and LLM for decision-making.
    Configuration loaded from llm.yaml and prompts.yaml.
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize step executor.
        
        Args:
            use_llm: Whether to use LLM for execution decisions
        """
        self.use_llm = use_llm
        self._tool_registry = None
    
    def _get_tool_registry(self):
        """Get tool registry instance."""
        if self._tool_registry is None:
            from app.tools import ToolRegistry
            self._tool_registry = ToolRegistry()
        return self._tool_registry
    
    async def execute(self, step: TaskStep, task_context: Dict[str, Any]) -> ExecutionResult:
        """
        Execute a task step.
        
        Args:
            step: TaskStep to execute
            task_context: Task context (goal, previous steps, etc.)
        
        Returns:
            ExecutionResult with outcome
        """
        logger.info(f"Executing step: {step.description}")
        
        # Try LLM-based execution first
        if self.use_llm:
            try:
                result = await self._llm_execute(step, task_context)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM execution failed: {e}")
        
        # Fallback: try tool-based execution
        return await self._tool_execute(step, task_context)
    
    async def _llm_execute(self, step: TaskStep, task_context: Dict[str, Any]) -> Optional[ExecutionResult]:
        """
        Use LLM for step execution.
        
        Args:
            step: TaskStep to execute
            task_context: Task context
        
        Returns:
            ExecutionResult or None if LLM not available
        """
        try:
            from app.llm_client import create_llm_client, get_prompt
        except ImportError:
            logger.debug("LLM client not available")
            return None
        
        try:
            # Get executor prompt template
            prompt_template = get_prompt('executor_prompt')
            
            # Build previous steps summary
            previous_steps = self._format_previous_steps(
                task_context.get('previous_steps', [])
            )
            
            # Format prompt
            prompt = prompt_template.format(
                task_goal=task_context.get('goal', 'Unknown task'),
                current_step=step.description,
                step_number=task_context.get('step_number', 1),
                total_steps=task_context.get('total_steps', 1),
                previous_steps=previous_steps,
                available_tools=self._get_available_tools_description()
            )
            
            # Get system prompt
            system_prompt = get_prompt('system_main')
            
            # Create LLM client
            client = create_llm_client('execution')
            
            # Call LLM
            response = await client.complete(prompt, system_prompt)
            
            # Parse response for tool commands
            tool_result = await self._parse_and_execute_tools(response)
            
            return ExecutionResult(
                success=True,
                output=response,
                tool_used=tool_result.get('tool'),
                tool_result=tool_result.get('result')
            )
            
        except Exception as e:
            logger.error(f"LLM execution error: {e}")
            return None
    
    async def _tool_execute(self, step: TaskStep, task_context: Dict[str, Any]) -> ExecutionResult:
        """
        Execute step using tools directly.
        
        Args:
            step: TaskStep to execute
            task_context: Task context
        
        Returns:
            ExecutionResult
        """
        try:
            registry = self._get_tool_registry()
            
            # Try to match step to available tools
            tool_match = self._match_step_to_tool(step.description)
            
            if tool_match:
                tool_name, params = tool_match
                tool = registry.get_tool(tool_name)
                
                if tool:
                    result = await tool.execute(**params)
                    
                    return ExecutionResult(
                        success=result.get('success', False),
                        output=result.get('output'),
                        error=result.get('error'),
                        tool_used=tool_name,
                        tool_result=result
                    )
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ExecutionResult(
                success=False,
                error=str(e)
            )
        
        # Fallback: simulated execution
        return ExecutionResult(
            success=True,
            output=f"[Simulated] Step completed: {step.description}"
        )
    
    def _format_previous_steps(self, steps: List[Dict[str, Any]]) -> str:
        """Format previous steps for prompt."""
        if not steps:
            return "No previous steps completed."
        
        lines = []
        for i, step in enumerate(steps, 1):
            status = step.get('status', 'unknown')
            result = step.get('result', 'No result')
            lines.append(f"{i}. {step.get('description', 'Unknown')} [{status}]")
            if result:
                lines.append(f"   Result: {str(result)[:200]}")
        
        return "\n".join(lines)
    
    def _get_available_tools_description(self) -> str:
        """Get description of available tools."""
        try:
            registry = self._get_tool_registry()
            tools = registry.list_tools()
            
            if not tools:
                return "No tools available."
            
            descriptions = []
            for name, info in tools.items():
                descriptions.append(f"- {name}: {info.get('description', 'No description')}")
            
            return "\n".join(descriptions)
        except Exception:
            return "Tools: file, shell, python"
    
    def _match_step_to_tool(self, step_description: str) -> Optional[tuple]:
        """
        Match step description to a tool.
        
        Args:
            step_description: Step description text
        
        Returns:
            Tuple of (tool_name, params) or None
        """
        step_lower = step_description.lower()
        
        # File operations
        if 'read file' in step_lower or 'open file' in step_lower:
            import re
            match = re.search(r'["\']([^"\']+)["\']', step_description)
            if match:
                return ('file', {'action': 'read', 'path': match.group(1)})
        
        if 'write file' in step_lower or 'create file' in step_lower:
            import re
            match = re.search(r'["\']([^"\']+)["\']', step_description)
            if match:
                return ('file', {'action': 'write', 'path': match.group(1)})
        
        # Shell commands
        if 'run' in step_lower or 'execute' in step_lower:
            import re
            match = re.search(r'["\']([^"\']+)["\']', step_description)
            if match:
                return ('shell', {'command': match.group(1)})
        
        # Python code
        if 'python' in step_lower or 'calculate' in step_lower:
            return ('python', {'code': step_description})
        
        return None
    
    async def _parse_and_execute_tools(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response for tool commands and execute.
        
        Args:
            llm_response: LLM response text
        
        Returns:
            Dict with tool name and result
        """
        # Look for tool command patterns
        # Format: [TOOL: tool_name] params... [/TOOL]
        import re
        
        tool_pattern = r'\[TOOL:\s*(\w+)\](.*?)\[/TOOL\]'
        matches = re.findall(tool_pattern, llm_response, re.DOTALL)
        
        if not matches:
            return {'tool': None, 'result': None}
        
        results = []
        try:
            registry = self._get_tool_registry()
            
            for tool_name, params_str in matches:
                tool = registry.get_tool(tool_name)
                if tool:
                    # Try to parse params as JSON or use as string
                    try:
                        import json
                        params = json.loads(params_str.strip())
                    except json.JSONDecodeError:
                        params = {'input': params_str.strip()}
                    
                    result = await tool.execute(**params)
                    results.append({
                        'tool': tool_name,
                        'result': result
                    })
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
        
        return results[0] if results else {'tool': None, 'result': None}


def create_executor(use_llm: bool = True) -> StepExecutor:
    """
    Create a step executor instance.
    
    Args:
        use_llm: Whether to use LLM for execution
    
    Returns:
        StepExecutor instance
    """
    return StepExecutor(use_llm=use_llm)
