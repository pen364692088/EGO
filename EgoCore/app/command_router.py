"""
OpenEmotion Agent Runtime - Command Router

Handles routing of Telegram commands to appropriate handlers.
Integrated with TaskRuntime for Phase 3.
"""

from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass

from app.runtime.task_runtime import TaskRuntime, get_runtime
from app.storage.models import TaskStatus
from app.integrations.openemotion.reply_injection import maybe_inject_plan
from app.integrations.openemotion.injection_metrics import (
    record_injection_attempt,
    record_injection_allowed,
    record_injection_fallback,
    record_injection_skipped,
)
from app.integrations.openemotion.event_mirror import get_event_mirror

# EgoCore Metrics Integration (Phase: PRODUCTION_INTEGRATION)
# Feature Flag: runtime_metrics_enabled (default: OFF)
# Protection: fast_disable / rollback / timeout / circuit_breaker / exception isolation
try:
    from system_core import record_metric
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

import logging

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """Context passed to command handlers."""
    chat_id: int
    user_id: int
    username: Optional[str]
    args: str  # Arguments after the command
    message_text: str  # Full message text


@dataclass
class CommandResult:
    """Result from command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CommandRouter:
    """
    Routes Telegram commands to their handlers.

    Commands:
    - /start: Initialize bot interaction
    - /new: Create a new task
    - /status: Check current task status
    - /tasks: List all tasks
    - /resume: Resume a paused task
    - /pause: Pause current task
    - /retry: Retry last failed step
    - /abort: Abort current task
    - /report: Generate task report
    - /run: Execute next step
    - /memory: View memory summary
    """

    def __init__(self, runtime: Optional[TaskRuntime] = None):
        """
        Initialize command router.

        Args:
            runtime: TaskRuntime instance (uses global if not provided)
        """
        self._runtime = runtime or get_runtime()
        self._handlers: Dict[str, Callable[[CommandContext], CommandResult]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default command handlers."""
        self.register_handler("start", self._handle_start)
        self.register_handler("new", self._handle_new)
        self.register_handler("status", self._handle_status)
        self.register_handler("tasks", self._handle_tasks)
        self.register_handler("resume", self._handle_resume)
        self.register_handler("pause", self._handle_pause)
        self.register_handler("retry", self._handle_retry)
        self.register_handler("abort", self._handle_abort)
        self.register_handler("report", self._handle_report)
        self.register_handler("run", self._handle_run)
        self.register_handler("memory", self._handle_memory)
        self.register_handler("help", self._handle_help)

    def register_handler(self, command: str, handler: Callable[[CommandContext], CommandResult]) -> None:
        """
        Register a command handler.

        Args:
            command: Command name (without /)
            handler: Function to handle the command
        """
        self._handlers[command.lower()] = handler

    def route(self, command: str, context: CommandContext) -> CommandResult:
        """
        Route a command to its handler.

        Args:
            command: Command name (without /)
            context: Command context with user info and arguments

        Returns:
            CommandResult with response message
        """
        # Metrics: Record command routing (Phase: PRODUCTION_INTEGRATION)
        # Feature Flag: runtime_metrics_enabled (default: OFF)
        # Protection: fallback returns dropped, no exception propagation
        if _METRICS_AVAILABLE:
            record_metric(
                metric_name="command_routed_total",
                metric_type="counter",
                value=1.0,
                labels={"command": command, "user_id": str(context.user_id)},
                module="command_router"
            )

        handler = self._handlers.get(command.lower())
        if handler:
            return handler(context)
        return CommandResult(
            success=False,
            message=f"Unknown command: /{command}\nUse /help to see available commands."
        )

    def is_command(self, text: str) -> bool:
        """Check if text is a command."""
        return text.strip().startswith("/")

    def parse_command(self, text: str) -> tuple[str, str]:
        """
        Parse command and arguments from text.

        Args:
            text: Message text starting with /

        Returns:
            Tuple of (command, arguments)
        """
        text = text.strip()
        if not text.startswith("/"):
            return "", text

        # Remove leading /
        text = text[1:]

        # Split into command and args
        parts = text.split(maxsplit=1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        return command, args

    # ========================================
    # Command Handlers
    # ========================================

    def _handle_start(self, ctx: CommandContext) -> CommandResult:
        """Handle /start command."""
        welcome = (
            "👋 *Welcome to OpenEmotion Agent!*\n\n"
            "I'm your AI-powered task assistant. I can help you:\n"
            "• Create and manage tasks\n"
            "• Track progress and status\n"
            "• Execute tasks step by step\n\n"
            "*Available Commands:*\n"
            "/new `task` - Create a new task\n"
            "/status - Check current task status\n"
            "/tasks - List all tasks\n"
            "/run - Execute next step\n"
            "/pause - Pause current task\n"
            "/resume - Resume a paused task\n"
            "/retry - Retry last failed step\n"
            "/abort - Abort current task\n"
            "/report - Generate task report\n"
            "/memory - View memory summary\n"
            "/proto - Control Proto-Self ingress version\n"
            "/help - Show this help\n\n"
            "Just send me a message to start creating a task!"
        )
        return CommandResult(success=True, message=welcome)

    def _handle_help(self, ctx: CommandContext) -> CommandResult:
        """Handle /help command."""
        return self._handle_start(ctx)

    def _handle_new(self, ctx: CommandContext) -> CommandResult:
        """Handle /new command - create new task with scope."""
        if not ctx.args:
            return CommandResult(
                success=True,
                message="📋 *Create New Task*\n\n"
                        "Please provide a task description.\n"
                        "Example: `/new Build a REST API for user management`\n\n"
                        "Or just send me a message describing what you need!",
                data={"action": "await_task_description"}
            )

        try:
            # Build scope from context
            scope_key = f"tg:{ctx.chat_id or 'unknown'}:{ctx.user_id or 'unknown'}"

            # Create task with scope
            task = self._runtime.create_task(
                ctx.args,
                chat_id=str(ctx.chat_id),
                user_id=str(ctx.user_id),
                scope_key=scope_key
            )

            # Plan task (decompose into steps)
            task = self._runtime.plan_task(task.id)

            # Start task
            task = self._runtime.start_task(task.id)

            # Build response
            lines = [
                "✅ *Task Created and Started!*",
                "",
                f"🆔 Task ID: `{task.id}`",
                f"🎯 Objective: {task.objective}",
                f"📊 Status: {task.status.value.upper()}",
                "",
                f"📝 *Planned Steps ({len(task.steps)}):*"
            ]

            for i, step in enumerate(task.steps):
                current = " ▶️" if i == task.current_step_index else ""
                lines.append(f"  {i+1}. {step.description}{current}")

            lines.append("")
            lines.append("Use /run to execute the next step.")
            lines.append("Use /report to see full task details.")

            return CommandResult(
                success=True,
                message="\n".join(lines),
                data={"task_id": task.id, "action": "task_created"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to create task: {str(e)}"
            )

    def _handle_status(self, ctx: CommandContext) -> CommandResult:
        """Handle /status command - check current task status with scope."""
        from app.runtime.task_resolver import get_resolver

        try:
            # Get active task with scope isolation
            resolver = get_resolver()
            task = resolver.get_active_for_context(ctx)

            if not task:
                return CommandResult(
                    success=True,
                    message="📊 *Task Status*\n\n"
                            "No active task in current scope.\n\n"
                            "Use /new to create a task!",
                    data={"action": "no_active_task", "scope_key": resolver._build_scope_key(ctx)}
                )

            # Build status
            completed, total = task.progress
            progress_pct = task.progress_percentage

            lines = [
                f"📊 *Task Status: {task.id}*",
                "",
                f"🎯 Objective: {task.objective}",
                f"📌 Status: {task.status.value.upper()}",
                f"📈 Progress: {completed}/{total} steps ({progress_pct:.0f}%)"
            ]

            # Current step
            current = task.current_step
            if current:
                lines.append("")
                lines.append(f"▶️ *Current Step:* {current.description}")

            # Next step
            if task.current_step_index < len(task.steps):
                next_step = task.steps[task.current_step_index]
                if next_step != current:
                    lines.append("")
                    lines.append(f"⏭️ *Next Step:* {next_step.description}")

            # Actions
            lines.append("")
            lines.append("*Actions:*")
            if task.status == TaskStatus.RUNNING:
                lines.append("  /run - Execute next step")
                lines.append("  /pause - Pause task")
            elif task.status == TaskStatus.PAUSED:
                lines.append("  /resume - Resume task")
            elif task.status == TaskStatus.BLOCKED:
                lines.append("  /retry - Retry failed step")

            return CommandResult(
                success=True,
                message="\n".join(lines),
                data={"task_id": task.id, "action": "status_check"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to get status: {str(e)}"
            )

    def _handle_tasks(self, ctx: CommandContext) -> CommandResult:
        """Handle /tasks command - list tasks with scope isolation."""
        from app.runtime.task_resolver import get_resolver

        try:
            # List tasks with scope isolation
            resolver = get_resolver()
            scope_key = resolver._build_scope_key(ctx)
            tasks = resolver.list_tasks_for_scope(scope_key, limit=20)

            if not tasks:
                return CommandResult(
                    success=True,
                    message="📋 *Task List*\n\n"
                            "No tasks found in current scope.\n\n"
                            "Use /new to create your first task!",
                    data={"action": "list_tasks", "scope_key": scope_key}
                )

            lines = ["📋 *Task List*", ""]

            for task in tasks:
                completed, total = task.progress
                status_emoji = {
                    TaskStatus.CREATED: "📝",
                    TaskStatus.PLANNING: "📋",
                    TaskStatus.RUNNING: "▶️",
                    TaskStatus.PAUSED: "⏸️",
                    TaskStatus.BLOCKED: "🚫",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.FAILED: "❌",
                    TaskStatus.ABORTED: "⏹️"
                }.get(task.status, "❓")

                lines.append(
                    f"{status_emoji} `{task.id}` - {task.objective[:40]}{'...' if len(task.objective) > 40 else ''}"
                )
                lines.append(f"   Status: {task.status.value} | Progress: {completed}/{total}")

            lines.append("")
            lines.append("Use /status to see details of active task.")
            lines.append("Use /report `task_id` for full report.")

            return CommandResult(
                success=True,
                message="\n".join(lines),
                data={"action": "list_tasks", "count": len(tasks)}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to list tasks: {str(e)}"
            )

    def _handle_run(self, ctx: CommandContext) -> CommandResult:
        """Handle /run command - execute next step using unified resolver."""
        try:
            from app.runtime.task_resolver import resolve_task_for_run

            # Use unified resolver
            result = resolve_task_for_run(ctx)

            if not result.found:
                return CommandResult(
                    success=True,
                    message="▶️ *Execute Step*\n\n"
                            "No active task to execute.\n\n"
                            "Use /new to create a task first!",
                    data={
                        "action": "no_active_task",
                        "scope_key": result.scope_key,
                        "resolver_source": result.source.value
                    }
                )

            task = result.task

            if task.status != TaskStatus.RUNNING:
                return CommandResult(
                    success=False,
                    message=f"❌ Task is not running (status: {task.status.value})\n\n"
                            "Use /resume to resume a paused task."
                )

            # Execute next step
            task, exec_result = self._runtime.execute_next_step(task.id)

            lines = ["▶️ *Step Executed*", ""]

            if exec_result.success:
                lines.append("✅ *Step Completed Successfully!*")
                lines.append("")
                lines.append(f"📝 Result: {exec_result.output}")

                if task.status == TaskStatus.COMPLETED:
                    lines.append("")
                    lines.append("🎉 *Task Completed!*")
                    lines.append(f"All {len(task.steps)} steps completed.")
                else:
                    # Show next step
                    if task.current_step_index < len(task.steps):
                        next_step = task.steps[task.current_step_index]
                        lines.append("")
                        lines.append(f"⏭️ *Next Step:* {next_step.description}")
                        lines.append("")
                        lines.append("Use /run to execute next step.")
            else:
                lines.append("❌ *Step Failed*")
                lines.append(f"Error: {exec_result.error}")
                lines.append("")
                lines.append("Use /retry to retry this step.")

            return CommandResult(
                success=exec_result.success,
                message="\n".join(lines),
                data={
                    "task_id": task.id,
                    "action": "step_executed",
                    "scope_key": result.scope_key,
                    "resolver_source": result.source.value
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to execute step: {str(e)}"
            )

    def _handle_resume(self, ctx: CommandContext) -> CommandResult:
        """Handle /resume command - resume task using unified resolver."""
        try:
            from app.runtime.task_resolver import resolve_task_for_resume

            task_id = ctx.args if ctx.args else None

            # Use unified resolver
            result = resolve_task_for_resume(ctx, task_id)

            if not result.found:
                return CommandResult(
                    success=True,
                    message="▶️ *Resume Task*\n\n"
                            f"{result.error or 'No resumable tasks found.'}\n\n"
                            "Use /tasks to see available tasks.",
                    data={
                        "action": "no_resumable_task",
                        "scope_key": result.scope_key,
                        "resolver_source": result.source.value
                    }
                )

            task = result.task

            # Resume if paused
            if task.status == TaskStatus.PAUSED:
                task = self._runtime.resume_task(task.id)
            elif task.status == TaskStatus.BLOCKED:
                # Try retry for blocked tasks
                task, exec_result = self._runtime.retry_step(task.id)
            # For planning/running, just proceed to execute

            return CommandResult(
                success=True,
                message=f"▶️ *Task Resumed*\n\n"
                        f"Task ID: `{task.id}`\n"
                        f"Objective: {task.objective[:50]}\n"
                        f"Status: {task.status.value.upper()}\n\n"
                        f"Use /run to continue execution.",
                data={
                    "task_id": task.id,
                    "action": "task_resumed",
                    "scope_key": result.scope_key,
                    "resolver_source": result.source.value
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to resume task: {str(e)}"
            )

    def _handle_pause(self, ctx: CommandContext) -> CommandResult:
        """Handle /pause command - pause current task."""
        try:
            task = self._runtime.get_active_task()

            if not task:
                return CommandResult(
                    success=True,
                    message="⏸️ *Pause Task*\n\n"
                            "No active task to pause.\n\n"
                            "Use /status to check current task.",
                    data={"action": "no_active_task"}
                )

            task = self._runtime.pause_task(task.id)

            return CommandResult(
                success=True,
                message=f"⏸️ *Task Paused*\n\n"
                        f"Task ID: `{task.id}`\n"
                        f"Status: {task.status.value.upper()}\n\n"
                        f"Use /resume to continue later.",
                data={"task_id": task.id, "action": "task_paused"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to pause task: {str(e)}"
            )

    def _handle_retry(self, ctx: CommandContext) -> CommandResult:
        """Handle /retry command - retry last failed step."""
        try:
            task = self._runtime.get_active_task()

            if not task:
                return CommandResult(
                    success=True,
                    message="🔄 *Retry Failed Step*\n\n"
                            "No active task found.\n\n"
                            "Use /status to check current task.",
                    data={"action": "no_active_task"}
                )

            # Execute retry
            task, result = self._runtime.execute_next_step(task.id)

            lines = ["🔄 *Step Retried*", ""]

            if result.success:
                lines.append("✅ *Step Completed Successfully!*")
                lines.append(f"📝 Result: {result.output}")
            else:
                lines.append("❌ *Step Failed Again*")
                lines.append(f"Error: {result.error}")

            return CommandResult(
                success=result.success,
                message="\n".join(lines),
                data={"task_id": task.id, "action": "step_retried"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to retry step: {str(e)}"
            )

    def _handle_abort(self, ctx: CommandContext) -> CommandResult:
        """Handle /abort command - abort current task."""
        try:
            task = self._runtime.get_active_task()

            if not task:
                return CommandResult(
                    success=True,
                    message="❌ *Abort Task*\n\n"
                            "No active task to abort.\n\n"
                            "Use /status to check current task.",
                    data={"action": "no_active_task"}
                )

            task = self._runtime.abort_task(task.id)

            return CommandResult(
                success=True,
                message=f"❌ *Task Aborted*\n\n"
                        f"Task ID: `{task.id}`\n"
                        f"Status: {task.status.value.upper()}\n\n"
                        f"Use /new to start a new task.",
                data={"task_id": task.id, "action": "task_aborted"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to abort task: {str(e)}"
            )

    def _handle_report(self, ctx: CommandContext) -> CommandResult:
        """Handle /report command - generate task report."""
        try:
            task_id = ctx.args if ctx.args else None

            if task_id:
                # Report for specific task
                report = self._runtime.generate_report(task_id)
            else:
                # Report for active task
                task = self._runtime.get_active_task()

                if not task:
                    # Report for last task
                    tasks = self._runtime.list_tasks(limit=1)
                    if not tasks:
                        return CommandResult(
                            success=True,
                            message="📊 *Task Report*\n\n"
                                    "No tasks to report on.\n\n"
                                    "Use /new to create a task!",
                            data={"action": "no_tasks"}
                        )
                    task = tasks[0]

                report = self._runtime.generate_report(task.id)

            return CommandResult(
                success=True,
                message=report,
                data={"action": "generate_report"}
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"❌ Failed to generate report: {str(e)}"
            )

    def _handle_memory(self, ctx: CommandContext) -> CommandResult:
        """Handle /memory command - view memory summary."""
        return CommandResult(
            success=True,
            message="🧠 *Memory Summary*\n\n"
                    "Memory system initialized but empty.\n\n"
                    "*Memory Types Available:*\n"
                    "• Working Memory - Current task context\n"
                    "• Episodic Memory - Past experiences\n"
                    "• Semantic Memory - Facts and knowledge\n\n"
                    "_Memory integration coming in Phase 5._",
            data={"action": "memory_summary"}
        )


def _build_diagnostic_data(
    intent_result,
    task_id: Optional[str] = None,
    action: str = "unknown"
) -> Dict[str, Any]:
    """
    Build diagnostic data for message tracing (T2, T8).

    Args:
        intent_result: IntentResult from semantic classification
        task_id: Task ID if bound to a task
        action: Action being taken

    Returns:
        Dict with diagnostic fields for tracing
    """
    data = {
        "action": action,
        # T2 Diagnostic fields
        "current_message": intent_result.original_message[:100] if intent_result.original_message else None,
        "classified_intent": str(intent_result.intent.value),
        "matched_task_id": task_id,
        "source_of_context": getattr(intent_result, 'source_of_context', None) or str(intent_result.intent.value),
        "confidence": intent_result.confidence,
        "matched_patterns": intent_result.matched_patterns[:3] if intent_result.matched_patterns else []
    }

    # T8 P1.5 Diagnostic fields
    if hasattr(intent_result, 'scope_key') and intent_result.scope_key:
        data["scope_key"] = intent_result.scope_key
    if hasattr(intent_result, 'resolver_source') and intent_result.resolver_source:
        data["resolver_source"] = intent_result.resolver_source

    return data


def handle_natural_language(ctx: CommandContext, router: Optional[CommandRouter] = None) -> CommandResult:
    """
    Handle natural language messages with semantic routing.

    P1 Strategy: Semantic classification → appropriate handler
    - chat → friendly response
    - question → LLM answer
    - new_task → auto create + auto first step
    - continue_task → bind to active task + continue

    Args:
        ctx: Command context with message info
        router: CommandRouter instance (creates new if not provided)

    Returns:
        CommandResult with response
    """
    message = ctx.message_text.strip()

    if not message:
        return CommandResult(
            success=False,
            message="请发送消息或使用命令。发送 /help 查看可用命令。"
        )

    # === EVENT MIRROR: User Message (Cycle Core v1) ===
    # Mirror user message to OpenEmotion for emotional processing
    # This is the formal chain: Telegram → EgoCore → emotiond /cycle
    user_id = f"telegram:{ctx.user_id}"
    event_mirror = get_event_mirror()
    mirror_result = event_mirror.mirror_user_message(
        user_id=str(ctx.user_id),
        message_text=message,
        chat_id=str(ctx.chat_id),
        username=ctx.username,
    )

    # Extract subject result from Cycle Core v1
    subject_result = None
    if mirror_result.success and mirror_result.response:
        subject_result = mirror_result.response.get("result")
        logger.info(
            f"Cycle Core v1 result: latency={mirror_result.latency_ms:.1f}ms, "
            f"trace={mirror_result.response.get('trace_id')}, "
            f"primary_mode={subject_result.get('interaction_interpretation', {}).get('primary_mode') if subject_result else 'N/A'}"
        )
    else:
        logger.warning(f"Cycle Core v1 failed: {mirror_result.error}")
    # ===================================

    # Initialize router if needed
    if router is None:
        router = CommandRouter()

    # Use semantic router for classification
    from app.runtime.semantic_router import classify_message, SemanticIntent
    intent_result = classify_message(message)
    intent = intent_result.intent

    # Route based on intent, passing subject_result to handlers
    if intent == SemanticIntent.CHAT:
        return _handle_chat_intent(ctx, router, intent_result, subject_result)

    elif intent == SemanticIntent.QUESTION:
        return _handle_question_intent(ctx, router, intent_result, subject_result)

    elif intent == SemanticIntent.NEW_TASK:
        return _handle_new_task_intent(ctx, router, intent_result, subject_result)

    elif intent == SemanticIntent.CONTINUE_TASK:
        return _handle_continue_intent(ctx, router, intent_result, subject_result)

    else:
        # Fallback
        return CommandResult(
            success=True,
            message="我收到了你的消息。如果你需要执行任务，请直接告诉我。",
            data={"action": "chat", "intent": str(intent), "subject_result": subject_result is not None}
        )


def _handle_chat_intent(ctx: CommandContext, router: CommandRouter, intent_result, subject_result=None) -> CommandResult:
    """
    Handle chat intent - 使用新的"主体解释 -> 现实裁决 -> 回复生成"链路。

    v2.1 (2026-03-19):
    - 注入 ContextAssembler / RepairContextManager
    - 添加链路日志追踪

    链路：
    用户输入 -> ContextAssembler -> RepairContextManager -> EventBuilder
    -> EventNormalizer -> InteractionEventEnvelope
    -> SubjectAdapter -> SubjectInterpretationResult
    -> RuntimeDecider -> RuntimeDecisionEnvelope
    -> ResponseContractBuilder -> OutwardResponsePackage
    -> Verbalizer -> 自然语言回复

    关键原则：
    - 主体解释权归 OpenEmotion
    - 现实裁决权归 EgoCore
    - 不再使用固定欢迎词模板
    - 没有上下文不允许直接规划
    """
    from app.handlers.social_chat_handler import handle_social_chat
    from app.runtime.task_resolver import get_resolver
    from app.interaction.session_context_store import get_session_context_store

    message = ctx.message_text.strip().lower()
    user_id = f"telegram:{ctx.user_id}"
    session_id = f"tg_{ctx.chat_id}"

    # === 链路日志 ===
    chain_log = {
        "context_assembler_invoked": False,
        "repair_context_detected": False,
        "event_builder_mode": "basic",
        "completion_guard_verdict": "not_applicable",  # CHAT intent 通常不涉及 completion
        "final_status_source": "verbalizer",
    }

    # Set source of context
    intent_result.source_of_context = "chat"

    # === 获取会话上下文 ===
    context_store = get_session_context_store()
    recent_messages = context_store.get_recent_turns(session_id, limit=10)

    # 获取当前轮次索引（在添加当前输入之前）
    turn_index = context_store.get_turn_index(session_id)

    # 添加当前用户输入到上下文
    context_store.add_turn(session_id, "user", ctx.message_text)

    # === v2.1: 检测失败反馈 (前移) ===
    from app.runtime.repair_context_manager import get_repair_context_manager
    repair_manager = get_repair_context_manager()

    failure_record = repair_manager.detect_user_feedback(
        user_input=ctx.message_text,
        session_id=session_id,
        user_id=str(ctx.user_id),
    )
    if failure_record:
        chain_log["repair_context_detected"] = True
        logger.info(
            f"CHAT intent: detected failure feedback, "
            f"failed_task={failure_record.task_id}, "
            f"feedback={ctx.message_text[:50]}"
        )

    # === 使用新链路处理 ===

    # 获取活动任务（如果需要传递给处理器）
    resolver = get_resolver()
    active_task = resolver.get_active_for_context(ctx)

    # 转换活动任务格式
    task_dict = None
    if active_task:
        completed, total = active_task.progress
        task_dict = {
            "task_id": active_task.id,
            "objective": active_task.objective,
            "status": active_task.status.value,
            "progress": {"completed": completed, "total": total}
        }
        intent_result.matched_task_id = active_task.id
        intent_result.scope_key = resolver._build_scope_key(ctx)

    # 调用新链路，传递 turn_index
    result = handle_social_chat(
        user_input=ctx.message_text,
        user_id=ctx.user_id,
        chat_id=ctx.chat_id,
        username=ctx.username,
        recent_messages=recent_messages,
        active_task=task_dict,
        turn_index=turn_index,  # 新增：传递轮次索引
    )

    # 添加助手回复到上下文
    if result["success"]:
        context_store.add_turn(session_id, "assistant", result["message"])

    # 更新诊断数据
    diagnostic = _build_diagnostic_data(
        intent_result,
        active_task.id if active_task else None,
        "social_chat_handler"
    )
    diagnostic.update(result.get("data", {}))

    # === 提取链路日志 ===
    exec_ctx = result.get("data", {}).get("execution_context", {})
    chain_log["context_assembler_invoked"] = exec_ctx.get("has_task") is not None or exec_ctx.get("target_path") is not None
    chain_log["repair_context_detected"] = exec_ctx.get("repair_needed", False)
    chain_log["event_builder_mode"] = "execution_context"

    logger.info(f"CHAIN_LOG (CHAT): {chain_log}")

    return CommandResult(
        success=result["success"],
        message=result["message"],
        data=diagnostic
    )


def _handle_question_intent(ctx: CommandContext, router: CommandRouter, intent_result, subject_result=None) -> CommandResult:
    """
    Handle question intent - P1-C 优化版

    关键改进：
    1. 短问句已通过 semantic_router 分流到 CHAT intent
    2. 剩余 question intent 使用 verbalizer 约束自然度
    3. 整合 relationship_context 和 style_profile 保持风格连续性
    """
    message = ctx.message_text.strip()
    user_id = f"telegram:{ctx.user_id}"
    session_id = f"tg_{ctx.chat_id}"

    # Set source of context
    intent_result.source_of_context = "question"

    # === P1-C: 获取会话上下文保持风格连续性 ===
    from app.response.relationship_context import get_relationship_context_manager
    from app.response.style_profile import get_style_profile_manager
    from app.response.question_verbalizer import QuestionVerbalizer
    from app.interaction.session_context_store import get_session_context_store

    rel_manager = get_relationship_context_manager()
    style_manager = get_style_profile_manager()
    context_store = get_session_context_store()

    relationship_ctx = rel_manager.get_context(session_id)
    style_profile = style_manager.get_profile(session_id)
    recent_messages = context_store.get_recent_turns(session_id, limit=5)

    # 检查是否为短问句（二次检查，确保不遗漏）
    from app.response.question_verbalizer import is_short_question
    if is_short_question(message):
        # 短问句应走 CHAT 链路，但这里做兜底处理
        verbalizer = QuestionVerbalizer(
            relationship_context=relationship_ctx,
            style_profile=style_profile,
        )
        reply = verbalizer.verbalize(message, recent_messages)

        # 更新上下文
        rel_manager.update_context(
            session_id=session_id,
            event_type="short_question",
            user_input=message[:50],
            agent_response=reply[:50],
            impact="neutral",
        )

        return CommandResult(
            success=True,
            message=reply,
            data=_build_diagnostic_data(intent_result, None, "short_question_verbalized")
        )

    # === 长问题处理：使用 LLM，但经过 verbalizer 约束 ===
    # Build system prompt with natural expression constraints
    system_prompt = """你是助手。回答问题时遵守以下原则：

1. 回复简短，1-2句话
2. 口语化，不解释系统内部
3. 不提及用户ID、chatID等内部标识
4. 保持自然对话风格
"""

    try:
        from app.llm_client import get_llm_client
        llm = get_llm_client()

        # Use LLM to generate initial response
        response = llm.generate(
            message,
            system_prompt=system_prompt
        )

        # P1-C: 使用 verbalizer 过滤和优化
        verbalizer = QuestionVerbalizer(
            relationship_context=relationship_ctx,
            style_profile=style_profile,
        )

        # 如果 LLM 回复过长或包含内部标识，使用 verbalizer 兜底
        raw_reply = response.content
        if len(raw_reply) > 100 or "telegram:" in raw_reply or "8420019401" in raw_reply:
            # 使用 verbalizer 生成简短回复
            reply = verbalizer.verbalize(message, recent_messages)
        else:
            reply = raw_reply

        # 更新上下文
        rel_manager.update_context(
            session_id=session_id,
            event_type="question",
            user_input=message[:50],
            agent_response=reply[:50],
            impact="neutral",
        )

        return CommandResult(
            success=True,
            message=reply,
            data=_build_diagnostic_data(intent_result, None, "question_verbalized")
        )

    except Exception as e:
        # P1-C: 异常时使用 verbalizer 兜底
        logger.error(f"Question handling error: {e}")
        verbalizer = QuestionVerbalizer()
        fallback_reply = verbalizer.verbalize(message, recent_messages)

        return CommandResult(
            success=True,
            message=fallback_reply,
            data=_build_diagnostic_data(intent_result, None, "question_fallback")
        )


def _handle_new_task_intent(ctx: CommandContext, router: CommandRouter, intent_result, subject_result=None) -> CommandResult:
    """Handle new task intent - auto create and execute first step.

    v2.1 (2026-03-19):
    - 注入 ContextAssembler 组装执行上下文
    - 使用 CompletionGuard 验证完成状态
    - 添加链路日志追踪

    Args:
        subject_result: Optional Cycle Core v1 result from OpenEmotion
    """
    message = ctx.message_text.strip()

    # === 链路日志 ===
    chain_log = {
        "context_assembler_invoked": False,
        "repair_context_detected": False,
        "event_builder_mode": "basic",
        "completion_guard_verdict": "pending",
        "final_status_source": "legacy_formatter",
    }

    # Set source of context
    intent_result.source_of_context = "new_task"

    # === v2.1: 注入 ContextAssembler ===
    from app.runtime.context_assembler import get_context_assembler
    from app.runtime.repair_context_manager import get_repair_context_manager

    context_assembler = get_context_assembler()
    repair_manager = get_repair_context_manager()

    session_id = f"tg_{ctx.chat_id}"

    # 组装执行上下文
    execution_context = context_assembler.assemble(
        user_input=message,
        session_id=session_id,
        user_id=str(ctx.user_id),
        chat_id=str(ctx.chat_id),
    )
    chain_log["context_assembler_invoked"] = True

    # 检测失败反馈
    failure_record = repair_manager.detect_user_feedback(
        user_input=message,
        session_id=session_id,
        user_id=str(ctx.user_id),
    )
    if failure_record:
        chain_log["repair_context_detected"] = True
        logger.info(f"Detected failure feedback in NEW_TASK: task={failure_record.task_id}")

    # === Cycle Core v1: Consume subject result ===
    policy_hint = None
    response_tendency = None
    if subject_result:
        policy_hint = subject_result.get("policy_hint")
        response_tendency = subject_result.get("response_tendency")
        logger.info(
            f"NEW_TASK consuming subject_result: "
            f"policy_hint={policy_hint is not None}, "
            f"response_tendency={response_tendency is not None}"
        )

    # Check if this is a high-risk operation
    from app.runtime.semantic_router import get_semantic_router
    semantic_router = get_semantic_router()

    if semantic_router.is_high_risk(message):
        return CommandResult(
            success=True,
            message="⚠️ 这看起来是一个可能需要确认的操作。\n\n"
                    f"请求: {message}\n\n"
                    "请确认你想要执行此操作，或使用更安全的表达方式。\n"
                    "例如：\"分析一下这个目录\" 而不是 \"删除这个目录\"",
            data=_build_diagnostic_data(intent_result, None, "task_requires_confirmation")
        )

    # Extract task content
    task_content = semantic_router.extract_task_content(message) or message

    # Create the task
    try:
        # Create a new context with args for _handle_new
        new_ctx = CommandContext(
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            username=ctx.username,
            args=task_content,
            message_text=ctx.message_text
        )

        # Create task
        result = router._handle_new(new_ctx)

        if not result.success:
            return result

        # Get the created task
        task_id = result.data.get("task_id") if result.data else None
        if not task_id:
            return result

        task = router._runtime.get_task(task_id)
        if not task:
            return result

        # Set matched task ID for diagnostics
        intent_result.matched_task_id = task.id

        # Auto-execute first step (task is already started by _handle_new)
        try:
            # Execute first step
            task, exec_result = router._runtime.execute_next_step(task.id)

            # === v2.1: 使用 CompletionGuard 验证完成状态 ===
            from app.runtime.completion_guard import get_completion_guard, CompletionStatus

            guard = get_completion_guard()
            task_type = guard.classify_task_type(task.objective)

            # 构造 execution_result 格式
            execution_result = {
                "success": exec_result.success,
                "output": exec_result.output,
                "error": exec_result.error,
                "tool_result": {"success": exec_result.success} if exec_result else None,
            }

            # 验证完成状态
            verification = guard.verify(
                task_type=task_type,
                task_goal=task.objective,
                execution_result=execution_result,
                target_path=execution_context.target_path,
            )

            chain_log["completion_guard_verdict"] = "allow" if verification.verified else "block"

            # 根据 verification 结果决定最终状态
            # 如果 verification 失败，不能标记为 completed
            actual_status = task.status.value
            if actual_status == "completed" and not verification.verified:
                logger.warning(
                    f"CompletionGuard blocked completed status: "
                    f"task={task.id}, status={verification.status.value}, "
                    f"missing={verification.missing}"
                )
                actual_status = "blocked"
                chain_log["final_status_source"] = "completion_guard"
            else:
                chain_log["final_status_source"] = "tool_result" if verification.verified else "legacy_formatter"

            # 记录链路日志
            logger.info(
                f"CHAIN_LOG: {chain_log}"
            )

            # Build response with Cycle Core v1 influence
            # Check response_tendency for tone adjustment
            tone = "neutral"
            if response_tendency:
                tone = response_tendency.get("tone", "neutral")
                urgency = response_tendency.get("urgency", 0.5)
                logger.info(f"Task response using tendency: tone={tone}, urgency={urgency}")

            # Adjust message based on tone
            if tone == "warm" or tone == "friendly":
                header = "好的，我来帮你处理这个任务"
            elif tone == "formal":
                header = "已接收任务请求"
            elif urgency > 0.7:
                header = "收到，立即开始执行"
            else:
                header = "✅ 已识别为任务并自动开始执行"

            lines = [
                header,
                "",
                f"📋 任务: {task.objective}",
                f"📊 状态: {actual_status}",
            ]

            if exec_result.success:
                lines.append("")
                lines.append("📝 执行结果:")
                lines.append(exec_result.output[:500] if exec_result.output else "完成")
            else:
                lines.append("")
                lines.append(f"⚠️ 执行遇到问题: {exec_result.error[:100] if exec_result.error else '未知错误'}")

            lines.append("")
            if actual_status == "running":
                lines.append("说\"继续\"可以继续执行下一步。")
            elif actual_status == "completed":
                lines.append("🎉 任务已完成！")
            elif actual_status == "blocked":
                lines.append("⚠️ 任务被阻塞。可能需要验证执行结果。")
                lines.append("使用 /retry 重试或 /report 查看详情。")
            elif task.status.value == "blocked":
                lines.append("任务被阻塞。使用 /retry 重试或 /report 查看详情。")

            return CommandResult(
                success=True,
                message="\n".join(lines),
                data=_build_diagnostic_data(intent_result, task.id, "auto_task")
            )

        except Exception as e:
            return CommandResult(
                success=True,
                message=f"✅ 已创建任务，但自动执行失败。\n\n任务ID: {task.id}\n错误: {str(e)[:50]}\n\n使用 /run 手动执行。",
                data=_build_diagnostic_data(intent_result, task.id, "task_created")
            )

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"创建任务失败: {str(e)}",
            data=_build_diagnostic_data(intent_result, None, "task_error")
        )


def _handle_continue_intent(ctx: CommandContext, router: CommandRouter, intent_result, subject_result=None) -> CommandResult:
    """Handle continue intent - bind to active/recent task and continue using unified resolver.

    Args:
        subject_result: Optional Cycle Core v1 result from OpenEmotion
    """
    from app.runtime.task_resolver import resolve_task_for_continue

    # === Cycle Core v1: Consume subject result ===
    policy_hint = None
    response_tendency = None
    memory_update = None
    if subject_result:
        policy_hint = subject_result.get("policy_hint")
        response_tendency = subject_result.get("response_tendency")
        memory_update = subject_result.get("memory_update")
        logger.info(
            f"CONTINUE consuming subject_result: "
            f"policy_hint={policy_hint is not None}, "
            f"response_tendency={response_tendency is not None}, "
            f"memory_update={memory_update is not None}"
        )

    # Use unified resolver
    result = resolve_task_for_continue(ctx)

    # Set source of context
    intent_result.source_of_context = "continue"
    intent_result.scope_key = result.scope_key
    intent_result.resolver_source = result.source.value

    if not result.found:
        return CommandResult(
            success=True,
            message=f"📋 {result.error or '当前没有可继续的任务。'}\n\n"
                    "你可以直接告诉我你需要做什么，例如：\n"
                    "• 帮我检查项目问题\n"
                    "• 分析代码结构",
            data=_build_diagnostic_data(intent_result, None, "no_task_to_continue")
        )

    task = result.task
    intent_result.matched_task_id = task.id

    # Found a task to continue
    try:
        exec_result = None

        # Handle different states
        if task.status.value == "paused":
            task = router._runtime.resume_task(task.id)
            # Now execute next step
            task, exec_result = router._runtime.execute_next_step(task.id)
        elif task.status.value == "blocked":
            # Try retry
            try:
                task, exec_result = router._runtime.retry_step(task.id)
            except Exception:
                # If retry fails, just show the task status
                pass
        elif task.status.value == "running":
            # Execute next step
            task, exec_result = router._runtime.execute_next_step(task.id)
        # For planning or other states, start the task
        elif task.status.value == "planning" or task.status.value == "created":
            task = router._runtime.start_task(task.id)
            task, exec_result = router._runtime.execute_next_step(task.id)

        # Get progress
        completed, total = task.progress if isinstance(task.progress, tuple) else (0, 0)

        # Cycle Core v1: Adjust response based on memory_update and response_tendency
        # Check if this is a follow-up from previous context
        has_memory_context = memory_update and memory_update.get("event_stored")
        tone = "neutral"
        if response_tendency:
            tone = response_tendency.get("tone", "neutral")

        # Adjust header based on context and tone
        if has_memory_context and tone == "warm":
            header = "好的，继续处理"
        elif has_memory_context:
            header = "继续执行"
        elif tone == "formal":
            header = "已绑定到任务"
        else:
            header = "↻ 已绑定到任务"

        lines = [
            header,
            "",
            f"📋 任务: {task.objective}",
            f"📊 状态: {task.status.value}",
            f"📈 进度: {completed}/{total}",
        ]

        # Log Cycle Core v1 influence
        logger.info(
            f"CONTINUE response influenced by: "
            f"memory_context={has_memory_context}, tone={tone}"
        )

        if exec_result and exec_result.success:
            lines.append("")
            lines.append("📝 执行结果:")
            lines.append(exec_result.output[:300] if exec_result.output else "完成")
        elif exec_result and not exec_result.success:
            lines.append("")
            lines.append(f"⚠️ 执行遇到问题: {exec_result.error[:100] if exec_result.error else '未知错误'}")

        if task.status.value == "completed":
            lines.append("")
            lines.append("🎉 任务已完成！")
        elif task.status.value == "running":
            lines.append("")
            lines.append("说\"继续\"可以继续执行下一步。")
        elif task.status.value == "blocked":
            lines.append("")
            lines.append(f"⚠️ 任务被阻塞: {task.error[:100] if task.error else ''}")
            lines.append("使用 /retry 重试或 /report 查看详情。")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            data=_build_diagnostic_data(intent_result, task.id, "continue_task")
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return CommandResult(
            success=True,
            message=f"继续任务时遇到问题: {str(e)[:100]}\n\n使用 /report 查看任务详情。",
            data=_build_diagnostic_data(intent_result, task.id if task else None, "continue_error")
        )


# Global router instance
_router: Optional[CommandRouter] = None


def get_router(runtime: Optional[TaskRuntime] = None) -> CommandRouter:
    """Get the global command router instance."""
    global _router
    if _router is None:
        _router = CommandRouter(runtime)
    return _router
