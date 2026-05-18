from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from openemotion.proto_self_v2.seed_schemas import ActionSpec, KernelEvent


AUTO_ALLOW = {
    "inspect_file",
    "inspect_browser",
    "inspect_window_state",
    "read_clipboard",
    "read_text",
    "review_recent_failure",
}

LIMITED_ALLOW = {
    "open_file",
    "focus_window",
    "scroll",
    "copy",
    "switch_tab",
    "continue_pending_commitment",
    "ask_user",
}

APPROVAL_REQUIRED = {
    "write_file",
    "type_text",
    "delete",
    "run_code",
    "shell_exec",
    "bulk_click",
    "submit_form",
    "system_setting_change",
}


@dataclass(slots=True)
class GovernorLite:
    auto_allow: set[str] = field(default_factory=lambda: set(AUTO_ALLOW))
    limited_allow: set[str] = field(default_factory=lambda: set(LIMITED_ALLOW))
    approval_required: set[str] = field(default_factory=lambda: set(APPROVAL_REQUIRED))

    def classify(
        self,
        candidate_actions: Iterable[ActionSpec],
        event: KernelEvent,
    ) -> Dict[str, object]:
        actions: List[ActionSpec] = sorted(
            list(candidate_actions),
            key=lambda item: (item.urge_score, item.expected_gain),
            reverse=True,
        )
        if not actions:
            return {
                "status": "no_candidate",
                "reason": "no candidate actions",
                "candidate_count": 0,
            }

        if event.safety_context.get("blocked", False):
            return {
                "status": "blocked",
                "reason": "runtime blocked by safety_context",
                "selected_action": actions[0].to_dict(),
                "candidate_count": len(actions),
            }

        selected = actions[0]
        if (
            selected.action_type in self.approval_required
            or selected.requires_approval
            or selected.risk_level == "high"
        ):
            return {
                "status": "approval_required",
                "reason": "selected candidate is approval-gated",
                "selected_action": selected.to_dict(),
                "candidate_count": len(actions),
                "approval_required_count": sum(
                    1
                    for item in actions
                    if item.requires_approval or item.action_type in self.approval_required
                ),
            }

        if selected.action_type in self.auto_allow:
            return {
                "status": "approved",
                "reason": "selected candidate is auto-allow in seed phase",
                "selected_action": selected.to_dict(),
                "candidate_count": len(actions),
            }

        if selected.action_type in self.limited_allow:
            return {
                "status": "approved",
                "reason": "selected candidate is limited-allow in seed phase",
                "selected_action": selected.to_dict(),
                "candidate_count": len(actions),
            }

        return {
            "status": "blocked",
            "reason": "selected candidate is outside seed phase policy surface",
            "selected_action": selected.to_dict(),
            "candidate_count": len(actions),
        }
