"""
runEmbeddedEgoCoreAgent - legacy runtime core kept for compatibility

⚠️ Status:
- This module is still used by the older runtime chain and related tests.
- It is NOT the formal Telegram Runtime v2 mainline.
- Telegram Runtime v2 formal mainline lives in `app/runtime_v2/*` + `app/telegram_bot.py` with `use_runtime_v2=True`.

Historical intent:
- EgoCore as the formal agent runtime entry
- OpenEmotion as cognition core inside the loop

Current cleanup rule:
- edit this module only for compatibility containment, migration support, or legacy test preservation
- do not treat this file as the primary entry when changing Telegram Runtime v2 behavior

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timezone
import logging
import traceback

from .types import (
    EgoCoreRunParams,
    EgoCoreRunResult,
    RunStatus,
    LifecyclePhase,
    ReplyPayload,
    ReplyType,
    SessionKey,
    NO_REPLY,
)
from .lane_manager import get_lane_manager, enqueue_in_lane
from .session_manager import get_session_manager, SessionManager
from .event_bus import (
    get_event_bus,
    emit_lifecycle_event,
    emit_tool_event,
    emit_reply_event,
)
from .context_assembler import (
    ContextAssembler,
    get_context_assembler,
    ExecutionContext,
)
from .completion_guard import (
    CompletionGuard,
    get_completion_guard,
    CompletionStatus,
)
from .repair_context_manager import (
    RepairContextManager,
    get_repair_context_manager,
)
from .follow_up_resolver import resolve_follow_up
from .html_artifact_adapter import inspect_state as inspect_html_state, apply_edit as apply_html_edit
from .task_planning import build_minimal_task_plan
from .artifact_skill_contract import ArtifactSkillRequest, ArtifactEdit
from .html_skill import execute_html_skill
from .request_classifier import classify_request, is_small_talk
from .request_registry import get_request_registry, TurnRecord, RequestRecord
from .completion_contract import CompletionContract, HtmlEffectVerifier
from app.tools import setup_tools, get_registry, execute_tool


def _normalize_artifact_edit(edit: Dict[str, Any]) -> Dict[str, Any]:
    """Host-side artifact edit normalization before skill/tool execution."""
    normalized = dict(edit or {})
    prop = normalized.get("property")
    value = normalized.get("value")
    value_policy = normalized.get("value_policy")

    if not normalized.get("scope"):
        normalized["scope"] = normalized.get("target_scope") or "primary_text"
    if not normalized.get("target_scope"):
        normalized["target_scope"] = normalized.get("scope")

    if not normalized.get("value_policy"):
        if value == "agent_choice":
            normalized["value_policy"] = "agent_choice"
        else:
            normalized["value_policy"] = "literal"

    if not normalized.get("operation"):
        if prop == "background_color" and (normalized.get("value_policy") == "agent_choice" or value in (None, "", "agent_choice")):
            normalized["operation"] = "choose_and_set"
        else:
            normalized["operation"] = "set"

    if prop == "background_color" and (normalized.get("value_policy") == "agent_choice" or value == "agent_choice"):
        normalized["operation"] = "choose_and_set"
        normalized["value"] = "agent_choice"

    return normalized

logger = logging.getLogger(__name__)


def _has_verified_html_effect(tool_results: List[Dict[str, Any]], expected_target: Optional[str] = None) -> bool:
    """Require structured post-edit observation before claiming completion."""
    verifier = HtmlEffectVerifier()
    contract = CompletionContract(
        effect_type="artifact_style_change",
        expected_target=expected_target,
        required_observations=["target_path", "applied_edit", "current_state"],
        verifier_name="html_effect_verifier",
    )
    for item in tool_results or []:
        if not item.get("success"):
            continue
        if item.get("tool_name") != "html_skill":
            continue
        meta = item.get("metadata") or {}
        result = verifier.verify(contract, {"observations": meta.get("observations", []) or []})
        if result.passed:
            return True
    return False


def create_run_id() -> str:
    import uuid
    return f"run_{uuid.uuid4().hex[:8]}"


async def runEmbeddedEgoCoreAgent(
    params: EgoCoreRunParams,
) -> EgoCoreRunResult:
    """
    EgoCore 核心运行入口
    
    这是唯一正式入口，类似 OpenClaw 的 runEmbeddedPiAgent()。
    
    执行流程:
    1. Session/Lane 层: 队列串行化
    2. Agent Loop:
       a. load session/task state
       b. assemble execution context
       c. detect repair / continuation
       d. run cognition core (OpenEmotion /cycle)
       e. planner / executor
       f. tool result consume
       g. completion guard
       h. lifecycle emit
       i. produce normalized reply payload
    3. Reply/Streaming 层: 分发回复
    
    Args:
        params: 运行参数
    
    Returns:
        EgoCoreRunResult
    """
    run_id = params.run_id
    session_id = params.session_id
    session_key = params.session_key
    
    start_time = datetime.now(timezone.utc)
    
    # 初始化结果
    result = EgoCoreRunResult(
        run_id=run_id,
        session_id=session_id,
        status=RunStatus.ACCEPTED,
        started_at=start_time,
    )
    
    # 获取组件
    lane_manager = get_lane_manager()
    session_manager = get_session_manager()
    event_bus = get_event_bus()
    context_assembler = get_context_assembler()
    completion_guard = get_completion_guard()
    repair_manager = get_repair_context_manager()
    
    # 发射 start 事件
    emit_lifecycle_event(
        phase=LifecyclePhase.START,
        run_id=run_id,
        session_id=session_id,
        data={"trigger": params.trigger, "channel": params.channel},
    )
    
    # === Layer 1: Session/Lane ===
    # 将任务加入队列
    lane_key = lane_manager.resolve_lane_key(session_key)
    
    # 创建执行协程
    async def execute():
        nonlocal result
        
        try:
            result.status = RunStatus.RUNNING
            
            # === Step 1: Load session state ===
            session = await session_manager.get_or_create(
                session_key=session_key,
                channel=params.channel,
            )
            
            turn_index = await session_manager.increment_turn(session_key)
            registry = get_request_registry()
            turn_id = f"turn_{session.session_id}_{turn_index}"

            # === Step 1.5: request classifier + planning step ===
            session_state = session.to_dict()
            req_class = await classify_request(params.prompt, session_state)
            task_turn_kind = req_class.get("kind")
            registry.record_turn(TurnRecord(
                turn_id=turn_id,
                session_key=session_key,
                message_text=params.prompt,
                classified_as=req_class.get("kind", "unknown"),
                message_id=(params.extra_context or {}).get("telegram_message_id"),
            ))

            # small-talk: 明确走普通回复，不消费旧 plan，不让旧 artifact context 抢回复
            if req_class.get("kind") == "unresolved_request_query":
                unresolved = registry.get_latest_unresolved_request(session_key)
                latest = registry.get_latest_task_request(session_key)
                if unresolved:
                    result.reply_text = f"我查到了，上一条未闭环请求还在{unresolved.status}：{unresolved.objective}"
                    result.status = RunStatus.COMPLETED
                    return result
                if latest and not latest.reply_sent:
                    result.reply_text = f"我查到最近一条请求还没有完成回复：{latest.objective}"
                    result.status = RunStatus.COMPLETED
                    return result
                result.reply_text = "我这边没有查到未闭环的上一条请求。你可以把那条消息再发一次，我直接跟进。"
                result.status = RunStatus.COMPLETED
                return result

            if req_class.get("kind") == "small_talk":
                await session_manager.update(
                    session_key=session_key,
                    active_task_id=None,
                    task_plan={},
                    plan_steps=[],
                    targets=[],
                    completed_steps=[],
                )
                session.active_task_id = None
                session.task_plan = {}
                session.plan_steps = []
                session.targets = []
                session.completed_steps = []
                # 保留 artifact memory 作为被动背景，不进入本轮 task execution 决策

            # completed task 默认关闭；只有 relative follow-up 才允许继承 artifact context，不继承旧 steps
            if not getattr(session, "plan_steps", []) and getattr(session, "active_task_id", None):
                await session_manager.update(
                    session_key=session_key,
                    active_task_id=None,
                    task_plan={},
                    plan_steps=[],
                    targets=[],
                    completed_steps=[],
                )
                session.active_task_id = None
                session.task_plan = {}
                session.plan_steps = []
                session.targets = []
                session.completed_steps = []

            planning_input = {
                "artifact_context_by_path": getattr(session, "artifact_context_by_path", {}),
                "active_target": req_class.get("force_target_path") or (req_class.get("llm_intent") or {}).get("target_path") or getattr(session, "active_target", None),
            }

            request_id = None
            if req_class.get("kind") in {"new_task", "follow_up"}:
                request_id = f"req_{session.session_id}_{turn_index}"
                latest_req = registry.get_active_request(session_key) or registry.get_latest_task_request(session_key)
                if latest_req and latest_req.request_id != request_id and latest_req.status in {"pending", "running", "waiting_input"}:
                    registry.supersede_request(latest_req.request_id, request_id)
                registry.record_request(RequestRecord(
                    request_id=request_id,
                    origin_turn_id=turn_id,
                    session_key=session_key,
                    objective=params.prompt,
                    request_type=req_class.get("kind", "other"),
                    status="pending",
                    linked_targets=[],
                ))
                registry.bind_turn_to_request(turn_id, request_id)

            if req_class.get("kind") in {"new_task", "follow_up"}:
                # 新请求/显式续接：允许强制重绑 active target，但只在 new_task 时清空旧 plan。
                reset_fields = {
                    "active_target": req_class.get("force_target_path") or (req_class.get("llm_intent") or {}).get("target_path") or getattr(session, "active_target", None),
                    "active_artifact_path": req_class.get("force_target_path") or (req_class.get("llm_intent") or {}).get("target_path") or getattr(session, "active_artifact_path", None),
                }
                if req_class.get("kind") == "new_task":
                    reset_fields.update({
                        "active_task_id": None,
                        "task_plan": {},
                        "plan_steps": [],
                        "targets": [],
                        "completed_steps": [],
                    })
                await session_manager.update(session_key=session_key, **reset_fields)
                if req_class.get("kind") == "new_task":
                    session.active_task_id = None
                    session.task_plan = {}
                    session.plan_steps = []
                    session.targets = []
                    session.completed_steps = []
                if req_class.get("force_target_path"):
                    session.active_target = req_class.get("force_target_path")
                    session.active_artifact_path = req_class.get("force_target_path")

            plan_state = build_minimal_task_plan(params.prompt, planning_input)
            if plan_state.plan_steps:
                if request_id:
                    req = registry.requests.get(request_id)
                    if req:
                        req.linked_targets = [t.get("path") for t in plan_state.targets]
                    registry.update_status(request_id, "running")
                await session_manager.update(
                    session_key=session_key,
                    active_task_id=plan_state.task_id,
                    task_plan=plan_state.to_dict(),
                    plan_steps=plan_state.plan_steps,
                    targets=plan_state.targets,
                    active_target=plan_state.active_target,
                )
                session.active_task_id = plan_state.task_id
                session.task_plan = plan_state.to_dict()
                session.plan_steps = plan_state.plan_steps
                session.targets = plan_state.targets
                session.active_target = plan_state.active_target
            elif request_id:
                registry.update_status(request_id, "failed")

            logger.info(
                f"runEmbeddedEgoCoreAgent: session={session.session_id} "
                f"turn={turn_index} run={run_id}"
            )
            
            # === Step 2: Assemble execution context ===
            execution_context = context_assembler.assemble(
                user_input=params.prompt,
                session_id=session_key,
                user_id=params.user_id or "unknown",
                chat_id=params.message_to,
            )
            
            emit_lifecycle_event(
                phase=LifecyclePhase.CONTEXT_LOADED,
                run_id=run_id,
                session_id=session_id,
                data={
                    "has_task": execution_context.task_context.active_task_id is not None,
                    "repair_needed": execution_context.repair_context.has_pending_repair,
                    "target_path": execution_context.target_path,
                },
            )
            
            # === Step 3: Detect repair / continuation ===
            repair_context = repair_manager.get_repair_context(session_id, params.user_id or "unknown")
            
            if repair_context.has_pending_repair:
                logger.info(
                    f"Detected pending repair: task={repair_context.failed_task_id} "
                    f"reason={repair_context.failure_reason}"
                )
                # 关联修复上下文到执行上下文
                execution_context.repair_context = repair_context
            
            # === Step 4: Run cognition core (OpenEmotion) ===
            cognition_result = await _run_cognition_core(
                params=params,
                execution_context=execution_context,
                session=session,
                turn_index=turn_index,
            )
            
            emit_lifecycle_event(
                phase=LifecyclePhase.COGNITION_COMPLETE,
                run_id=run_id,
                session_id=session_id,
                data={
                    "primary_mode": cognition_result.get("primary_mode"),
                    "runtime_route": cognition_result.get("runtime_route"),
                },
            )
            
            result.primary_mode = cognition_result.get("primary_mode")
            result.runtime_route = cognition_result.get("runtime_route")
            
            # === Step 5: Tool execution + re-evaluate loop (P1-P3 minimal) ===
            tool_results = []
            if cognition_result.get("needs_tool_execution"):
                tool_results = await _execute_tools(
                    params=params,
                    cognition_result=cognition_result,
                    event_bus=event_bus,
                )

                emit_lifecycle_event(
                    phase=LifecyclePhase.TOOLS_EXECUTED,
                    run_id=run_id,
                    session_id=session_id,
                    data={"tool_count": len(tool_results)},
                )

                if tool_results:
                    first_ok = next((t for t in tool_results if t.get("success")), None)
                    if first_ok:
                        if first_ok.get("tool_name") == "html_skill":
                            meta = first_ok.get("metadata") or {}
                            observations = meta.get("observations", [])
                            artifact_context_by_path = getattr(session, "artifact_context_by_path", {}) or {}
                            for obs in observations:
                                path = obs.get("path")
                                if path:
                                    artifact_context_by_path[path] = obs
                            active_target = (meta.get("targets") or [{}])[0].get("path") if meta.get("targets") else getattr(session, "active_target", None)
                            if observations:
                                last_obs = observations[-1]
                                await session_manager.update(
                                    params.session_key,
                                    active_artifact_path=active_target,
                                    artifact_kind=last_obs.get("kind"),
                                    active_focus=last_obs.get("focus") or "primary_text",
                                    default_edit_target=last_obs.get("focus") or "primary_text",
                                    artifact_summary=last_obs,
                                    last_known_state=last_obs.get("state", {}),
                                    last_tool_result=first_ok,
                                    active_target=active_target,
                                    completed_steps=(getattr(session, "completed_steps", []) or []) + meta.get("completed_steps", []),
                                    last_observation=last_obs,
                                    artifact_context_by_path=artifact_context_by_path,
                                )
                                session.completed_steps = (getattr(session, "completed_steps", []) or []) + meta.get("completed_steps", [])
                                session.last_observation = last_obs
                                session.artifact_context_by_path = artifact_context_by_path
                                if not session.plan_steps:
                                    await session_manager.update(
                                        params.session_key,
                                        active_task_id=None,
                                        task_plan={},
                                        targets=[],
                                        completed_steps=[],
                                    )
                                    session.active_task_id = None
                                    session.task_plan = {}
                                    session.targets = []
                                    session.completed_steps = []
                        else:
                            artifact_path = (first_ok.get("params") or {}).get("path") or (first_ok.get("metadata") or {}).get("path")
                            artifact_summary = _summarize_artifact_from_tool_result(first_ok)
                            await session_manager.update(
                                params.session_key,
                                active_artifact_path=artifact_path,
                                artifact_kind=artifact_summary.get("artifact_kind") or artifact_summary.get("kind") or ("html" if str(artifact_path).endswith('.html') else None),
                                active_focus=artifact_summary.get("active_focus") or artifact_summary.get("focus") or "primary_text",
                                default_edit_target=artifact_summary.get("default_edit_target") or artifact_summary.get("focus") or "primary_text",
                                artifact_summary=artifact_summary,
                                last_known_state=artifact_summary.get("state", {}),
                                last_tool_result=first_ok,
                            )
                            if not session.plan_steps:
                                await session_manager.update(
                                    params.session_key,
                                    active_task_id=None,
                                    task_plan={},
                                    targets=[],
                                    completed_steps=[],
                                )
                                session.active_task_id = None
                                session.task_plan = {}
                                session.targets = []
                                session.completed_steps = []
                cognition_result = await _evaluate_after_tools(
                    user_input=params.prompt,
                    execution_context=execution_context,
                    openemotion_result=cognition_result.get("interpretation", {}),
                    tool_results=tool_results,
                    expected_target=getattr(session, "active_target", None),
                )
                result.runtime_route = cognition_result.get("runtime_route")

                # plan lifecycle: consume one planned step after execution attempt.
                if getattr(session, "plan_steps", []):
                    consumed = (getattr(session, "plan_steps", []) or [])[0]
                    remaining_steps = (getattr(session, "plan_steps", []) or [])[1:]
                    await session_manager.update(
                        params.session_key,
                        plan_steps=remaining_steps,
                    )
                    session.plan_steps = remaining_steps
                    logger.info(f"plan step consumed: session={session.session_id} kind={consumed.get('kind')} remaining={len(remaining_steps)}")

                    # completion boundary: no steps means close active task by default.
                    if not remaining_steps and getattr(session, "active_task_id", None):
                        await session_manager.update(
                            params.session_key,
                            active_task_id=None,
                            task_plan={},
                            targets=[],
                            completed_steps=[],
                        )
                        session.active_task_id = None
                        session.task_plan = {}
                        session.targets = []
                        session.completed_steps = []
            
            # === Step 6: Completion guard ===
            if execution_context.target_path:
                task_type = completion_guard.classify_task_type(params.prompt)
                verification = completion_guard.verify(
                    task_type=task_type,
                    task_goal=params.prompt,
                    execution_result=tool_results[0] if tool_results else None,
                    target_path=execution_context.target_path,
                )
                
                if not verification.verified:
                    logger.warning(
                        f"CompletionGuard blocked: status={verification.status.value} "
                        f"missing={verification.missing}"
                    )
                    # 记录失败
                    repair_manager.record_failure(
                        task_id=str(uuid.uuid4()),
                        session_id=session_id,
                        user_id=params.user_id or "unknown",
                        task_goal=params.prompt,
                        failure_reason=", ".join(verification.missing),
                    )
            
            # === Step 7: Produce reply ===
            reply_text = cognition_result.get("reply_text", "")
            
            # task turn 最低回复保障：避免“首条任务无回应”
            if (task_turn_kind in {"new_task", "follow_up"}) and (not reply_text or not reply_text.strip()):
                reply_text = "我收到了，正在处理这条请求。"

            # 检查静默回复
            if reply_text.strip() == NO_REPLY:
                result.reply_text = None
            else:
                result.reply_text = reply_text

            if request_id:
                result.request_id = request_id
                # stale reply suppression (runtime-level): if a newer task request exists, do not emit old reply.
                latest_task_req = registry.get_latest_task_request(session_key)
                if latest_task_req and latest_task_req.request_id != request_id:
                    result.reply_text = None
                req_obj = registry.requests.get(request_id)
                if req_obj:
                    final_status = "completed" if result.reply_text else "waiting_input"
                    registry.update_status(request_id, final_status)
                    if result.reply_text:
                        registry.mark_reply_sent(request_id)
            
            # 发射回复事件
            if result.reply_text:
                emit_reply_event(
                    content=result.reply_text,
                    run_id=run_id,
                    session_id=session_id,
                    is_final=True,
                )
            
            # === Step 8: Update session ===
            await session_manager.update(
                session_key=session_key,
                last_intent=cognition_result.get("primary_mode"),
            )
            
            # 标记完成
            result.status = RunStatus.COMPLETED
            
        except asyncio.CancelledError:
            result.status = RunStatus.ABORTED
            result.error = "Run was cancelled"
            raise
        
        except Exception as e:
            result.status = RunStatus.FAILED
            result.error = str(e)
            logger.error(f"runEmbeddedEgoCoreAgent failed: {e}\n{traceback.format_exc()}")
        
        finally:
            # 计算持续时间
            end_time = datetime.now(timezone.utc)
            result.ended_at = end_time
            result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # 发射 end 事件
            emit_lifecycle_event(
                phase=LifecyclePhase.END,
                run_id=run_id,
                session_id=session_id,
                data={
                    "status": result.status.value,
                    "duration_ms": result.duration_ms,
                },
            )
            
            # 清理订阅
            event_bus.unsubscribe(run_id)
            
            logger.info(
                f"runEmbeddedEgoCoreAgent: completed run={run_id} "
                f"status={result.status.value} duration={result.duration_ms}ms"
            )
        
        return result
    
    # 加入队列执行
    task_id = await lane_manager.enqueue(session_key, execute)
    
    # 等待完成
    final_task = await lane_manager.wait_for_task(
        task_id,
        timeout_ms=params.timeout_ms,
    )
    
    if final_task:
        if final_task.status == "completed":
            return final_task.result
        elif final_task.status == "failed":
            result.status = RunStatus.FAILED
            result.error = final_task.error
            return result
        elif final_task.status == "cancelled":
            result.status = RunStatus.ABORTED
            return result
    
    # 超时
    result.status = RunStatus.TIMEOUT
    result.error = "Run timed out"
    return result


async def _run_cognition_core(
    params: EgoCoreRunParams,
    execution_context: ExecutionContext,
    session: Any,
    turn_index: int,
) -> Dict[str, Any]:
    """
    运行认知核心 (OpenEmotion 注入) + EgoCore LLM 决策层

    边界：
    - OpenEmotion 只提供主体读出 / memory / appraisal / tendency / policy_hint
    - EgoCore 使用这些结构化读出做最终 runtime 决策
    - LLM 只允许输出: reply / act / ask
    """
    from app.openemotion.subject_adapter import get_subject_adapter
    from app.openemotion_adapter.event_builder import default_event_builder

    subject_adapter = get_subject_adapter()

    event_v1 = default_event_builder.build_from_execution_context(
        execution_context=execution_context,
        content=params.prompt,
        metadata={
            "channel": params.channel,
            "trigger": params.trigger,
            "turn_index": turn_index,
        }
    )

    try:
        cycle_result = subject_adapter.cycle(event_v1)
        result_data = cycle_result.get("result", {})

        # non-task turn context guard:
        # 普通寒暄/非任务消息不复用旧 task/artifact 执行上下文，但最终回复仍交给 LLM 自然生成。
        if is_small_talk(params.prompt):
            session_artifact = None

        # 如果 session 里已经有正式 plan_steps，优先由宿主计划驱动 act，而不是让模型重想一遍
        if getattr(session, "plan_steps", None):
            planned = _decision_from_task_plan(params.prompt, session)
            if planned:
                return {
                    "primary_mode": "planned_task",
                    "runtime_route": planned.get("decision", "reply"),
                    "reply_text": planned.get("reply_text", ""),
                    "needs_tool_execution": planned.get("decision") == "act" and bool(planned.get("tool_calls")),
                    "tool_calls": planned.get("tool_calls", []),
                    "interpretation": result_data,
                    "decision_payload": planned,
                }

        decision = await _decide_with_llm(
            user_input=params.prompt,
            execution_context=execution_context,
            openemotion_result=result_data,
            session_artifact={
                "path": getattr(session, "active_artifact_path", None),
                "kind": getattr(session, "artifact_kind", None),
                "active_focus": getattr(session, "active_focus", None),
                "default_edit_target": getattr(session, "default_edit_target", None),
                "artifact_summary": getattr(session, "artifact_summary", {}),
                "last_known_state": getattr(session, "last_known_state", {}),
                "last_tool_result": getattr(session, "last_tool_result", {}),
            },
        )

        runtime_route = decision.get("decision", "reply")
        primary_mode = result_data.get("result_type", "interpretation")
        reply_text = decision.get("reply_text", "")
        tool_calls = decision.get("tool_calls", [])

        return {
            "primary_mode": primary_mode,
            "runtime_route": runtime_route,
            "reply_text": reply_text,
            "needs_tool_execution": runtime_route == "act" and bool(tool_calls),
            "tool_calls": tool_calls,
            "interpretation": result_data,
            "decision_payload": decision,
        }

    except Exception as e:
        logger.error(f"Cognition core failed: {e}")
        return {
            "primary_mode": "fallback",
            "runtime_route": "reply",
            "reply_text": "我在。你刚刚那句我没处理好，你再发一次我继续。",
            "needs_tool_execution": False,
            "error": str(e),
        }


def _decision_from_task_plan(user_input: str, session: Any) -> Optional[Dict[str, Any]]:
    plan_steps = getattr(session, "plan_steps", []) or []
    targets = getattr(session, "targets", []) or []
    if not plan_steps:
        return None
    step = plan_steps[0]
    kind = step.get("kind")
    if kind == "create_artifacts":
        targets = step.get("targets", [])
        edits = [{
            "target_path": t.get("path"),
            "scope": "primary_text",
            "property": "text_content",
            "operation": "set",
            "value": t.get("content"),
        } for t in targets]
        return {"decision": "act", "reply_text": "", "tool_calls": [{
            "name": "html_skill",
            "args": {
                "action": "create_artifact",
                "artifact_type": "html",
                "targets": targets,
                "edits": edits,
            }
        }], "reason": "planned_create_artifacts"}
    if kind == "batch_edit_artifacts":
        return {"decision": "act", "reply_text": "", "tool_calls": [{
            "name": "html_skill",
            "args": {
                "action": "batch_edit_artifacts",
                "artifact_type": "html",
                "targets": step.get("targets", []),
                "edits": step.get("edits", []),
            }
        }], "reason": "planned_batch_edit_artifacts"}
    if kind == "inspect_artifact":
        return {"decision": "act", "reply_text": "", "tool_calls": [{
            "name": "html_skill",
            "args": {
                "action": "inspect_artifact",
                "artifact_type": "html",
                "targets": step.get("targets", []),
                "edits": [],
            }
        }], "reason": "planned_inspect_artifact"}
    return None


async def _decide_with_llm(
    user_input: str,
    execution_context: ExecutionContext,
    openemotion_result: Dict[str, Any],
    session_artifact: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """EgoCore 最终决策层：只允许 reply / act / ask。"""
    from app.config import load_config, get_config, ConfigError
    from app.llm_client import get_llm_client

    try:
        get_config()
    except Exception:
        load_config(validate=False)

    system_prompt = """你是 EgoCore 的运行时决策层。
