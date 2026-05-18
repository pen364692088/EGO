from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core_bus.events import BusEvent


def _safe_session_filename(session_key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", session_key.strip())
    return normalized[:180] or "session"


class SessionLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: BusEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def tail(self, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0 or not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out: List[Dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
        return out


class SessionLogManager:
    def __init__(self, root: Optional[Path] = None) -> None:
        base = root or Path("data") / "session_logs"
        self.root = base
        self.root.mkdir(parents=True, exist_ok=True)

    def get_log(self, session_key: str) -> SessionLog:
        filename = f"{_safe_session_filename(session_key)}.jsonl"
        return SessionLog(self.root / filename)

    def append(self, event: BusEvent) -> Path:
        log = self.get_log(event.session_key)
        log.append(event)
        return log.path
