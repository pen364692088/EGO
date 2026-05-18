"""
OpenEmotion Agent Runtime - Approval Policy

P2-C.1: Defines when user confirmation is required.

Core principle: Ask user when:
- Path is ambiguous
- Multiple candidate targets exist
- High-risk operations (overwrite/delete)
- Multiple high-confidence intents coexist
- User needs to choose next branch
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from enum import Enum

from app.risk_signal import is_high_risk_message
from app.runtime.execution_result import FailureClass
from app.runtime.intent_mapper import OperationType, OperationIntent


class ApprovalType(str, Enum):
    """Types of user approval requests."""
    YES_NO = "yes_no"                    # Simple yes/no confirmation
    OPTION_SELECT = "option_select"      # Choose from options
    FREE_TEXT = "free_text"              # Free-text clarification
    PATH_CLARIFY = "path_clarify"        # Clarify target path
    INTENT_DISAMBIGUATE = "intent_disambiguate"  # Disambiguate intent


class ApprovalReason(str, Enum):
    """Reasons why approval is needed."""
    PATH_AMBIGUOUS = "path_ambiguous"              # Path not clear
    MULTIPLE_TARGETS = "multiple_targets"          # Multiple candidate targets
    HIGH_RISK_OPERATION = "high_risk_operation"    # Overwrite/delete/risky write
    MULTIPLE_INTENTS = "multiple_intents"          # Multiple high-confidence intents
    BRANCH_CHOICE = "branch_choice"                # User needs to choose branch
    SAFETY_CONFIRM = "safety_confirm"              # Safety confirmation required
    PERMISSION_CONFIRM = "permission_confirm"      # Permission confirmation


@dataclass
class ApprovalRequest:
    """
    Request for user approval.
    
    This is the payload that gets persisted to task waiting state
    and used to render confirmation message.
    """
    # Core fields
    approval_type: ApprovalType
    reason: ApprovalReason
    prompt: str                              # User-facing question
    options: List[str] = field(default_factory=list)  # For OPTION_SELECT
    
    # Context
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    operation_type: Optional[str] = None
    target_path: Optional[str] = None
    
    # Expected reply
    expected_reply_type: str = "text"        # text, yes/no, option_index
    valid_replies: List[str] = field(default_factory=list)  # Valid reply values
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "approval_type": self.approval_type.value,
            "reason": self.reason.value,
            "prompt": self.prompt,
            "options": self.options,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "operation_type": self.operation_type,
            "target_path": self.target_path,
            "expected_reply_type": self.expected_reply_type,
            "valid_replies": self.valid_replies,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        return cls(
            approval_type=ApprovalType(data["approval_type"]),
            reason=ApprovalReason(data["reason"]),
            prompt=data["prompt"],
            options=data.get("options", []),
            task_id=data.get("task_id"),
            step_id=data.get("step_id"),
            operation_type=data.get("operation_type"),
            target_path=data.get("target_path"),
            expected_reply_type=data.get("expected_reply_type", "text"),
            valid_replies=data.get("valid_replies", []),
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# High-Risk Operations
# ============================================================================

HIGH_RISK_PATHS: Set[str] = {
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/root",
    "/home",
    "~/.ssh",
    "~/.gnupg",
}


def is_high_risk_operation(step_description: str) -> bool:
    """
    Check if a step description contains high-risk operation keywords.
    
    Args:
        step_description: Description of the step
    
    Returns:
        True if high-risk operation detected
    """
    return is_high_risk_message(step_description)


def is_high_risk_path(path: str) -> bool:
    """
    Check if a path is in a high-risk location.
    
    Args:
        path: Target path
    
    Returns:
        True if path is high-risk
    """
    import os
    expanded = os.path.expanduser(path)
    normalized = os.path.normpath(expanded)
    
    for risky_path in HIGH_RISK_PATHS:
        if normalized.startswith(risky_path) or risky_path in normalized:
            return True
    
    return False


# ============================================================================
# Approval Decision Logic
# ============================================================================

@dataclass
class ApprovalDecision:
    """
    Decision on whether approval is needed.
    
    If approval_needed is True, approval_request contains the request.
    If approval_needed is False, can proceed directly.
    """
    approval_needed: bool
    approval_request: Optional[ApprovalRequest] = None
    reason: str = ""


def check_approval_needed(
    step_description: str,
    intent: Optional[OperationIntent] = None,
    target_path: Optional[str] = None,
    candidate_paths: Optional[List[str]] = None,
    candidate_intents: Optional[List[OperationIntent]] = None,
    task_id: Optional[str] = None,
    step_id: Optional[str] = None,
) -> ApprovalDecision:
    """
    Check if user approval is needed before executing a step.
    
    Args:
        step_description: Description of the step
        intent: Parsed operation intent
        target_path: Target path (if known)
        candidate_paths: Multiple candidate paths (ambiguous)
        candidate_intents: Multiple candidate intents
        task_id: Task ID
        step_id: Step ID
    
    Returns:
        ApprovalDecision with approval_needed and optional request
    """
    
    # Case 1: Multiple candidate intents - need disambiguation
    if candidate_intents and len(candidate_intents) > 1:
        options = [
            f"{i.operation.value}: {i.target_path or 'unknown'}"
            for i in candidate_intents[:5]  # Limit to 5 options
        ]
        
        return ApprovalDecision(
            approval_needed=True,
            approval_request=ApprovalRequest(
                approval_type=ApprovalType.INTENT_DISAMBIGUATE,
                reason=ApprovalReason.MULTIPLE_INTENTS,
                prompt="检测到多种可能的操作意图，请选择要执行的操作：",
                options=options,
                task_id=task_id,
                step_id=step_id,
                expected_reply_type="option_index",
                valid_replies=[str(i) for i in range(len(options))],
            ),
            reason="Multiple high-confidence intents detected",
        )
    
    # Case 2: Path not determined
    if intent and not intent.target_path and intent.operation in (
        OperationType.READ_FILE,
        OperationType.WRITE_FILE,
        OperationType.LIST_DIR,
        OperationType.MKDIR,
        OperationType.EXISTS,
    ):
        return ApprovalDecision(
            approval_needed=True,
            approval_request=ApprovalRequest(
                approval_type=ApprovalType.PATH_CLARIFY,
                reason=ApprovalReason.PATH_AMBIGUOUS,
                prompt="请指定目标文件或目录路径：",
                task_id=task_id,
                step_id=step_id,
                operation_type=intent.operation.value,
                expected_reply_type="text",
            ),
            reason="Target path could not be determined",
        )
    
    # Case 3: Multiple candidate paths
    if candidate_paths and len(candidate_paths) > 1:
        options = candidate_paths[:5]  # Limit to 5 options
        
        return ApprovalDecision(
            approval_needed=True,
            approval_request=ApprovalRequest(
                approval_type=ApprovalType.OPTION_SELECT,
                reason=ApprovalReason.MULTIPLE_TARGETS,
                prompt="发现多个可能的目标，请选择：",
                options=options,
                task_id=task_id,
                step_id=step_id,
                expected_reply_type="option_index",
                valid_replies=[str(i) for i in range(len(options))],
            ),
            reason="Multiple candidate targets found",
        )
    
    # Case 4: High-risk operation
    if is_high_risk_operation(step_description):
        return ApprovalDecision(
            approval_needed=True,
            approval_request=ApprovalRequest(
                approval_type=ApprovalType.YES_NO,
                reason=ApprovalReason.HIGH_RISK_OPERATION,
                prompt=f"⚠️ 此操作可能具有风险：{step_description}\n确认执行？(yes/no)",
                task_id=task_id,
                step_id=step_id,
                expected_reply_type="yes_no",
                valid_replies=["yes", "no", "y", "n", "是", "否"],
            ),
            reason="High-risk operation detected",
        )
    
    # Case 5: High-risk path
    if target_path and is_high_risk_path(target_path):
        return ApprovalDecision(
            approval_needed=True,
            approval_request=ApprovalRequest(
                approval_type=ApprovalType.YES_NO,
                reason=ApprovalReason.SAFETY_CONFIRM,
                prompt=f"⚠️ 目标路径敏感：{target_path}\n确认操作？(yes/no)",
                task_id=task_id,
                step_id=step_id,
                target_path=target_path,
                expected_reply_type="yes_no",
                valid_replies=["yes", "no", "y", "n", "是", "否"],
            ),
            reason="High-risk path detected",
        )
    
    # Case 6: Write operations to existing files
    if intent and intent.operation == OperationType.WRITE_FILE and target_path:
        import os
        if os.path.exists(target_path):
            return ApprovalDecision(
                approval_needed=True,
                approval_request=ApprovalRequest(
                    approval_type=ApprovalType.YES_NO,
                    reason=ApprovalReason.HIGH_RISK_OPERATION,
                    prompt=f"文件已存在：{target_path}\n确认覆盖？(yes/no)",
                    task_id=task_id,
                    step_id=step_id,
                    target_path=target_path,
                    expected_reply_type="yes_no",
                    valid_replies=["yes", "no", "y", "n", "是", "否"],
                ),
                reason="Overwrite confirmation needed",
            )
    
    # No approval needed
    return ApprovalDecision(
        approval_needed=False,
        reason="No approval required",
    )


# ============================================================================
# Reply Validation
# ============================================================================

def validate_user_reply(
    user_reply: str,
    approval_request: ApprovalRequest,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a user reply against an approval request.
    
    Args:
        user_reply: User's reply text
        approval_request: The approval request
    
    Returns:
        Tuple of (is_valid, parsed_value, error_message)
    """
    reply_lower = user_reply.lower().strip()
    
    if approval_request.approval_type == ApprovalType.YES_NO:
        # Normalize yes/no
        if reply_lower in ("yes", "y", "是", "确认", "ok"):
            return True, "yes", None
        elif reply_lower in ("no", "n", "否", "取消", "cancel"):
            return True, "no", None
        else:
            return False, None, f"请回复 yes/no（是/否）"
    
    elif approval_request.approval_type == ApprovalType.OPTION_SELECT:
        # Check if reply is a valid option index
        try:
            index = int(reply_lower)
            if 0 <= index < len(approval_request.options):
                return True, str(index), None
            else:
                return False, None, f"请选择 0-{len(approval_request.options)-1}"
        except ValueError:
            return False, None, f"请输入选项编号"
    
    elif approval_request.approval_type == ApprovalType.INTENT_DISAMBIGUATE:
        # Same as option select
        try:
            index = int(reply_lower)
            if 0 <= index < len(approval_request.options):
                return True, str(index), None
            else:
                return False, None, f"请选择 0-{len(approval_request.options)-1}"
        except ValueError:
            return False, None, f"请输入选项编号"
    
    elif approval_request.approval_type == ApprovalType.PATH_CLARIFY:
        # Accept any non-empty path
        if user_reply.strip():
            return True, user_reply.strip(), None
        else:
            return False, None, "请输入有效路径"
    
    elif approval_request.approval_type == ApprovalType.FREE_TEXT:
        # Accept any non-empty text
        if user_reply.strip():
            return True, user_reply.strip(), None
        else:
            return False, None, "请输入内容"
    
    # Unknown type
    return False, None, "未知的确认类型"


