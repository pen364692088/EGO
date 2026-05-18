from enum import Enum
from typing import Iterable


class RequestLifecycleState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    WAITING_INPUT = "waiting_input"
    SUPERSEDED = "superseded"
    COMPLETED_VERIFIED = "completed_verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIONABLE_STATES = {
    RequestLifecycleState.CREATED,
    RequestLifecycleState.ACTIVE,
    RequestLifecycleState.WAITING_INPUT,
}

TERMINAL_STATES = {
    RequestLifecycleState.SUPERSEDED,
    RequestLifecycleState.COMPLETED_VERIFIED,
    RequestLifecycleState.FAILED,
    RequestLifecycleState.CANCELLED,
}


def is_actionable(state: str | RequestLifecycleState) -> bool:
    return RequestLifecycleState(state) in ACTIONABLE_STATES


def is_terminal(state: str | RequestLifecycleState) -> bool:
    return RequestLifecycleState(state) in TERMINAL_STATES


def normalize_runtime_status(status: str) -> RequestLifecycleState:
    mapping = {
        "pending": RequestLifecycleState.CREATED,
        "running": RequestLifecycleState.ACTIVE,
        "waiting_input": RequestLifecycleState.WAITING_INPUT,
        "completed": RequestLifecycleState.COMPLETED_VERIFIED,
        "completed_verified": RequestLifecycleState.COMPLETED_VERIFIED,
        "failed": RequestLifecycleState.FAILED,
        "cancelled": RequestLifecycleState.CANCELLED,
        "superseded": RequestLifecycleState.SUPERSEDED,
        "created": RequestLifecycleState.CREATED,
        "active": RequestLifecycleState.ACTIVE,
    }
    return mapping.get(status, RequestLifecycleState.CREATED)


def assert_single_actionable(states: Iterable[str | RequestLifecycleState]) -> bool:
    count = sum(1 for s in states if is_actionable(s))
    return count <= 1
