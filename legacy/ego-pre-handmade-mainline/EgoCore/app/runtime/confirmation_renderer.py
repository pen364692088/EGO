"""
OpenEmotion Agent Runtime - Confirmation Renderer

P2-C.3: Renders confirmation messages for user approval.

Message design principles:
- Short and clear
- Tell user how to reply
- Avoid long explanations
- Easy to parse for Telegram
"""

from typing import List, Optional
from app.runtime.approval_policy import (
    ApprovalRequest,
    ApprovalType,
    ApprovalReason,
)


def render_confirmation_message(request: ApprovalRequest) -> str:
    """
    Render a confirmation message for user approval.
    
    Args:
        request: The approval request
    
    Returns:
        Formatted message string
    """
    if request.approval_type == ApprovalType.YES_NO:
        return render_yes_no_message(request)
    elif request.approval_type == ApprovalType.OPTION_SELECT:
        return render_option_select_message(request)
    elif request.approval_type == ApprovalType.INTENT_DISAMBIGUATE:
        return render_intent_disambiguate_message(request)
    elif request.approval_type == ApprovalType.PATH_CLARIFY:
        return render_path_clarify_message(request)
    elif request.approval_type == ApprovalType.FREE_TEXT:
        return render_free_text_message(request)
    else:
        return render_generic_message(request)


def render_yes_no_message(request: ApprovalRequest) -> str:
    """Render a yes/no confirmation message."""
    lines = []
    
    # Emoji based on reason
    emoji = "⚠️" if request.reason in (
        ApprovalReason.HIGH_RISK_OPERATION,
        ApprovalReason.SAFETY_CONFIRM,
    ) else "❓"
    
    lines.append(f"{emoji} **需要确认**")
    lines.append("")
    lines.append(request.prompt)
    lines.append("")
    lines.append("回复 **yes** 或 **no**（或 是/否）")
    
    return "\n".join(lines)


def render_option_select_message(request: ApprovalRequest) -> str:
    """Render an option selection message."""
    lines = []
    
    lines.append("📋 **请选择**")
    lines.append("")
    lines.append(request.prompt)
    lines.append("")
    
    for i, option in enumerate(request.options):
        # Truncate long options
        display = option[:50] + "..." if len(option) > 50 else option
        lines.append(f"**{i}**. {display}")
    
    lines.append("")
    lines.append(f"回复选项编号 **0-{len(request.options)-1}**")
    
    return "\n".join(lines)


def render_intent_disambiguate_message(request: ApprovalRequest) -> str:
    """Render an intent disambiguation message."""
    lines = []
    
    lines.append("🔍 **检测到多种意图**")
    lines.append("")
    lines.append(request.prompt)
    lines.append("")
    
    for i, option in enumerate(request.options):
        lines.append(f"**{i}**. {option}")
    
    lines.append("")
    lines.append(f"回复编号选择要执行的操作")
    
    return "\n".join(lines)


def render_path_clarify_message(request: ApprovalRequest) -> str:
    """Render a path clarification message."""
    lines = []
    
    lines.append("📂 **请指定路径**")
    lines.append("")
    lines.append(request.prompt)
    
    if request.operation_type:
        op_name = {
            "read_file": "读取文件",
            "write_file": "写入文件",
            "list_dir": "列出目录",
            "mkdir": "创建目录",
            "exists": "检查存在",
        }.get(request.operation_type, request.operation_type)
        lines.append(f"操作类型: {op_name}")
    
    lines.append("")
    lines.append("回复目标路径，例如：`/home/user/file.txt`")
    
    return "\n".join(lines)


def render_free_text_message(request: ApprovalRequest) -> str:
    """Render a free-text clarification message."""
    lines = []
    
    lines.append("💬 **需要补充信息**")
    lines.append("")
    lines.append(request.prompt)
    lines.append("")
    lines.append("直接回复你的回答")
    
    return "\n".join(lines)


def render_generic_message(request: ApprovalRequest) -> str:
    """Render a generic confirmation message."""
    lines = []
    
    lines.append("❓ **请确认**")
    lines.append("")
    lines.append(request.prompt)
    
    if request.options:
        lines.append("")
        for i, option in enumerate(request.options):
            lines.append(f"**{i}**. {option}")
    
    if request.valid_replies:
        lines.append("")
        lines.append(f"有效回复: {', '.join(request.valid_replies)}")
    
    return "\n".join(lines)


# ============================================================================
# Telegram-specific formatting
# ============================================================================

def render_telegram_confirmation(request: ApprovalRequest) -> str:
    """
    Render a confirmation message optimized for Telegram.
    
    Uses Telegram Markdown formatting.
    
    Args:
        request: The approval request
    
    Returns:
        Formatted message string for Telegram
    """
    # Telegram uses different markdown
    message = render_confirmation_message(request)
    
    # Convert ** to * for Telegram bold
    message = message.replace("**", "*")
    
    return message


def render_telegram_inline_keyboard(request: ApprovalRequest) -> Optional[List[List[dict]]]:
    """
    Render inline keyboard buttons for Telegram.
    
    Returns None if inline keyboard is not appropriate.
    
    Args:
        request: The approval request
    
    Returns:
        List of button rows, or None
    """
    if request.approval_type == ApprovalType.YES_NO:
        return [
            [
                {"text": "✅ 确认", "callback_data": f"confirm:{request.task_id}:yes"},
                {"text": "❌ 取消", "callback_data": f"confirm:{request.task_id}:no"},
            ]
        ]
    
    elif request.approval_type in (ApprovalType.OPTION_SELECT, ApprovalType.INTENT_DISAMBIGUATE):
        # Limit to 4 options inline, rest as text
        buttons = []
        for i, option in enumerate(request.options[:4]):
            # Truncate button text
            text = option[:20] + "..." if len(option) > 20 else option
            buttons.append({
                "text": f"{i}. {text}",
                "callback_data": f"confirm:{request.task_id}:{i}",
            })
        
        # Arrange in rows of 2
        rows = []
        for i in range(0, len(buttons), 2):
            rows.append(buttons[i:i+2])
        
        return rows
    
    # Other types use text reply
    return None


# ============================================================================
# Quick Reply Hints
# ============================================================================

def get_quick_reply_hint(request: ApprovalRequest) -> str:
    """
    Get a quick hint for how to reply.
    
    Useful for status display or logging.
    
    Args:
        request: The approval request
    
    Returns:
        Short hint string
    """
    if request.approval_type == ApprovalType.YES_NO:
        return "回复 yes/no"
    elif request.approval_type in (ApprovalType.OPTION_SELECT, ApprovalType.INTENT_DISAMBIGUATE):
        return f"回复 0-{len(request.options)-1}"
    elif request.approval_type == ApprovalType.PATH_CLARIFY:
        return "回复路径"
    else:
        return "回复内容"


def format_waiting_status(request: ApprovalRequest) -> str:
    """
    Format waiting status for status query.
    
    Args:
        request: The approval request
    
    Returns:
        Status string
    """
    lines = []
    lines.append(f"⏳ 等待用户输入")
    lines.append(f"类型: {request.approval_type.value}")
    lines.append(f"原因: {request.reason.value}")
    lines.append(f"提示: {get_quick_reply_hint(request)}")
    return "\n".join(lines)
