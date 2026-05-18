from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class InteractionKind(str, Enum):
    CHAT = "chat"
    TASK = "task"
    ADMIN = "admin"
    ASK = "ask"
    WAIT = "wait"
    RESUME = "resume"


@dataclass(frozen=True)
class InteractionClassification:
    kind: InteractionKind
    authority_source: str = "interaction.classifier"
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def classify_interaction(
    text: str,
    state: Any,
    *,
    graph: Optional[Any] = None,
    control_intent: Optional[Any] = None,
    runtime_action: Optional[str] = None,
) -> InteractionClassification:
    normalized = (text or "").strip()
    intent_kind = getattr(control_intent, "kind", None)

    if normalized.startswith("/"):
        return InteractionClassification(
            kind=InteractionKind.ADMIN,
            reason="slash_command",
        )

    if intent_kind == "manual_resume":
        return InteractionClassification(
            kind=InteractionKind.RESUME,
            reason="session_control.manual_resume",
        )

    if intent_kind == "task_conflict_resolution":
        return InteractionClassification(
            kind=InteractionKind.ADMIN,
            reason="session_control.task_conflict_resolution",
        )

    if intent_kind == "status_probe":
        return InteractionClassification(
            kind=InteractionKind.WAIT,
            reason="session_control.status_probe",
        )

    if intent_kind == "chat_ping":
        return InteractionClassification(
            kind=InteractionKind.CHAT,
            reason="session_control.chat_ping",
        )

    if getattr(state, "waiting_for_user_input", False):
        return InteractionClassification(
            kind=InteractionKind.ASK,
            reason="runtime.waiting_for_user_input",
        )

    primary_intent = getattr(graph, "primary_intent", None)
    if primary_intent == "task_request" or runtime_action == "execute_task":
        return InteractionClassification(
            kind=InteractionKind.TASK,
            reason="semantic.task_request",
            metadata={"runtime_action": runtime_action},
        )

    return InteractionClassification(
        kind=InteractionKind.CHAT,
        reason="default_chat",
        metadata={"runtime_action": runtime_action},
    )
