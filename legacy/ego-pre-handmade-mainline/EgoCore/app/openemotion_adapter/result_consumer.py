"""
Result Consumer - OpenEmotion 结果消费

用途: 消费 OpenEmotion ResultV1，衔接到 EgoCore 现实裁决
职责: L3 边界适配层，不是主体本体层

重要:
- 不在这里定义主体字段语义
- 只做结果消费和格式适配
- 主体逻辑在 OpenEmotion 侧
- 现实裁决在 EgoCore 侧

版本: v1.0.0
"""

from dataclasses import dataclass
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConsumedResult:
    """
    消费后的结果

    用于 EgoCore 内部传递，不直接暴露给外部
    """
    event_id: str
    success: bool

    # 结构化消费字段
    self_model_delta: Optional[dict] = None
    self_model_writeback: Optional[dict] = None
    memory_update: Optional[dict] = None
    policy_hint: Optional[dict] = None
    response_tendency: Optional[dict] = None

    # 稳定性指标
    stable: bool = True
    memory_integrity: bool = True
    policy_consistent: bool = True

    # 错误信息
    error: Optional[str] = None


class ResultConsumer:
    """
    结果消费者 - EgoCore 侧

    职责:
    - 消费 OpenEmotionResultV1
    - 把结构字段转成 EgoCore 内部格式
    - 不做主体语义解释，只做格式适配
    """

    def __init__(self):
        self.consumed_count = 0
        self.error_count = 0

    def consume(self, result_dict: dict[str, Any]) -> ConsumedResult:
        """
        消费 OpenEmotion 结果

        Args:
            result_dict: OpenEmotionResultV1 格式的字典

        Returns:
            ConsumedResult: 消费后的结果
        """
        event_id = result_dict.get("event_id", "unknown")
        result_type = result_dict.get("result_type", "interpretation")
        confidence = result_dict.get("confidence", 0.0)

        # 提取结构字段
        self_model_delta = result_dict.get("self_model_delta")
        self_model_writeback = result_dict.get("self_model_writeback")
        memory_update = result_dict.get("memory_update")
        policy_hint = result_dict.get("policy_hint")
        response_tendency = result_dict.get("response_tendency")
        stability = result_dict.get("stability", {})
        error_info = result_dict.get("error")

        # 计算稳定性
        stable = stability.get("self_model_stable", True) if stability else True
        memory_integrity = stability.get("memory_integrity", True) if stability else True
        policy_consistent = stability.get("policy_consistent", True) if stability else True

        # 错误处理
        error = None
        if error_info:
            error = error_info.get("message", "Unknown error")
            self.error_count += 1
            logger.warning(f"OpenEmotion result error for {event_id}: {error}")

        self.consumed_count += 1

        return ConsumedResult(
            event_id=event_id,
            success=result_type != "error",
            self_model_delta=self_model_delta,
            self_model_writeback=self_model_writeback,
            memory_update=memory_update,
            policy_hint=policy_hint,
            response_tendency=response_tendency,
            stable=stable,
            memory_integrity=memory_integrity,
            policy_consistent=policy_consistent,
            error=error,
        )

    def get_policy_hint(self, result: ConsumedResult) -> Optional[dict]:
        """
        提取策略提示

        策略提示是给 EgoCore 参考的，不是强制的
        """
        return result.policy_hint

    def get_response_tendency(self, result: ConsumedResult) -> Optional[dict]:
        """
        提取响应倾向

        响应倾向是给 EgoCore 参考的，不是强制的
        现实裁决（should_reply / runtime_route 等）在 EgoCore 侧决定
        """
        return result.response_tendency

    def should_update_memory(self, result: ConsumedResult) -> bool:
        """判断是否需要更新记忆"""
        if not result.memory_update:
            return False
        return result.memory_update.get("event_stored", False)

    def should_propagate_policy(self, result: ConsumedResult) -> bool:
        """判断是否需要传播策略变化"""
        if not result.policy_hint:
            return False
        return result.policy_hint.get("confidence", 0) > 0.7

    def get_stats(self) -> dict[str, int]:
        """获取消费统计"""
        return {
            "consumed_count": self.consumed_count,
            "error_count": self.error_count,
        }


# 默认实例
default_result_consumer = ResultConsumer()
