"""
WS-4: Progress Events / 阶段事件

用真实阶段事件替换 generic busy notice。

事件类型（第一版最小集）：
- target_selected: 目标已选定
- reading_context: 正在读取上下文
- executing_step: 正在执行步骤
- verifying_result: 正在验证结果
- blocked: 卡住了
- completed: 完成

关键原则：
1. 事件从 runtime 阶段推进触发，不从 bridge 文案层硬猜
2. 快任务（<2秒）可以直接 final，不强行插 progress
3. terminal 后不再发 progress
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum
import time


class ProgressEventType(str, Enum):
    """进度事件类型"""
    TARGET_SELECTED = "locking_goal"
    READING_CONTEXT = "reading_context"
    EXECUTING_STEP = "executing_changes"
    VERIFYING_RESULT = "verifying"
    BLOCKED = "blocked"
    COMPLETED = "completed"


# 文案模板（尽量短，有信息量）
PROGRESS_TEMPLATES = {
    ProgressEventType.TARGET_SELECTED: {
        "task": "我先把目标锁定下来。",
        "spec": "我先把 {filename} 作为当前约束。",
        "bundle": "我先锁定任务目标，再把 {count} 份约束一起带上。",
        "default": "我先锁定目标。",
    },
    ProgressEventType.READING_CONTEXT: {
        "default": "我先读取相关上下文。",
        "context": "我先把相关文件读全。",
    },
    ProgressEventType.EXECUTING_STEP: {
        "default": "我先推进当前这一步。",
        "step": "我先推进当前步骤。",
        "file": "我先处理需要的文件。",
        "shell": "我先跑必要的检查。",
        "python": "我先执行必要的脚本。",
    },
    ProgressEventType.VERIFYING_RESULT: {
        "default": "我先验证一下结果。",
    },
    ProgressEventType.BLOCKED: {
        "default": "这里卡住了：{reason}。",
        "no_path": "这里卡住了：缺少可访问路径。",
        "no_tool": "这里卡住了：找不到合适的执行方式。",
    },
    ProgressEventType.COMPLETED: {
        "default": "这一步完成了。",
    },
}

MECHANICAL_TOOL_ACTIONS = {"file", "shell", "python"}


@dataclass
class ProgressEvent:
    """
    进度事件
    
    用于替换 generic busy notice，提供有信息量的阶段反馈。
    """
    event_type: ProgressEventType
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    # 关联信息
    target_filename: Optional[str] = None
    step_number: Optional[int] = None
    total_steps: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "target_filename": self.target_filename,
            "step_number": self.step_number,
            "total_steps": self.total_steps,
        }


def build_progress_event(
    event_type: ProgressEventType,
    context: Optional[str] = None,
    filename: Optional[str] = None,
    step: Optional[int] = None,
    action: Optional[str] = None,
    reason: Optional[str] = None,
    count: Optional[int] = None,
    task: Optional[str] = None,
) -> ProgressEvent:
    """
    构建进度事件
    
    参数：
        event_type: 事件类型
        context: 上下文类型（task/spec/bundle/default）
        filename: 目标文件名
        step: 步骤编号
        action: 步骤动作
        reason: 阻塞原因
        count: 文件数量
        task: 任务文件名
    
    返回：
        ProgressEvent
    """
    templates = PROGRESS_TEMPLATES.get(event_type, {"default": "处理中..."})
    
    # 选择模板
    if event_type == ProgressEventType.EXECUTING_STEP and action in MECHANICAL_TOOL_ACTIONS:
        template = templates.get(action, templates["default"])
    elif context and context in templates:
        template = templates[context]
    elif event_type == ProgressEventType.EXECUTING_STEP and step and action:
        template = templates.get("step", templates["default"])
    elif event_type == ProgressEventType.BLOCKED and reason:
        template = templates.get(reason, templates.get("default", templates["default"]))
    else:
        template = templates.get("default", "处理中...")
    
    # 格式化消息
    try:
        message = template.format(
            filename=filename or "",
            step=step or "",
            action=action or "",
            reason=reason or "",
            count=count or "",
            task=task or "",
        )
    except KeyError:
        message = template
    
    return ProgressEvent(
        event_type=event_type,
        message=message,
        target_filename=filename,
        step_number=step,
        total_steps=None,
        metadata={
            "context": context,
            "action": action,
            "reason": reason,
        },
    )


def is_terminal_event(event_type: ProgressEventType) -> bool:
    """
    判断是否是终端事件
    
    终端事件后不应该再发 progress
    """
    return event_type in {
        ProgressEventType.COMPLETED,
        ProgressEventType.BLOCKED,
    }


def should_emit_progress(event: ProgressEvent, state) -> bool:
    """
    判断是否应该发送进度事件
    
    规则：
    1. terminal 后不再发 progress
    2. final_sent 后不再发 progress
    3. 快任务可以直接 final，不插 progress
    """
    # terminal 状态后不发 progress
    if state.active_turn_status == "terminal":
        return False
    
    # final_sent 后不发 progress
    if state.final_sent:
        return False
    
    # blocked/completed 可以发送
    if is_terminal_event(event.event_type):
        return True
    
    return True