def parse_user_decision(
    user_reply: str,
    approval_request: ApprovalRequest,
) -> Dict[str, Any]:
    """
    Parse user reply into a decision.
    
    Args:
        user_reply: User's reply text
        approved_request: The approval request
    
    Returns:
        Decision dict with approved, value, and other fields
    """
    is_valid, parsed_value, error = validate_user_reply(user_reply, approval_request)
    
    decision = {
        "is_valid": is_valid,
        "raw_reply": user_reply,
        "parsed_value": parsed_value,
        "error": error,
        "approved": False,
        "selected_option": None,
        "clarified_path": None,
    }
    
    if not is_valid:
        return decision
    
    if approval_request.approval_type == ApprovalType.YES_NO:
        decision["approved"] = (parsed_value == "yes")
    
    elif approval_request.approval_type in (ApprovalType.OPTION_SELECT, ApprovalType.INTENT_DISAMBIGUATE):
        decision["approved"] = True
        decision["selected_option"] = int(parsed_value)
        if approval_request.options and decision["selected_option"] < len(approval_request.options):
            decision["selected_value"] = approval_request.options[decision["selected_option"]]
    
    elif approval_request.approval_type == ApprovalType.PATH_CLARIFY:
        decision["approved"] = True
        decision["clarified_path"] = parsed_value
    
    elif approval_request.approval_type == ApprovalType.FREE_TEXT:
        decision["approved"] = True
        decision["clarified_value"] = parsed_value
    
    return decision
