"""
Social Chat Handler v2 - EgoCore

处理 social/chat 类型消息的新链路。

v2 改进：
- 整合 RelationshipContext，支持关系连续性
- 整合 StyleProfile，支持风格一致性
- 使用 VerbalizerV3

v2.1 改进 (2026-03-19):
- 注入 ContextAssembler，保证执行前上下文完整
- 整合 RepairContextManager，追踪失败任务
- 整合 CompletionGuard，验证任务完成

链路：
用户输入
-> ContextAssembler (NEW: 组装完整执行上下文)
-> EventNormalizer
-> InteractionEventEnvelope
-> SubjectAdapter
-> SubjectInterpretationResult
-> RuntimeDecider
-> RuntimeDecisionEnvelope
-> ResponseContractBuilder
-> OutwardResponsePackage
-> VerbalizerV3 (关系感知 + 风格条件化)
-> 自然语言回复

关键原则：
- 主体解释权归 OpenEmotion
- 现实裁决权归 EgoCore
- 不能只改欢迎词文案或只补 regex
- 关系连续性优先于模板
- 没有上下文不允许直接规划或宣称完成 (NEW)
"""

import logging
from typing import Optional, Dict, Any

from egocore.contracts.interaction_event_envelope_v1 import InteractionEventEnvelope
from egocore.contracts.runtime_decision_envelope_v1 import RuntimeDecisionEnvelope
from egocore.contracts.outward_response_package_v1 import OutwardResponsePackage

from app.interaction.event_normalizer import get_event_normalizer, EventNormalizer
from app.openemotion.subject_adapter import get_subject_adapter, SubjectAdapter
from app.openemotion_adapter.event_builder import default_event_builder
from app.openemotion_adapter.result_consumer import default_result_consumer
from app.response.verbalizer_v3 import VerbalizerV3
from app.response.question_verbalizer import QuestionVerbalizer, is_short_question
from app.response.relationship_context import (
    RelationshipContext,
    RelationshipContextManager,
    get_relationship_context_manager,
    RelationshipEvent,
)
from app.response.style_profile import (
    StyleProfile,
    StyleProfileManager,
    get_style_profile_manager,
)
# v2.1: ContextAssembler + RepairContextManager
from app.runtime.context_assembler import (
    ContextAssembler,
    get_context_assembler,
    assemble_execution_context,
)
from app.runtime.repair_context_manager import (
    RepairContextManager,
    get_repair_context_manager,
)

logger = logging.getLogger(__name__)


