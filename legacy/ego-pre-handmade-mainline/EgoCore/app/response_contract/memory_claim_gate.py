from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Sequence

from app.restore_runtime import PendingRestoreObservation


RESTORE_CLAIM_MARKERS = (
    "已恢复",
    "恢复成功",
    "恢复了",
    "restore succeeded",
    "restored",
)
MEMORY_CLAIM_MARKERS = (
    "我记得",
    "还记得",
    "记得你",
    "我当然认得",
    "认得你",
    "remember",
    "i remember",
)
CURRENT_SESSION_RECALL_ANCHORS = (
    "刚才",
    "刚刚",
    "前面",
    "上一条",
    "上条",
    "这段对话",
    "这个话题",
    "刚聊",
    "刚聊到",
    "刚才聊",
    "刚才说",
)
_TRIVIAL_RECALL_PROBES = {
    "还记得我吗",
    "记得我吗",
    "还记得吗",
    "记得吗",
    "在吗",
    "?",
    "？",
}


def _normalize_probe_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?\"'“”:：]", "", str(text or "").strip().lower())


@dataclass(frozen=True)
class CurrentSessionRecallGrounding:
    recent_user_turns: tuple[str, ...]
    current_user_turn: str
    authority_source: str = "memory_claim_gate.current_session_grounding"


@dataclass(frozen=True)
class MemoryClaimVerdict:
    allowed: bool
    reason: str
    authority_source: str
    claim_detected: bool


def build_current_session_recall_grounding(
    *,
    recent_user_turns: Sequence[str],
    current_user_turn: str = "",
    authority_source: str = "memory_claim_gate.current_session_grounding",
) -> Optional[CurrentSessionRecallGrounding]:
    cleaned = tuple(str(turn or "").strip() for turn in recent_user_turns if str(turn or "").strip())
    current = str(current_user_turn or "").strip()
    previous_turns = cleaned
    if current and previous_turns and previous_turns[-1] == current:
        previous_turns = previous_turns[:-1]
    previous_turns = tuple(
        turn for turn in previous_turns if _normalize_probe_text(turn) not in _TRIVIAL_RECALL_PROBES
    )
    if not previous_turns:
        return None
    return CurrentSessionRecallGrounding(
        recent_user_turns=previous_turns,
        current_user_turn=current,
        authority_source=authority_source,
    )


def evaluate_memory_claim(
    text: str,
    *,
    restore_observation: Optional[PendingRestoreObservation] = None,
    current_session_grounding: Optional[CurrentSessionRecallGrounding] = None,
) -> MemoryClaimVerdict:
    normalized = (text or "").strip().lower()
    restore_claim_detected = any(marker.lower() in normalized for marker in RESTORE_CLAIM_MARKERS)
    memory_claim_detected = any(marker.lower() in normalized for marker in MEMORY_CLAIM_MARKERS)
    claim_detected = restore_claim_detected or memory_claim_detected
    if not claim_detected:
        return MemoryClaimVerdict(
            allowed=True,
            reason="no_memory_claim_detected",
            authority_source="memory_claim_gate",
            claim_detected=False,
        )

    if restore_claim_detected:
        if restore_observation is None:
            return MemoryClaimVerdict(
                allowed=False,
                reason="missing_restore_authority",
                authority_source="memory_claim_gate",
                claim_detected=True,
            )

        if restore_observation.restore_status in {"success", "partial"}:
            return MemoryClaimVerdict(
                allowed=True,
                reason=f"restore_{restore_observation.restore_status}",
                authority_source=restore_observation.authority_source,
                claim_detected=True,
            )

        return MemoryClaimVerdict(
            allowed=False,
            reason=f"restore_{restore_observation.restore_status}",
            authority_source=restore_observation.authority_source,
            claim_detected=True,
        )

    if _is_grounded_current_session_recall(text, current_session_grounding):
        return MemoryClaimVerdict(
            allowed=True,
            reason="grounded_current_session_recall",
            authority_source=current_session_grounding.authority_source,
            claim_detected=True,
        )

    if restore_observation is not None and restore_observation.restore_status in {"success", "partial"}:
        return MemoryClaimVerdict(
            allowed=True,
            reason=f"restore_{restore_observation.restore_status}",
            authority_source=restore_observation.authority_source,
            claim_detected=True,
        )

    return MemoryClaimVerdict(
        allowed=False,
        reason="missing_restore_authority",
        authority_source="memory_claim_gate",
        claim_detected=True,
    )


def _is_grounded_current_session_recall(
    text: str,
    grounding: Optional[CurrentSessionRecallGrounding],
) -> bool:
    if grounding is None or not grounding.recent_user_turns:
        return False
    normalized = str(text or "").strip().lower()
    if any(marker.lower() in normalized for marker in RESTORE_CLAIM_MARKERS):
        return False
    return any(anchor.lower() in normalized for anchor in CURRENT_SESSION_RECALL_ANCHORS)