你的唯一任务是根据用户输入、运行时上下文、以及 OpenEmotion 的结构化读出，输出 JSON 决策。

硬规则：
1. 你只能输出三类 decision: reply / act / ask
2. reply: 直接回复用户，必须提供简短自然的 reply_text
3. ask: 信息不足时追问，必须提供简短自然的 reply_text
4. act: 只有当用户明确要求执行现实动作，且适合交给工具边界处理时才允许
5. 绝不输出解释性散文、markdown、额外字段说明
6. 不要暴露内部词：route/mode/probe/repair/testing
7. 输出必须是单个 JSON 对象

记忆/上下文规则（非常重要）：
- execution_context.conversation_context.recent_messages 是当前会话的真实上下文证据
- 如果 recent_messages 里已经有用户明确表达过偏好/约束/目标，就不要再说“这是对话开始/我还不知道/我还没有记录”
- 用户问“你记得我的偏好吗”这类问题时，优先根据 recent_messages 直接确认已知偏好
- 只有在 recent_messages 和 openemotion 都没有相关证据时，才允许 ask

JSON 格式：
{
  "decision": "reply" | "act" | "ask",
  "reply_text": "...",
  "tool_calls": [{"name": "...", "args": {...}}],
  "reason": "简短内部理由"
}

默认偏好：
- 普通聊天/寒暄/记忆确认 => reply
- 信息缺失 => ask
- 明确执行请求（读文件、列目录等）=> act
- 若不确定，选 reply 而不是 act
"""

    recent_messages = execution_context.conversation_context.recent_messages or []

    def _extract_preference_from_recent_messages(msgs):
        for m in reversed(msgs):
            if m.get("role") != "user":
                continue
            c = (m.get("content") or "").strip()
            for prefix in ["记住我喜欢", "我喜欢", "我的偏好是"]:
                if prefix in c:
                    idx = c.find(prefix)
                    pref = c[idx + len(prefix):].strip(" ：:，,。.!！?？")
                    if pref:
                        return pref
        return None

    explicit_pref = _extract_preference_from_recent_messages(recent_messages)

    # 宿主侧确定性规则：显式偏好确认，不交给模型瞎猜
    if user_input.strip() in ["你记得我的偏好吗?", "你记得我的偏好吗？", "记得我的偏好吗?", "记得我的偏好吗？"] and explicit_pref:
        return {
            "decision": "reply",
            "reply_text": f"记得。你喜欢{explicit_pref}，我会按这个风格和你交流。",
            "tool_calls": [],
            "reason": "host_preference_confirmation",
        }

    # 宿主侧 follow-up resolver：基于活跃产物和属性级状态做解析
    followup_intent = resolve_follow_up(user_input, session_artifact or {})
    if followup_intent:
        if followup_intent.intent == "inspect_artifact":
            return {
                "decision": "act",
                "reply_text": "",
                "tool_calls": [{
                    "name": "html_artifact",
                    "args": {
                        "path": followup_intent.target_path,
                        "intent": followup_intent.intent,
                    }
                }],
                "reason": "host_followup_inspect_artifact",
            }
        if followup_intent.intent == "edit_artifact_property":
            return {
                "decision": "act",
                "reply_text": "",
                "tool_calls": [{
                    "name": "html_artifact",
                    "args": {
                        "path": followup_intent.target_path,
                        "intent": followup_intent.intent,
                        "target_scope": followup_intent.target_scope,
                        "property": followup_intent.property_name,
                        "operation": followup_intent.operation,
                        "value": followup_intent.value,
                    }
                }],
                "reason": "host_followup_edit_property",
            }

    # 宿主侧最小 create_artifact 规则：html 页面创建
    normalized = user_input.strip()
    if ("html" in normalized.lower() and ("创建" in normalized or "新建" in normalized)):
        import re
        m = re.search(r'在\s*([^\s]+?)\s*(文件夹|目录)?下', normalized)
        base_dir = m.group(1) if m else None
        if base_dir:
            named_content_match = re.search(r'文字内容是\s*([A-Za-z0-9_\-]+)\s*的?html页面', normalized, re.I)
            file_match = re.search(r'创建(?:一个)?\s*([\w\-]+)\s*的?html页面', normalized, re.I)
            text_match = re.search(r'文字内容是\s*([A-Za-z0-9_\-]+)', normalized, re.I)
            title_text = (text_match.group(1).rstrip('的').strip() if text_match else ('Hello, World!' if 'hello world' in normalized.lower() else None))
            if named_content_match:
                filename = f"{named_content_match.group(1).rstrip('的')}.html"
            elif file_match:
                filename = f"{file_match.group(1).rstrip('的')}.html"
            elif text_match:
                filename = f"{text_match.group(1).rstrip('的')}.html"
            else:
                filename = "index.html"
            if title_text is None and 'hello world' in normalized.lower():
                title_text = 'Hello, World!'
            if title_text:
                return {
                    "decision": "act",
                    "reply_text": "",
                    "tool_calls": [{
                        "name": "html_artifact",
                        "args": {
                            "intent": "create_artifact",
                            "path": f"{base_dir.rstrip('/')}/{filename}",
                            "target_scope": "primary_text",
                            "property": "text_content",
                            "operation": "set",
                            "value": title_text,
                        }
                    }],
                    "reason": "host_create_html_artifact",
                }

    payload = {
        "user_input": user_input,
        "execution_context": execution_context.to_dict(),
        "openemotion": {
            "self_model_delta": openemotion_result.get("self_model_delta"),
            "memory_update": openemotion_result.get("memory_update"),
            "policy_hint": openemotion_result.get("policy_hint"),
            "response_tendency": openemotion_result.get("response_tendency"),
            "confidence": openemotion_result.get("confidence"),
            "reflection_note": openemotion_result.get("reflection_note"),
            "appraisal_state_delta": openemotion_result.get("appraisal_state_delta"),
        },
    }

    client = get_llm_client()
    resp = await asyncio.to_thread(
        client.generate,
        json.dumps(payload, ensure_ascii=False, indent=2),
        system_prompt,
        temperature=0.2,
        max_tokens=500,
        timeout=45,
    )
    content = (resp.content or '').strip()

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        parsed = json.loads(cleaned[start:end+1])
    except Exception:
        logger.warning(f"LLM decision parse failed, fallback to reply: {content[:400]}")
        parsed = {
            "decision": "reply",
            "reply_text": "我在。你继续说。",
            "tool_calls": [],
            "reason": "parse_fallback",
        }

    decision = parsed.get("decision", "reply")
    if decision not in ("reply", "act", "ask"):
        decision = "reply"
        parsed["decision"] = "reply"
    if decision in ("reply", "ask") and not parsed.get("reply_text"):
        parsed["reply_text"] = "我在。你继续说。"
    if decision != "act":
        parsed["tool_calls"] = []
    return parsed


async def _ensure_tools_ready() -> None:
    from app.config import load_config, get_config
    try:
        cfg = get_config()
    except Exception:
        cfg = load_config(validate=False)
    registry = get_registry()
    if registry.list_tools():
        return
    setup_tools(cfg.get("tools", {}) if hasattr(cfg, "get") else {})


async def _execute_tools(
    params: EgoCoreRunParams,
    cognition_result: Dict[str, Any],
    event_bus,
) -> List[Dict[str, Any]]:
    """执行结构化 tool_calls，禁止自由 shell 文本直通。"""
    await _ensure_tools_ready()
    tool_calls = cognition_result.get("tool_calls", []) or []
    results: List[Dict[str, Any]] = []

    # 只开放最小闭环：file(list/read/write/mkdir/exists)
    allowed_tools = {"file", "file_read", "file_write", "list_dir", "html_artifact", "html_skill"}

    for i, call in enumerate(tool_calls):
        raw_name = call.get("name", "")
        args = call.get("args", {}) or {}
        tool_name = raw_name
        tool_params = args.copy()

        # html skill（artifact skill contract v1）
        if raw_name == "html_skill":
            def _loader(path):
                rr = execute_tool("file", {"operation": "read", "path": path}, None, f"step_{i}_skill_read")
                return rr.success, rr.output if rr.success else rr.error
            def _writer(path, content):
                wr = execute_tool("file", {"operation": "write", "path": path, "content": content}, None, f"step_{i}_skill_write")
                return wr.success, wr.error
            normalized_edits = [_normalize_artifact_edit(e) for e in args.get("edits", [])]
            req = ArtifactSkillRequest(
                action=args.get("action"),
                artifact_type=args.get("artifact_type", "html"),
                targets=args.get("targets", []),
                edits=[ArtifactEdit(**e) for e in normalized_edits],
            )
            skill_result = execute_html_skill(req, _loader, _writer)
            trd = {
                "success": skill_result.success,
                "tool_name": "html_skill",
                "raw_name": raw_name,
                "params": {**args, "edits": normalized_edits},
                "output": skill_result.summary,
                "metadata": skill_result.to_dict(),
            }
            results.append(trd)
            continue

        # html artifact 专用动作（通用 artifact edit pipeline, v1）
        if raw_name == "html_artifact":
            path = args.get("path")
            intent = args.get("intent")
            if intent == "create_artifact":
                text_value = args.get("value") or "Hello, World!"
                content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{text_value}</title>
</head>
<body>
  <h1>{text_value}</h1>
</body>
</html>
'''
                tool_name = 'file'
                tool_params = {"operation":"write","path":path,"content":content}
            else:
                read_result = await asyncio.to_thread(execute_tool, "file", {"operation":"read","path":path}, None, f"step_{i}_read")
                if not read_result.success:
                    trd = read_result.to_dict(); trd["tool_name"]='file'; trd["raw_name"]=raw_name; trd["params"]={"operation":"read","path":path}
                    results.append(trd)
                    continue
                content = read_result.output
                if intent == "inspect_artifact":
                    tool_name = 'file'
                    tool_params = {"operation":"read","path":path}
                elif intent == "edit_artifact_property":
                    edited = apply_html_edit(
                        path=path,
                        content=content,
                        scope=args.get("target_scope") or 'primary_text',
                        property_name=args.get("property"),
                        operation=args.get("operation"),
                        value=args.get("value"),
                    )
                    tool_name = 'file'
                    tool_params = {"operation":"write","path":path,"content":edited["content"]}

        # 规范化别名到 file 工具
        elif raw_name == "file_read":
            tool_name = "file"
            tool_params = {"operation": "read", **args}
        elif raw_name == "file_write":
            tool_name = "file"
            tool_params = {"operation": "write", **args}
        elif raw_name == "list_dir":
            tool_name = "file"
            tool_params = {"operation": "list", **args}

        if raw_name not in allowed_tools and tool_name not in {"file"}:
            results.append({
                "success": False,
                "tool_name": raw_name,
                "error": f"Tool not allowed in minimal loop: {raw_name}",
                "status": "denied",
            })
            continue

        emit_tool_event(
            tool_name=tool_name,
            tool_args=tool_params,
            status="start",
        )
        if tool_name == "file" and tool_params.get("operation") == "write" and tool_params.get("content_template") == "hello_world_html":
            path = tool_params.get("path", "index.html")
            title = "Hello World"
            body = "Hello, World!"
            tool_params = {
                "operation": "write",
                "path": path,
                "content": f'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>{title}</title>\n</head>\n<body>\n  <h1>{body}</h1>\n</body>\n</html>\n',
            }
        tr = await asyncio.to_thread(execute_tool, tool_name, tool_params, None, f"step_{i}")
        trd = tr.to_dict()
        trd["tool_name"] = tool_name
        trd["raw_name"] = raw_name
        trd["params"] = tool_params
        results.append(trd)
        emit_tool_event(
            tool_name=tool_name,
            tool_args=tool_params,
            status="end" if tr.success else "error",
            output=trd.get("output"),
            error=trd.get("error"),
            duration_ms=int(trd.get("execution_time_ms", 0)),
        )
    return results


async def _evaluate_after_tools(
    user_input: str,
    execution_context: ExecutionContext,
    openemotion_result: Dict[str, Any],
    tool_results: List[Dict[str, Any]],
    expected_target: Optional[str] = None,
) -> Dict[str, Any]:
    """宿主侧确定性 post-tool 评估，避免 follow-up 场景再被 LLM 超时打断。"""
    first = tool_results[0] if tool_results else {}
    params = first.get("params") or {}
    output = first.get("output") or ""

    if first.get("success"):
        if first.get("tool_name") == "html_skill":
            meta = first.get("metadata") or {}
            observations = meta.get("observations", [])
            contract = CompletionContract(
                effect_type="artifact_style_change",
                expected_target=expected_target,
                required_observations=["target_path", "applied_edit", "current_state"],
                verifier_name="html_effect_verifier",
            )
            verification = HtmlEffectVerifier().verify(contract, {"observations": observations})
            verified_effect = verification.passed
            if observations:
                parts = []
                for obs in observations:
                    state = obs.get("current_state") or obs.get("state", {})
                    path = obs.get("target_path") or obs.get("path")
                    desc = [path] if path else []
                    if state.get("font_size_px"):
                        desc.append(f"字体 {state.get('font_size_px')}px")
                    if state.get("background_color"):
                        desc.append(f"背景 {state.get('background_color')}")
                    if state.get("text_color"):
                        desc.append(f"文字 {state.get('text_color')}")
                    if state.get("text"):
                        desc.append(f"内容 {state.get('text')}")
                    parts.append('，'.join(desc))
                if meta.get('action') != 'inspect_artifact' and (not meta.get('completed_steps') or not verified_effect):
                    reply = "我这一步没成功：还没有拿到目标文件的可验证变更结果。你要我继续重试吗？"
                else:
                    reply = '已经处理好了。' if meta.get('action') != 'inspect_artifact' else ''
                    reply += '；'.join(parts)
            else:
                reply = first.get('output') or '我这一步没成功：没有拿到可验证结果。'
            return {
                "primary_mode": "post_tool_evaluation",
                "runtime_route": "reply",
                "reply_text": reply,
                "needs_tool_execution": False,
                "tool_calls": [],
                "interpretation": openemotion_result,
                "decision_payload": {"decision":"reply","reply_text":reply},
            }
        path = params.get("path")
        if params.get("operation") == "write":
            reply = "我这一步没成功：只有文件写入还不够，我还需要拿到目标文件的可验证变更结果。你要我继续吗？"
            return {
                "primary_mode": "post_tool_evaluation",
                "runtime_route": "ask",
                "reply_text": reply,
                "needs_tool_execution": False,
                "tool_calls": [],
                "interpretation": openemotion_result,
                "decision_payload": {"decision":"ask","reply_text":reply},
            }
        if params.get("operation") == "read":
            # inspect 场景：给出可见状态摘要
            facts = []
            if path:
                facts.append(f"文件是 {path}")
            if "background-color: #0000FF" in output:
                facts.append("背景已经是蓝色")
            if "color: #FFFFFF" in output:
                facts.append("文字颜色已经是白色")
            if "Hello, World!" in output or "Hello World" in output:
                facts.append("hello world 文字还在")
            reply = "，".join(facts) if facts else "我看过了，文件内容已经读到了。"
            return {
                "primary_mode": "post_tool_evaluation",
                "runtime_route": "reply",
                "reply_text": reply,
                "needs_tool_execution": False,
                "tool_calls": [],
                "interpretation": openemotion_result,
                "decision_payload": {"decision":"reply","reply_text":reply},
            }

    reply = f"我这一步没成功：{first.get('error','未知错误')}。你要我换一种方式继续吗？"
    return {
        "primary_mode": "post_tool_evaluation",
        "runtime_route": "ask",
        "reply_text": reply,
        "needs_tool_execution": False,
        "tool_calls": [],
        "interpretation": openemotion_result,
        "decision_payload": {"decision":"ask","reply_text":reply},
    }


def _summarize_artifact_from_tool_result(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    params = tool_result.get("params") or {}
    path = params.get("path")
    output = tool_result.get("output") or ""
    if path and str(path).endswith('.html'):
        try:
            return inspect_html_state(path, output)
        except Exception:
            pass
    return {
        "path": path,
        "kind": None,
        "focus": None,
        "state": {},
    }


async def run_agent(
    prompt: str,
    session_key: str,
    user_id: Optional[str] = None,
    channel: str = "cli",
    **kwargs,
) -> EgoCoreRunResult:
    """
    便捷函数：运行 agent
    
    Args:
        prompt: 用户输入
        session_key: 会话 key
        user_id: 用户 ID
        channel: 渠道
        **kwargs: 其他参数
    
    Returns:
        EgoCoreRunResult
    """
    session_manager = get_session_manager()
    session = await session_manager.get_or_create(session_key, channel)
    
    params = EgoCoreRunParams(
        session_id=session.session_id,
        session_key=session_key,
        run_id=create_run_id(),
        prompt=prompt,
        user_id=user_id,
        channel=channel,
        **kwargs,
    )
    
    return await runEmbeddedEgoCoreAgent(params)


async def run_agent_sync(
    prompt: str,
    session_key: str,
    **kwargs,
) -> str:
    """
    同步风格运行 agent (返回回复文本)
    
    用于简单场景，直接返回回复文本。
    """
    result = await run_agent(prompt, session_key, **kwargs)
    return result.reply_text or ""