class SocialChatHandlerV2:
    """
    Social/Chat 消息处理器 v2
    
    实现完整的"主体解释 -> 现实裁决 -> 回复生成"链路。
    
    v2 新增：
    - 关系上下文管理
    - 风格配置管理
    - 使用 VerbalizerV3
    
    v2.1 新增 (2026-03-19):
    - ContextAssembler 执行上下文注入
    - RepairContextManager 失败追踪
    - 强制规则: 没有上下文不允许直接规划
    """
    
    def __init__(
        self,
        normalizer: Optional[EventNormalizer] = None,
        subject_adapter: Optional[SubjectAdapter] = None,
        relationship_manager: Optional[RelationshipContextManager] = None,
        style_manager: Optional[StyleProfileManager] = None,
        context_assembler: Optional[ContextAssembler] = None,
        repair_manager: Optional[RepairContextManager] = None,
    ):
        self.normalizer = normalizer or get_event_normalizer()
        self.subject_adapter = subject_adapter or get_subject_adapter()
        self.relationship_manager = relationship_manager or get_relationship_context_manager()
        self.style_manager = style_manager or get_style_profile_manager()
        # v2.1
        self.context_assembler = context_assembler or get_context_assembler()
        self.repair_manager = repair_manager or get_repair_context_manager()
    
    def _get_session_id(self, chat_id: int, user_id: int) -> str:
        """生成会话 ID"""
        return f"chat_{chat_id}_user_{user_id}"
    
    def _map_primary_mode_to_event(self, primary_mode: str) -> str:
        """将主体解释的 primary_mode 映射到关系事件类型"""
        mapping = {
            "greeting": RelationshipEvent.GREETING.value,
            "testing": RelationshipEvent.TESTING.value,
            "status_probe": RelationshipEvent.STATUS_PROBE.value,
            "task_request": RelationshipEvent.TASK_REQUEST.value,
            "affective_probe": RelationshipEvent.AFFECTIVE_PROBE.value,
            "gratitude": RelationshipEvent.GRATITUDE.value,
            "frustration": RelationshipEvent.FRUSTRATION.value,
            "chitchat": RelationshipEvent.CHITCHAT.value,
        }
        return mapping.get(primary_mode, RelationshipEvent.CHITCHAT.value)
    
    def handle(
        self,
        user_input: str,
        user_id: int,
        chat_id: int,
        username: Optional[str] = None,
        recent_messages: Optional[list] = None,
        active_task: Optional[Dict[str, Any]] = None,
        turn_index: int = 0,
    ) -> Dict[str, Any]:
        """
        处理 social/chat 消息
        
        Args:
            user_input: 用户输入
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            username: 用户名
            recent_messages: 最近消息列表
            active_task: 活动任务
            turn_index: 会话轮次索引
        
        Returns:
            {
                "success": bool,
                "message": str,  # 回复文本
                "data": dict,    # 诊断数据
            }
        """
        session_id = self._get_session_id(chat_id, user_id)
        
        # === Step 0: 获取关系上下文和风格配置 ===
        relationship_ctx = self.relationship_manager.get_context(session_id)
        style_profile = self.style_manager.get_profile(session_id)
        
        # === Step 0.5 (NEW v2.1): 检测用户反馈中的失败指示 ===
        failure_record = self.repair_manager.detect_user_feedback(
            user_input=user_input,
            session_id=session_id,
            user_id=str(user_id),
        )
        if failure_record:
            logger.info(
                f"Detected failure feedback: task={failure_record.task_id}, "
                f"feedback={user_input[:50]}"
            )
        
        # === Step 0.6 (NEW v2.1): 组装完整执行上下文 ===
        execution_context = self.context_assembler.assemble(
            user_input=user_input,
            session_id=session_id,
            user_id=str(user_id),
            chat_id=str(chat_id),
            active_task=active_task,
        )
        
        logger.debug(
            f"ExecutionContext assembled: "
            f"has_task={execution_context.task_context.active_task_id is not None}, "
            f"repair_needed={execution_context.repair_context.has_pending_repair}, "
            f"target_path={execution_context.target_path}"
        )
        
        # === Step 1: 构建信封 ===
        envelope = self.normalizer.from_telegram_context(
            user_input=user_input,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            recent_messages=recent_messages,
            active_task=active_task,
        )
        
        logger.debug(f"Envelope created: {envelope.envelope_id}")
        
        # === Step 2: Cycle Core v1 - 新正式链路 (v2.1: 使用完整上下文) ===
        # context_assembler -> event_builder -> event_v1 -> subject_adapter.cycle() -> result_v1 -> result_consumer
        event_v1 = default_event_builder.build_from_execution_context(
            execution_context=execution_context,
            content=user_input,
            metadata={
                "chat_id": chat_id,
                "username": username,
                "has_active_task": active_task is not None,
                "has_pending_repair": execution_context.repair_context.has_pending_repair,
            }
        )
        
        cycle_result = self.subject_adapter.cycle(event_v1)
        
        # 消费 result_v1
        if cycle_result.get("status") == "ok":
            result_v1 = cycle_result.get("result", {})
            consumed = default_result_consumer.consume(result_v1)
            
            # 提取关键字段
            primary_mode = result_v1.get("interaction_interpretation", {}).get("primary_mode", "unknown")
            degraded = not consumed.stable

            # 把 response_tendency 放进 context，供 verbalizer 消费
            response_tendency = consumed.response_tendency
            policy_hint = consumed.policy_hint
            
            # 构造兼容 interpretation 格式的数据（用于后续链路）
            interpretation = {
                "result_id": result_v1.get("result_id"),
                "schema_version": result_v1.get("schema_version", "v1"),
                "interaction_interpretation": result_v1.get("interaction_interpretation", {}),
                "social_signal": result_v1.get("social_signal", {}),
                "relationship_implication": result_v1.get("relationship_implication", {}),
                "appraisal_state_delta": result_v1.get("appraisal_state_delta", {}),
                "response_tendency": result_v1.get("response_tendency", {}),
                "expressive_intent_candidate": result_v1.get("expressive_intent_candidate", {}),
                "reply_urge": result_v1.get("reply_urge", {}),
                "reflection_note": result_v1.get("reflection_note", {}),
                "policy_hint": result_v1.get("policy_hint", {}),
                "stability": {
                    "degraded": degraded,
                    "self_model_stable": consumed.stable,
                    "memory_integrity": consumed.memory_integrity,
                    "policy_consistent": consumed.policy_consistent,
                }
            }
            
            logger.info(
                f"Cycle Core v1: event={event_v1['event_id']}, "
                f"trace={cycle_result.get('trace_id')}, "
                f"primary_mode={primary_mode}, "
                f"memory_update={consumed.memory_update is not None}, "
                f"policy_hint={consumed.policy_hint is not None}"
            )
        else:
            # 降级到旧 interpret() 链路
            logger.warning(f"Cycle failed, falling back to interpret(): {cycle_result.get('error')}")
            interpretation = self.subject_adapter.interpret(envelope)
            primary_mode = interpretation.get("interaction_interpretation", {}).get("primary_mode", "unknown")
            degraded = interpretation.get("stability", {}).get("degraded", False)
        
        # DEBUG: 记录详细解释信息
        logger.info(
            f"DEBUG interpretation: primary_mode={primary_mode}, "
            f"repair_needed={interpretation.get('relationship_implication', {}).get('repair_needed')}, "
            f"response_plan will be checked"
        )
        
        # === Step 3: 运行时决策 ===
        decision = RuntimeDecisionEnvelope.from_subject_interpretation(
            envelope_id=envelope.envelope_id,
            result_id=interpretation.get("result_id", ""),
            interpretation=interpretation,
            has_active_task=active_task is not None,
            safety_context=None,  # chat 消息通常不需要安全检查
        )
        
        logger.debug(
            f"Decision: route={decision.runtime_route.value}, "
            f"should_reply={decision.should_reply}"
        )
        
        # === Step 4: 构建回复包 ===
        package = OutwardResponsePackage.from_decision(
            decision=decision.to_dict(),
            interpretation=interpretation,
            task_context=active_task,
        )
        
        # === Step 5: 生成回复 ===
        # P1-C.1: 短问句优先使用 QuestionVerbalizer
        reply = None
        if is_short_question(user_input):
            question_verbalizer = QuestionVerbalizer(
                relationship_context=relationship_ctx,
                style_profile=style_profile,
            )
            reply = question_verbalizer.verbalize(user_input, recent_messages)
            logger.info(f"Using QuestionVerbalizer for short question: '{user_input}' -> '{reply}'")

        # 非短问句或 QuestionVerbalizer 未生成回复，使用 VerbalizerV3
        if reply is None:
            verbalizer = VerbalizerV3(
                relationship_context=relationship_ctx,
                style_profile=style_profile,
            )

            # 构造 context，包含 response_tendency 和 policy_hint
            verbalizer_context = {
                "active_task": active_task,
                "turn_index": turn_index,
            }
            if response_tendency:
                verbalizer_context["response_tendency"] = response_tendency
            if policy_hint:
                verbalizer_context["policy_hint"] = policy_hint

            reply = verbalizer.verbalize(
                package,
                context=verbalizer_context,
                interpretation=interpretation,
            )
        
        # === Step 6: 更新关系上下文 ===
        event_type = self._map_primary_mode_to_event(primary_mode)
        
        # 判断影响
        impact = "neutral"
        ri = interpretation.get("relationship_implication", {})
        if ri.get("interaction_effect") == "positive":
            impact = "positive"
        elif ri.get("interaction_effect") == "negative":
            impact = "negative"
        
        # 更新关系上下文
        self.relationship_manager.update_context(
            session_id=session_id,
            event_type=event_type,
            user_input=user_input[:50],
            agent_response=reply[:50],
            impact=impact,
        )
        
        # 如果是关系修复，标记修复状态
        if primary_mode == "affective_probe":
            relationship_ctx = self.relationship_manager.get_context(session_id)
            if ri.get("repair_needed"):
                # 修复已处理
                relationship_ctx.mark_repair_resolved()
        
        # === Step 7: 更新风格配置 ===
        self.style_manager.adjust_for_context(session_id, relationship_ctx)
        
        # 检查避免列表
        avoid_list = package.tone_bounds.avoid_tones
        if avoid_list:
            for avoid in avoid_list:
                if avoid.lower() in reply.lower():
                    logger.warning(f"Reply contains avoided content: {avoid}")
        
        # === Build diagnostic data with full memory/consumed exposure ===
        diagnostic_data = {
            "envelope_id": envelope.envelope_id,
            "result_id": interpretation.get("result_id"),
            "decision_id": decision.decision_id,
            "primary_mode": primary_mode,
            "runtime_route": decision.runtime_route.value,
            "degraded": degraded,
            "relationship": {
                "temperature": relationship_ctx.conversation_temperature,
                "social_arc": relationship_ctx.current_social_arc,
                "turn_count": relationship_ctx.turn_count,
            },
            # C1: Expose memory_update for WS_C1 verification
            "memory_update": {
                "event_stored": consumed.memory_update.get("event_stored", False) if consumed.memory_update else False,
                "narrative_created": consumed.memory_update.get("narrative_created", False) if consumed.memory_update else False,
                "policy_candidate": consumed.memory_update.get("policy_candidate", False) if consumed.memory_update else False,
                "salience_score": consumed.memory_update.get("salience_score", 0.0) if consumed.memory_update else 0.0,
            },
            # C1: Expose consumed for policy/response/stability inspection
            "consumed": {
                "stable": consumed.stable,
                "memory_integrity": consumed.memory_integrity,
                "policy_consistent": consumed.policy_consistent,
                "policy_hint": consumed.policy_hint,
                "response_tendency": consumed.response_tendency,
            },
            # C1: Expose interpretation for context reading verification
            "interpretation": {
                "interaction_interpretation": interpretation.get("interaction_interpretation", {}),
                "relationship_implication": interpretation.get("relationship_implication", {}),
                "appraisal_state_delta": interpretation.get("appraisal_state_delta", {}),
                "reflection_note": interpretation.get("reflection_note"),
            },
            # v2.1: Expose execution context for verification
            "execution_context": {
                "has_task": execution_context.task_context.active_task_id is not None,
                "target_path": execution_context.target_path,
                "expected_side_effect": execution_context.expected_side_effect,
                "tool_capability": execution_context.tool_capability,
                "repair_needed": execution_context.repair_context.has_pending_repair,
                "failed_task_id": execution_context.repair_context.failed_task_id,
            },
        }

        return {
            "success": True,
            "message": reply,
            "data": diagnostic_data,
        }


# 全局实例
_handler: Optional[SocialChatHandlerV2] = None


def get_social_chat_handler() -> SocialChatHandlerV2:
    """获取全局处理器"""
    global _handler
    if _handler is None:
        _handler = SocialChatHandlerV2()
    return _handler


def handle_social_chat(
    user_input: str,
    user_id: int,
    chat_id: int,
    username: Optional[str] = None,
    recent_messages: Optional[list] = None,
    active_task: Optional[Dict[str, Any]] = None,
    turn_index: int = 0,
) -> Dict[str, Any]:
    """
    便捷函数：处理 social/chat 消息
    
    Args:
        user_input: 用户输入
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        username: 用户名
        recent_messages: 最近消息列表
        active_task: 活动任务
        turn_index: 会话轮次索引
    
    Returns:
        处理结果
    """
    return get_social_chat_handler().handle(
        user_input=user_input,
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        recent_messages=recent_messages,
        active_task=active_task,
        turn_index=turn_index,
    )


# 向后兼容
SocialChatHandler = SocialChatHandlerV2
