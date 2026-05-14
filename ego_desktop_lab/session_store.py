from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.decision_view import DecisionView


DEFAULT_SHELL_SESSION_LOG = Path("temp/ego_desktop_lab/shell_v6/session_log.jsonl")


@dataclass(frozen=True)
class ShellSessionRecord:
    timestamp: str
    provider_mode: str
    user_event: str
    canonical_final_intention: str
    gate_status: str | None
    evidence_log_path: str
    no_action_executed: bool
    claim_ceiling: str
    strict_admission_summary: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def shell_session_record_from_view(
    view: DecisionView,
    *,
    provider_mode: str,
    timestamp: str,
    strict_admission_summary: Mapping[str, object] | None = None,
) -> ShellSessionRecord:
    canonical = view.canonical_decision
    selected = canonical.get("after_selected_intention")
    gate = view.gate_decision or {}
    return ShellSessionRecord(
        timestamp=timestamp,
        provider_mode=provider_mode,
        user_event=view.user_event or "",
        canonical_final_intention=_selected_goal(selected),
        gate_status=_optional_str(gate.get("status")),
        evidence_log_path=view.evidence_log_path,
        no_action_executed=bool(view.no_action_executed),
        claim_ceiling=view.claim_ceiling,
        strict_admission_summary=dict(strict_admission_summary) if strict_admission_summary else None,
    )


def append_shell_session_record(path: Path, record: ShellSessionRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")


def read_recent_shell_sessions(path: Path, limit: int) -> tuple[ShellSessionRecord, ...]:
    if limit <= 0 or not path.exists():
        return ()
    records: list[ShellSessionRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            record = _record_from_mapping(payload)
            if record is not None:
                records.append(record)
    return tuple(records[-limit:])


def format_recent_shell_sessions(records: tuple[ShellSessionRecord, ...]) -> str:
    lines = [
        "## Recent Shell Evidence",
        "",
    ]
    if not records:
        lines.append("No recent shell session records.")
        return "\n".join(lines)
    for record in records:
        lines.extend(
            [
                f"- timestamp: {record.timestamp}",
                f"  provider_mode: {record.provider_mode}",
                f"  user_event: {record.user_event}",
                f"  canonical_final_intention: {record.canonical_final_intention}",
                f"  gate_status: {record.gate_status or 'none'}",
                f"  no_action_executed: {_bool_text(record.no_action_executed)}",
                f"  evidence_log_path: {record.evidence_log_path}",
            ]
        )
    return "\n".join(lines)


def _record_from_mapping(payload: Mapping[str, Any]) -> ShellSessionRecord | None:
    try:
        return ShellSessionRecord(
            timestamp=str(payload["timestamp"]),
            provider_mode=str(payload["provider_mode"]),
            user_event=str(payload["user_event"]),
            canonical_final_intention=str(payload["canonical_final_intention"]),
            gate_status=_optional_str(payload.get("gate_status")),
            evidence_log_path=str(payload["evidence_log_path"]),
            no_action_executed=bool(payload["no_action_executed"]),
            claim_ceiling=str(payload["claim_ceiling"]),
            strict_admission_summary=_optional_dict(payload.get("strict_admission_summary")),
        )
    except KeyError:
        return None


def _selected_goal(selected: object) -> str:
    if isinstance(selected, Mapping):
        goal = selected.get("goal")
        if goal is not None:
            return str(goal)
    return "unknown"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): item for key, item in value.items()}


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
