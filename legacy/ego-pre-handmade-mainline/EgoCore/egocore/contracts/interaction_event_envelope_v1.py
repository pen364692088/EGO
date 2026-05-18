"""
InteractionEventEnvelope v1 - EgoCore → OpenEmotion

标准化事件信封，用于 EgoCore 向 OpenEmotion 发送互动事件。

语义：
- 这是一个"发生了什么"的客观描述
- 不包含任何解释、判断或决策
- 归属权：EgoCore 构建，OpenEmotion 消费

版本：1.0.0
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class EventSource(str, Enum):
    """事件来源"""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    CLI = "cli"
    API = "api"


class InputType(str, Enum):
    """输入类型"""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    COMMAND = "command"


@dataclass
class RecentTurn:
    """最近一轮对话"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActiveTaskSummary:
    """活动任务摘要"""
    task_id: str
    objective: str
    status: str
    progress: tuple  # (completed, total)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status,
            "progress": {"completed": self.progress[0], "total": self.progress[1]}
        }


@dataclass
class RuntimeSummary:
    """运行时状态摘要"""
    has_active_task: bool = False
    pending_confirmations: int = 0
    last_activity_seconds_ago: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyContext:
    """安全上下文"""
    is_elevated: bool = False
    is_restricted: bool = False
    requires_confirmation: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionEventEnvelope:
    """
    互动事件信封 v1
    
    方向：EgoCore → OpenEmotion
    作用：把用户/环境输入、最近上下文、任务状态、运行时摘要转换成主体可理解事件。
    
    关键原则：
    - 只描述客观事实，不包含解释
    - 不包含任何决策字段（should_reply 等）
    - 所有字段都是 EgoCore 的权威
    """
    # === 必需字段（无默认值）===
    envelope_id: str  # 唯一信封 ID
    user_input: str  # 用户原始输入文本
    user_id: str  # 用户标识
    session_id: str  # 会话标识（用于上下文隔离）
    
    # === 可选字段（有默认值）===
    schema_version: str = "1.0.0"
    input_type: InputType = InputType.TEXT
    source: EventSource = EventSource.TELEGRAM
    
    # === 上下文字段 ===
    recent_turns: List[RecentTurn] = field(default_factory=list)  # 最近 N 轮对话
    turn_count: int = 0  # 当前会话总轮次
    
    # === 任务状态 ===
    active_task: Optional[ActiveTaskSummary] = None
    
    # === 运行时状态 ===
    runtime: RuntimeSummary = field(default_factory=RuntimeSummary)
    
    # === 安全上下文 ===
    safety: SafetyContext = field(default_factory=SafetyContext)
    
    # === 元数据 ===
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "schema_version": self.schema_version,
            "user_input": self.user_input,
            "input_type": self.input_type.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "source": self.source.value,
            "recent_turns": [t.to_dict() for t in self.recent_turns],
            "turn_count": self.turn_count,
            "active_task": self.active_task.to_dict() if self.active_task else None,
            "runtime": self.runtime.to_dict(),
            "safety": self.safety.to_dict(),
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionEventEnvelope":
        """从字典创建"""
        recent_turns = [
            RecentTurn(**t) if isinstance(t, dict) else t
            for t in data.get("recent_turns", [])
        ]
        
        active_task = None
        if data.get("active_task"):
            at = data["active_task"]
            progress = at.get("progress", {})
            active_task = ActiveTaskSummary(
                task_id=at["task_id"],
                objective=at["objective"],
                status=at["status"],
                progress=(progress.get("completed", 0), progress.get("total", 0))
            )
        
        runtime_data = data.get("runtime", {})
        runtime = RuntimeSummary(
            has_active_task=runtime_data.get("has_active_task", False),
            pending_confirmations=runtime_data.get("pending_confirmations", 0),
            last_activity_seconds_ago=runtime_data.get("last_activity_seconds_ago", 0),
        )
        
        safety_data = data.get("safety", {})
        safety = SafetyContext(
            is_elevated=safety_data.get("is_elevated", False),
            is_restricted=safety_data.get("is_restricted", False),
            requires_confirmation=safety_data.get("requires_confirmation", False),
        )
        
        return cls(
            envelope_id=data["envelope_id"],
            schema_version=data.get("schema_version", "1.0.0"),
            user_input=data["user_input"],
            input_type=InputType(data.get("input_type", "text")),
            user_id=data["user_id"],
            session_id=data["session_id"],
            source=EventSource(data.get("source", "telegram")),
            recent_turns=recent_turns,
            turn_count=data.get("turn_count", 0),
            active_task=active_task,
            runtime=runtime,
            safety=safety,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


# ============================================================================
# Golden Payloads
# ============================================================================

def golden_payload_1_first_greeting() -> Dict[str, Any]:
    """场景 1: 初次"你好" """
    return InteractionEventEnvelope(
        envelope_id="env_001",
        user_input="你好",
        user_id="telegram:8420019401",
        session_id="session_001",
        source=EventSource.TELEGRAM,
        recent_turns=[],
        turn_count=1,
        active_task=None,
        runtime=RuntimeSummary(has_active_task=False),
        safety=SafetyContext(),
    ).to_dict()


def golden_payload_2_repeated_greeting() -> Dict[str, Any]:
    """场景 2: 连续三次"你好 / 测试" (第三次)"""
    return InteractionEventEnvelope(
        envelope_id="env_002",
        user_input="你好",
        user_id="telegram:8420019401",
        session_id="session_001",
        source=EventSource.TELEGRAM,
        recent_turns=[
            RecentTurn(role="user", content="你好啊", timestamp="2026-03-17T05:30:00Z"),
            RecentTurn(role="assistant", content="👋 你好！我是 EgoCore 任务助手...", timestamp="2026-03-17T05:30:01Z"),
            RecentTurn(role="user", content="第二次测试", timestamp="2026-03-17T05:31:00Z"),
            RecentTurn(role="assistant", content="我收到了，继续测试。", timestamp="2026-03-17T05:31:01Z"),
        ],
        turn_count=5,
        active_task=None,
        runtime=RuntimeSummary(has_active_task=False, last_activity_seconds_ago=60),
        safety=SafetyContext(),
    ).to_dict()


def golden_payload_3_with_active_task() -> Dict[str, Any]:
    """场景 3: "在吗"且有活动任务"""
    return InteractionEventEnvelope(
        envelope_id="env_003",
        user_input="在吗",
        user_id="telegram:8420019401",
        session_id="session_002",
        source=EventSource.TELEGRAM,
        recent_turns=[
            RecentTurn(role="user", content="帮我分析这个项目", timestamp="2026-03-17T05:00:00Z"),
            RecentTurn(role="assistant", content="好的，开始分析...", timestamp="2026-03-17T05:00:05Z"),
        ],
        turn_count=3,
        active_task=ActiveTaskSummary(
            task_id="task_abc123",
            objective="分析项目结构",
            status="running",
            progress=(2, 5)
        ),
        runtime=RuntimeSummary(has_active_task=True, last_activity_seconds_ago=120),
        safety=SafetyContext(),
    ).to_dict()


def golden_payload_4_affective_probe() -> Dict[str, Any]:
    """场景 4: "你怎么这么冷淡" """
    return InteractionEventEnvelope(
        envelope_id="env_004",
        user_input="你怎么这么冷淡",
        user_id="telegram:8420019401",
        session_id="session_003",
        source=EventSource.TELEGRAM,
        recent_turns=[
            RecentTurn(role="user", content="在吗", timestamp="2026-03-17T05:40:00Z"),
            RecentTurn(role="assistant", content="我在。", timestamp="2026-03-17T05:40:01Z"),
        ],
        turn_count=3,
        active_task=None,
        runtime=RuntimeSummary(has_active_task=False),
        safety=SafetyContext(),
    ).to_dict()


def golden_payload_5_gratitude() -> Dict[str, Any]:
    """场景 5: "谢谢" """
    return InteractionEventEnvelope(
        envelope_id="env_005",
        user_input="谢谢",
        user_id="telegram:8420019401",
        session_id="session_004",
        source=EventSource.TELEGRAM,
        recent_turns=[
            RecentTurn(role="user", content="帮我检查一下代码", timestamp="2026-03-17T05:50:00Z"),
            RecentTurn(role="assistant", content="检查完成，发现 3 个问题...", timestamp="2026-03-17T05:50:30Z"),
        ],
        turn_count=3,
        active_task=None,
        runtime=RuntimeSummary(has_active_task=False, last_activity_seconds_ago=30),
        safety=SafetyContext(),
    ).to_dict()


# 验证函数
def validate_envelope(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证信封格式"""
    required_fields = ["envelope_id", "user_input", "user_id", "session_id", "schema_version"]
    
    for req_field in required_fields:
        if req_field not in data:
            return False, f"Missing required field: {req_field}"
    
    if data["schema_version"] != "1.0.0":
        return False, f"Unsupported schema version: {data['schema_version']}"
    
    return True, None
