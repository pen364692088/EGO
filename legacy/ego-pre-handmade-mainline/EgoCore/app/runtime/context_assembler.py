"""
ContextAssembler - 执行上下文组装器

职责:
- 从 session/task/project/runtime 组装统一执行上下文
- 保证执行前上下文完整注入
- 没有上下文不允许直接规划或宣称完成

版本: v1.0.0
Created: 2026-03-19
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

from app.risk_signal import assess_message_risk_level

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    turn_index: int
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    user_id: Optional[str] = None
    chat_id: Optional[str] = None


@dataclass
class TaskContext:
    """任务上下文"""
    active_task_id: Optional[str] = None
    task_goal: Optional[str] = None
    task_status: Optional[str] = None
    current_step_index: int = 0
    total_steps: int = 0
    previous_steps: List[Dict[str, Any]] = field(default_factory=list)
    task_memory: Optional[Dict[str, Any]] = None


@dataclass
class RuntimeSummary:
    """运行时摘要"""
    emotiond_available: bool = False
    llm_provider: Optional[str] = None
    tools_available: List[str] = field(default_factory=list)
    degraded_mode: bool = False


@dataclass
class ProjectMemory:
    """项目记忆"""
    project_name: Optional[str] = None
    key_files: List[str] = field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class SafetyContext:
    """安全上下文"""
    risk_level: str = "low"
    requires_approval: bool = False
    approval_reason: Optional[str] = None
    blocked_operations: List[str] = field(default_factory=list)


@dataclass
class RepairContext:
    """修复上下文"""
    has_pending_repair: bool = False
    failed_task_id: Optional[str] = None
    failure_reason: Optional[str] = None
    user_feedback: Optional[str] = None
    retry_count: int = 0
    last_attempt: Optional[datetime] = None


@dataclass
class ExecutionContext:
    """完整执行上下文"""
    conversation_context: ConversationContext
    task_context: TaskContext
    runtime_summary: RuntimeSummary
    project_memory: ProjectMemory
    safety_context: SafetyContext
    repair_context: RepairContext
    
    # 执行追踪
    target_path: Optional[str] = None
    expected_side_effect: Optional[str] = None
    tool_capability: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "conversation_context": {
                "session_id": self.conversation_context.session_id,
                "turn_index": self.conversation_context.turn_index,
                "recent_messages": self.conversation_context.recent_messages[-5:],
                "user_id": self.conversation_context.user_id,
            },
            "task_context": {
                "active_task_id": self.task_context.active_task_id,
                "task_goal": self.task_context.task_goal,
                "task_status": self.task_context.task_status,
                "current_step_index": self.task_context.current_step_index,
                "total_steps": self.task_context.total_steps,
                "has_task": self.task_context.active_task_id is not None,
            },
            "runtime_summary": {
                "emotiond_available": self.runtime_summary.emotiond_available,
                "llm_provider": self.runtime_summary.llm_provider,
                "tools_available": self.runtime_summary.tools_available[:5],
                "degraded_mode": self.runtime_summary.degraded_mode,
            },
            "project_memory": {
                "project_name": self.project_memory.project_name,
                "key_files": self.project_memory.key_files[:5],
                "constraints": self.project_memory.constraints[:3],
            },
            "safety_context": {
                "risk_level": self.safety_context.risk_level,
                "requires_approval": self.safety_context.requires_approval,
            },
            "repair_context": {
                "has_pending_repair": self.repair_context.has_pending_repair,
                "failed_task_id": self.repair_context.failed_task_id,
                "failure_reason": self.repair_context.failure_reason,
            },
            "execution_tracking": {
                "target_path": self.target_path,
                "expected_side_effect": self.expected_side_effect,
                "tool_capability": self.tool_capability,
            },
        }


class ContextAssembler:
    """
    执行上下文组装器
    
    强制规则:
    - 所有执行必须经过 ContextAssembler
    - 没有上下文不允许直接规划或宣称完成
    - repair_context 必须追踪失败任务
    """
    
    def __init__(
        self,
        session_store=None,
        task_runtime=None,
        project_memory_store=None,
        repair_manager=None,
    ):
        self._session_store = session_store
        self._task_runtime = task_runtime
        self._project_memory_store = project_memory_store
        self._repair_manager = repair_manager
    
    def assemble(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
        chat_id: Optional[str] = None,
        active_task: Optional[Dict[str, Any]] = None,
    ) -> ExecutionContext:
        """
        组装完整执行上下文
        
        Args:
            user_input: 用户输入
            session_id: 会话 ID
            user_id: 用户 ID
            chat_id: 聊天 ID
            active_task: 活动任务
        
        Returns:
            ExecutionContext 完整上下文
        """
        # 1. 组装对话上下文
        conversation_ctx = self._assemble_conversation(
            session_id=session_id,
            user_id=user_id,
            chat_id=chat_id,
        )
        
        # 2. 组装任务上下文
        task_ctx = self._assemble_task(active_task)
        
        # 3. 组装运行时摘要
        runtime_summary = self._assemble_runtime()
        
        # 4. 组装项目记忆
        project_memory = self._assemble_project_memory()
        
        # 5. 组装安全上下文
        safety_ctx = self._assemble_safety(user_input, task_ctx)
        
        # 6. 组装修复上下文
        repair_ctx = self._assemble_repair(session_id, user_id)
        
        # 7. 提取执行追踪信息
        target_path, expected_side_effect, tool_capability = self._extract_execution_tracking(
            user_input, task_ctx, active_task
        )
        
        context = ExecutionContext(
            conversation_context=conversation_ctx,
            task_context=task_ctx,
            runtime_summary=runtime_summary,
            project_memory=project_memory,
            safety_context=safety_ctx,
            repair_context=repair_ctx,
            target_path=target_path,
            expected_side_effect=expected_side_effect,
            tool_capability=tool_capability,
        )
        
        logger.info(
            f"ContextAssembler: session={session_id}, "
            f"has_task={task_ctx.active_task_id is not None}, "
            f"repair_needed={repair_ctx.has_pending_repair}"
        )
        
        return context
    
    def _assemble_conversation(
        self,
        session_id: str,
        user_id: str,
        chat_id: Optional[str],
    ) -> ConversationContext:
        """组装对话上下文"""
        recent_messages = []
        turn_index = 0
        
        if self._session_store:
            try:
                turn_index = self._session_store.get_turn_index(session_id)
                recent_messages = self._session_store.get_recent_turns(session_id, limit=5)
            except Exception as e:
                logger.warning(f"Failed to get session context: {e}")
        
        return ConversationContext(
            session_id=session_id,
            turn_index=turn_index,
            recent_messages=recent_messages,
            user_id=user_id,
            chat_id=chat_id,
        )
    
    def _assemble_task(self, active_task: Optional[Dict[str, Any]]) -> TaskContext:
        """组装任务上下文"""
        if not active_task:
            return TaskContext()
        
        return TaskContext(
            active_task_id=active_task.get("task_id"),
            task_goal=active_task.get("goal"),
            task_status=active_task.get("status"),
            current_step_index=active_task.get("current_step", 0),
            total_steps=active_task.get("total_steps", 0),
            previous_steps=active_task.get("previous_steps", []),
            task_memory=active_task.get("memory"),
        )
    
    def _assemble_runtime(self) -> RuntimeSummary:
        """组装运行时摘要"""
        emotiond_available = False
        llm_provider = None
        tools_available = []
        degraded_mode = False
        
        # 检查 emotiond
        try:
            import httpx
            resp = httpx.get("http://localhost:18080/health", timeout=1.0)
            emotiond_available = resp.status_code == 200
        except Exception:
            emotiond_available = False
        
        # 获取 LLM 配置
        try:
            from app.config import get_config
            config = get_config()
            llm_provider = config.llm.default_provider
        except Exception:
            pass
        
        # 获取可用工具
        try:
            from app.tools import get_registry
            registry = get_registry()
            tools_available = list(registry.list_tools().keys())[:5]
        except Exception:
            tools_available = ["file", "shell"]
        
        degraded_mode = not emotiond_available
        
        return RuntimeSummary(
            emotiond_available=emotiond_available,
            llm_provider=llm_provider,
            tools_available=tools_available,
            degraded_mode=degraded_mode,
        )
    
    def _assemble_project_memory(self) -> ProjectMemory:
        """组装项目记忆"""
        if not self._project_memory_store:
            return ProjectMemory()
        
        try:
            # 从项目记忆存储获取
            memory = self._project_memory_store.get_recent()
            return ProjectMemory(
                project_name=memory.get("project_name"),
                key_files=memory.get("key_files", []),
                recent_changes=memory.get("recent_changes", []),
                constraints=memory.get("constraints", []),
            )
        except Exception as e:
            logger.warning(f"Failed to get project memory: {e}")
            return ProjectMemory()
    
    def _assemble_safety(
        self,
        user_input: str,
        task_ctx: TaskContext,
    ) -> SafetyContext:
        """组装安全上下文"""
        risk_level = assess_message_risk_level(user_input)
        requires_approval = False
        approval_reason = None
        blocked_operations = []

        if risk_level in {"high", "critical"}:
            requires_approval = True
            approval_reason = f"检测到高风险操作: {risk_level}"
        
        return SafetyContext(
            risk_level=risk_level,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            blocked_operations=blocked_operations,
        )
    
    def _assemble_repair(self, session_id: str, user_id: str) -> RepairContext:
        """组装修复上下文"""
        if not self._repair_manager:
            return RepairContext()
        
        try:
            repair_info = self._repair_manager.get_pending_repair(session_id, user_id)
            if repair_info:
                return RepairContext(
                    has_pending_repair=True,
                    failed_task_id=repair_info.get("task_id"),
                    failure_reason=repair_info.get("failure_reason"),
                    user_feedback=repair_info.get("user_feedback"),
                    retry_count=repair_info.get("retry_count", 0),
                    last_attempt=repair_info.get("last_attempt"),
                )
        except Exception as e:
            logger.warning(f"Failed to get repair context: {e}")
        
        return RepairContext()
    
    def _extract_execution_tracking(
        self,
        user_input: str,
        task_ctx: TaskContext,
        active_task: Optional[Dict[str, Any]],
    ) -> tuple:
        """提取执行追踪信息"""
        import re
        
        target_path = None
        expected_side_effect = None
        tool_capability = None
        
        # 提取路径
        path_patterns = [
            r'["\']([/\w\-\.]+)["\']',  # 引号中的路径
            r'在\s+([/\w\-\.]+)',  # 中文: "在 /path"
            r'(?:create|write|read|open)\s+([/\w\-\.]+)',  # 英文操作
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, user_input)
            if match:
                target_path = match.group(1)
                break
        
        # 确定期望副作用
        if "创建" in user_input or "create" in user_input.lower():
            expected_side_effect = "file_created"
            tool_capability = "file_write"
        elif "写入" in user_input or "write" in user_input.lower():
            expected_side_effect = "file_written"
            tool_capability = "file_write"
        elif "读取" in user_input or "read" in user_input.lower():
            expected_side_effect = "file_read"
            tool_capability = "file_read"
        elif "运行" in user_input or "run" in user_input.lower():
            expected_side_effect = "command_executed"
            tool_capability = "shell"
        elif "git" in user_input.lower():
            expected_side_effect = "git_operation"
            tool_capability = "git"
        
        return target_path, expected_side_effect, tool_capability


# 全局实例
_assembler: Optional[ContextAssembler] = None


def get_context_assembler() -> ContextAssembler:
    """获取全局上下文组装器"""
    global _assembler
    if _assembler is None:
        from app.interaction.session_context_store import get_session_context_store
        _assembler = ContextAssembler(
            session_store=get_session_context_store(),
        )
    return _assembler


def assemble_execution_context(
    user_input: str,
    session_id: str,
    user_id: str,
    chat_id: Optional[str] = None,
    active_task: Optional[Dict[str, Any]] = None,
) -> ExecutionContext:
    """
    便捷函数：组装执行上下文
    
    Args:
        user_input: 用户输入
        session_id: 会话 ID
        user_id: 用户 ID
        chat_id: 聊天 ID
        active_task: 活动任务
    
    Returns:
        ExecutionContext
    """
    return get_context_assembler().assemble(
        user_input=user_input,
        session_id=session_id,
        user_id=user_id,
        chat_id=chat_id,
        active_task=active_task,
    )
