"""
Proto-Self Kernel v1 Trace Types

Trace payload 结构定义，用于写入 run.jsonl。

设计约束：
- replay 时优先读取 trace 中已记录的 cycle_delta / policy_hint
- 不允许用当前 cycle_store 现状重算旧轮结果
- 必须维持 anti-drift 与 trace-driven replay
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


TRACE_SCHEMA_VERSION = "proto_self.trace.v1"


@dataclass
class ProtoSelfTracePayload:
    """
    Proto-Self Kernel 每轮输出的 trace payload。
    
    设计意图：
    - 让 trace payload 成为一等输出
    - 支撑 trace-driven replay
    - 不依赖当前 store 重算旧轮结论
    """
    schema_version: str = TRACE_SCHEMA_VERSION
    event_id: str = ""

    # 感知结果
    perceived: Dict[str, Any] = field(default_factory=dict)

    # 状态增量
    appraisal_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    cycle_delta: Dict[str, Any] = field(default_factory=dict)
    identity_delta: Dict[str, Any] = field(default_factory=dict)

    # 反思触发（如有）
    reflection_trigger: Optional[str] = None

    # 策略输出
    policy_hint: Dict[str, Any] = field(default_factory=dict)

    # 时间戳
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "perceived": self.perceived,
            "appraisal_delta": self.appraisal_delta,
            "self_model_delta": self.self_model_delta,
            "cycle_delta": self.cycle_delta,
            "identity_delta": self.identity_delta,
            "reflection_trigger": self.reflection_trigger,
            "policy_hint": self.policy_hint,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProtoSelfTracePayload":
        return cls(
            schema_version=data.get("schema_version", TRACE_SCHEMA_VERSION),
            event_id=data.get("event_id", ""),
            perceived=data.get("perceived", {}),
            appraisal_delta=data.get("appraisal_delta", {}),
            self_model_delta=data.get("self_model_delta", {}),
            cycle_delta=data.get("cycle_delta", {}),
            identity_delta=data.get("identity_delta", {}),
            reflection_trigger=data.get("reflection_trigger"),
            policy_hint=data.get("policy_hint", {}),
            timestamp=data.get("timestamp", ""),
        )


def build_trace_payload(
    event_id: str,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
    cycle_delta: Dict[str, Any],
    identity_delta: Dict[str, Any],
    reflection_trigger: Optional[str],
    policy_hint: Dict[str, Any],
    timestamp: str = "",
) -> Dict[str, Any]:
    """
    构建 trace payload 字典。
    
    这是辅助函数，用于在 kernel.py 中快速构建 trace payload。
    """
    payload = ProtoSelfTracePayload(
        event_id=event_id,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        identity_delta=identity_delta,
        reflection_trigger=reflection_trigger,
        policy_hint=policy_hint,
        timestamp=timestamp,
    )
    return payload.to_dict()
