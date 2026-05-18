from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Tuple


WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() -]+[\\/])*[A-Za-z0-9._() -]+")
UNIX_PATH_RE = re.compile(r"(?:/mnt|/home|/tmp|/Users)(?:/[A-Za-z0-9._() -]+)+")
ATTACHMENT_MARKERS = ("[用户发送了文件:", "[附件:")


@dataclass(frozen=True)
class NormalizedUserTurn:
    raw_text: str
    text: str
    lower_text: str
    compact_lower: str
    probe_key: str
    control_key: str
    explicit_paths: Tuple[str, ...]
    has_attachment: bool
    is_slash_command: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "lower_text": self.lower_text,
            "compact_lower": self.compact_lower,
            "probe_key": self.probe_key,
            "control_key": self.control_key,
            "explicit_paths": list(self.explicit_paths),
            "has_attachment": self.has_attachment,
            "is_slash_command": self.is_slash_command,
        }


def normalize_user_turn(text: str) -> NormalizedUserTurn:
    raw_text = text or ""
    normalized_text = raw_text.strip()
    lower_text = normalized_text.lower()
    compact_lower = re.sub(r"\s+", "", lower_text)
    probe_key = compact_lower.strip("?!？！。,.，")
    control_key = compact_lower.strip("?!？！。,.，\"'“”‘’")
    explicit_paths = tuple(_extract_explicit_paths(raw_text))
    has_attachment = any(marker in raw_text for marker in ATTACHMENT_MARKERS)
    is_slash_command = normalized_text.startswith("/")
    return NormalizedUserTurn(
        raw_text=raw_text,
        text=normalized_text,
        lower_text=lower_text,
        compact_lower=compact_lower,
        probe_key=probe_key,
        control_key=control_key,
        explicit_paths=explicit_paths,
        has_attachment=has_attachment,
        is_slash_command=is_slash_command,
    )


def _extract_explicit_paths(text: str) -> list[str]:
    paths: list[str] = []
    for pattern in (WINDOWS_PATH_RE, UNIX_PATH_RE):
        for match in pattern.finditer(text or ""):
            candidate = match.group(0).strip().rstrip(".,!?，。！？")
            if candidate not in paths:
                paths.append(candidate)
    return paths
