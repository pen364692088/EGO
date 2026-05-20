"""
Candidate-local operator memory for EgoOperator.

This module is deliberately scoped to EgoOperator. It is not the EGO formal
memory authority and must not write PROJECT_MEMORY, OpenEmotion memory, or the
repo evidence ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json
import hashlib
import re


DEFAULT_CORE_MAX_CHARS = 3000
DEFAULT_EPISODE_MAX_CHARS = 3000
DEFAULT_KEEP_LAST_MESSAGES = 10
DEFAULT_MAX_CONTEXT_TOKENS = 200_000
DEFAULT_COMPACTION_THRESHOLD = 0.7
DEFAULT_HOT_CONTEXT_MAX_ITEMS = 5
DEFAULT_HOT_CONTEXT_MIN_HITS = 2
DEFAULT_MEMORY_ITEM_MAX_CHARS = 800
DEFAULT_STALE_PREFERENCE_DECAY_DAYS = 30

CONTINUITY_QUERY_PATTERNS = (
    r"记得",
    r"还记得",
    r"记住",
    r"我是谁",
    r"我的",
    r"偏好",
    r"称呼",
    r"名字",
    r"你好",
    r"继续",
    r"刚才",
    r"之前",
    r"上次",
    r"这个任务",
    r"这个项目",
    r"好了吗",
    r"\bremember\b",
    r"\bmy\b",
    r"\bcontinue\b",
    r"\bprevious\b",
    r"\bproject\b",
)

CANDIDATE_MEMORY_SIGNAL_PATTERNS = (
    r"我喜欢",
    r"我不喜欢",
    r"我偏好",
    r"我希望",
    r"我的目标",
    r"我正在",
    r"我习惯",
    r"对我来说",
    r"以后请",
    r"以后不要",
    r"不要再",
    r"其实",
    r"纠正",
    r"更正",
    r"\bi prefer\b",
    r"\bmy preference\b",
    r"\bmy goal\b",
    r"\bi am working on\b",
    r"\bi'm working on\b",
)
PREFERENCE_CATEGORY_CUES = {
    "language_preference": ("中文", "英文", "语言", "language"),
    "answer_style_preference": ("结论先行", "少废话", "详细", "简洁", "解释多", "直接", "style"),
    "tool_preference": ("工具", "审批", "自动执行", "不要自动", "tool", "approval"),
    "workflow_preference": ("先规划", "先测试", "一步一步", "提交", "推送", "workflow", "commit", "push"),
    "greeting_preference": ("打招呼", "问候", "称呼", "你好", "greeting"),
}

MEMORY_CORRECTION_PATTERNS = (
    r"不是",
    r"改成",
    r"纠正",
    r"更正",
    r"其实",
    r"以后不要",
    r"不要再",
    r"\binstead\b",
    r"\bcorrection\b",
    r"\bactually\b",
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now(clock: Clock) -> str:
    return clock().astimezone(timezone.utc).isoformat(timespec="seconds")


def _date_key(clock: Clock) -> str:
    return clock().astimezone(timezone.utc).strftime("%Y-%m-%d")


def _time_key(clock: Clock) -> str:
    return clock().astimezone(timezone.utc).strftime("%H:%M")


def _resolve_under(path: str | Path, root: str | Path) -> Path:
    resolved = Path(path).resolve()
    root_path = Path(root).resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"memory path outside EgoOperator workspace: {resolved}") from exc
    return resolved


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        pass

    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "__dict__"):
        return {
            str(k): _json_safe(v)
            for k, v in value.__dict__.items()
            if not str(k).startswith("_")
        }
    return str(value)


def _bounded(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if max_chars <= 0 or len(clean) <= max_chars:
        return clean
    return clean[:max_chars] + "\n...[truncated]"


def _query_tokens(text: str) -> List[str]:
    lowered = (text or "").lower()
    tokens = re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", lowered)
    return [token for token in tokens if token.strip()]


def _relevance_score(content: str, query_tokens: List[str]) -> int:
    if not query_tokens:
        return 0
    lowered = (content or "").lower()
    return sum(25 for token in query_tokens if token in lowered)


def _has_continuity_query_intent(query_text: str) -> bool:
    text = (query_text or "").strip()
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in CONTINUITY_QUERY_PATTERNS)


def _context_section_decision(content: str, query_text: str, *, section: str) -> Dict[str, Any]:
    clean = (content or "").strip()
    query = (query_text or "").strip()
    query_tokens = _query_tokens(query)
    relevance = _relevance_score(clean, query_tokens)
    continuity_intent = _has_continuity_query_intent(query)
    if not clean:
        return {
            "section": section,
            "included": False,
            "reason": "empty",
            "relevance_score": 0,
            "query_has_continuity_intent": continuity_intent,
        }
    if not query:
        return {
            "section": section,
            "included": True,
            "reason": "operator_context_command",
            "relevance_score": 0,
            "query_has_continuity_intent": continuity_intent,
        }
    if continuity_intent:
        return {
            "section": section,
            "included": True,
            "reason": "continuity_query_intent",
            "relevance_score": relevance,
            "query_has_continuity_intent": True,
        }
    if relevance > 0:
        return {
            "section": section,
            "included": True,
            "reason": "query_overlap",
            "relevance_score": relevance,
            "query_has_continuity_intent": False,
        }
    return {
        "section": section,
        "included": False,
        "reason": "not_relevant_to_query",
        "relevance_score": 0,
        "query_has_continuity_intent": False,
    }


def _is_memory_correction(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in MEMORY_CORRECTION_PATTERNS)


def _memory_key_from_content(text: str) -> str:
    value = (text or "").casefold()
    if not value:
        return ""
    if any(token in value for token in ("打招呼", "问候", "greeting")):
        return "greeting_preference"
    if any(token in value for token in ("名字", "称呼", "叫我", "name")):
        return "user_name"
    if any(token in value for token in ("中文", "英文", "语言", "language")):
        return "language_preference"
    if "claim ceiling" in value or "claim_ceiling" in value:
        return "claim_ceiling_preference"
    if any(token in value for token in ("工具", "tool", "审批", "approval")):
        return "tool_preference"
    return ""


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _age_days(ts: str, *, clock: Clock) -> int:
    parsed = _parse_iso_datetime(ts)
    if parsed is None:
        return 0
    delta = clock().astimezone(timezone.utc) - parsed
    return max(0, delta.days)


def _is_core_memory_note_line(line: str) -> bool:
    return line.lstrip().startswith("- ")


def extract_candidate_memory_from_turn(user_text: str) -> str:
    candidate = extract_preference_candidate_from_turn(user_text)
    if candidate.get("status") != "candidate":
        return ""
    return str(candidate["content"])


def extract_preference_candidate_from_turn(user_text: str) -> Dict[str, Any]:
    text = (user_text or "").strip()
    if not text:
        return {"status": "ignored", "reason": "empty"}
    lowered = text.lower()
    if not any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in CANDIDATE_MEMORY_SIGNAL_PATTERNS):
        return {"status": "ignored", "reason": "no_candidate_signal"}
    if "?" in text and not any(marker in text for marker in ("我喜欢", "我不喜欢", "我偏好", "我希望", "我的目标", "我正在", "我习惯")):
        return {"status": "ignored", "reason": "question_without_preference_signal"}
    memory_key = _memory_key_from_content(text)
    category = memory_key or "general_preference"
    cue_hits = {}
    for cue_category, cues in PREFERENCE_CATEGORY_CUES.items():
        matches = [cue for cue in cues if cue.casefold() in text.casefold()]
        if matches:
            cue_hits[cue_category] = matches
    if not memory_key and cue_hits:
        category = sorted(cue_hits.items(), key=lambda item: (len(item[1]), item[0]), reverse=True)[0][0]
    confidence = min(0.9, 0.45 + (0.15 if memory_key else 0) + len(cue_hits) * 0.08)
    return {
        "status": "candidate",
        "schema_version": "ego_operator.preference_candidate.v1",
        "content": "user_signal: " + _bounded(text, DEFAULT_MEMORY_ITEM_MAX_CHARS),
        "category": category,
        "memory_key": memory_key,
        "confidence": round(confidence, 2),
        "cue_hits": cue_hits,
        "candidate_only": True,
        "core_memory_write": "forbidden_without_operator_remember_or_approval",
        "claim_ceiling": "candidate preference extraction only; not durable learning proof",
    }


@dataclass
class MemoryContext:
    core: str = ""
    today_episode: str = ""
    hot_items: List[Dict[str, Any]] = field(default_factory=list)
    memory_dir: str = ""
    core_max_chars: int = DEFAULT_CORE_MAX_CHARS
    episode_max_chars: int = DEFAULT_EPISODE_MAX_CHARS
    injection: Dict[str, Any] = field(default_factory=dict)

    def render_for_prompt(self) -> str:
        core = _bounded(self.core, self.core_max_chars)
        episode = _bounded(self.today_episode, self.episode_max_chars)
        hot_items = [
            item for item in self.hot_items
            if str(item.get("content", "")).strip()
        ]
        if not core and not episode and not hot_items:
            return ""

        parts = [
            "[Operator Memory Context]",
            "Scope: candidate-local EgoOperator operator memory only.",
            "Authority: not repo authority, not OpenEmotion memory, not evidence ledger.",
        ]
        if self.memory_dir:
            parts.append(f"Storage: {self.memory_dir}")
        if core:
            parts.append("\n[Core MEMORY.md]\n" + core)
        if hot_items:
            lines = ["\n[Hot Context Memory]"]
            for item in hot_items:
                memory_id = item.get("id", "unknown")
                flags = []
                if item.get("pinned"):
                    flags.append("pinned")
                if item.get("hit_count", 0):
                    flags.append(f"hits={item.get('hit_count')}")
                flag_text = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"- [{memory_id}]{flag_text} {_bounded(str(item.get('content', '')), DEFAULT_MEMORY_ITEM_MAX_CHARS)}")
            parts.append("\n".join(lines))
        if episode:
            parts.append("\n[Today Episodic Summary]\n" + episode)
        return "\n".join(parts).strip()


class OperatorMemoryStore:
    def __init__(
        self,
        memory_dir: str | Path,
        *,
        containment_root: str | Path,
        clock: Clock = _utc_now,
    ) -> None:
        self.memory_dir = _resolve_under(memory_dir, containment_root)
        self.clock = clock
        self.history_file = self.memory_dir / "history.jsonl"
        self.episodic_dir = self.memory_dir / "episodic"
        self.core_file = self.memory_dir / "MEMORY.md"
        self.telemetry_dir = self.memory_dir / "telemetry"
        self.tokens_file = self.telemetry_dir / "tokens.jsonl"
        self.candidate_core_updates_file = self.memory_dir / "candidate_core_updates.jsonl"
        self.candidate_memory_file = self.memory_dir / "candidate_memory.jsonl"
        self.memory_events_file = self.memory_dir / "memory_events.jsonl"
        self.cold_archive_file = self.memory_dir / "cold_archive.jsonl"

    def _ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, path: Path, row: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_parent(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_json_safe(row), ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def _iter_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _new_memory_id(self, content: str, ts: str) -> str:
        digest = hashlib.sha1(f"{ts}\n{content}".encode("utf-8")).hexdigest()[:12]
        return f"mem_{digest}"

    def append_raw_turn(
        self,
        *,
        session_id: str,
        role: str,
        content: Any,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = {
            "ts": timestamp or _iso_now(self.clock),
            "session_id": session_id,
            "role": role,
            "content": _json_safe(content),
            "metadata": _json_safe(metadata or {}),
        }
        self._ensure_parent(self.history_file)
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def append_compact_marker(
        self,
        *,
        session_id: str,
        event_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = {
            "ts": _iso_now(self.clock),
            "session_id": session_id,
            "event_id": event_id,
            "type": "compact_event",
            "metadata": _json_safe(metadata or {}),
        }
        self._ensure_parent(self.history_file)
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def load_core(self) -> str:
        if not self.core_file.exists():
            return ""
        return self.core_file.read_text(encoding="utf-8")

    def save_core(self, content: str, *, source: str = "manual") -> Dict[str, Any]:
        if source not in {"manual", "operator", "test"}:
            raise ValueError("core memory can only be written by an explicit operator gate")
        text = (content or "").strip()
        self._ensure_parent(self.core_file)
        self.core_file.write_text(text + ("\n" if text else ""), encoding="utf-8")
        return {
            "status": "ok",
            "path": str(self.core_file),
            "source": source,
            "chars": len(text),
        }

    def remember(self, text: str, *, source: str = "operator") -> Dict[str, Any]:
        clean = (text or "").strip()
        if not clean:
            return {"status": "failed", "reason": "empty_memory_note"}

        current = self.load_core().strip()
        if not current:
            current = (
                "# EgoOperator Operator Memory\n\n"
                "Candidate-local notes only. This file is not EGO repo authority.\n"
            )
        memory_key = _memory_key_from_content(clean)
        correction = _is_memory_correction(clean)
        core_quarantine = {"status": "skipped", "reason": "not_a_keyed_correction"}
        if memory_key and correction:
            active_lines: List[str] = []
            quarantined: List[Dict[str, Any]] = []
            ts = _iso_now(self.clock)
            for line in current.splitlines():
                if _is_core_memory_note_line(line) and _memory_key_from_content(line) == memory_key:
                    archive_row = {
                        "ts": ts,
                        "layer": "core",
                        "status": "cold_archive",
                        "archived": True,
                        "action": "quarantine_core_conflict",
                        "reason": "superseded_by_operator_correction",
                        "memory_key": memory_key,
                        "content": line.strip(),
                        "replacement": clean,
                        "source": source,
                    }
                    self._append_jsonl(self.cold_archive_file, archive_row)
                    quarantined.append(archive_row)
                else:
                    active_lines.append(line)
            if quarantined:
                current = "\n".join(active_lines).strip()
            core_quarantine = {
                "status": "ok",
                "memory_key": memory_key,
                "count": len(quarantined),
                "archive_path": str(self.cold_archive_file),
            }
        note = f"- {_iso_now(self.clock)} [{source}] {clean}"
        result = self.save_core(current.rstrip() + "\n\n" + note, source="operator")
        result["memory_key"] = memory_key or None
        result["correction"] = correction
        result["core_conflicts_quarantined"] = core_quarantine
        if memory_key and correction:
            result["candidate_conflicts_quarantined"] = self.quarantine_candidate_conflicts(
                memory_key,
                replacement_content=clean,
                reason="superseded_by_operator_correction",
            )
        return result

    def episode_path(self, date_key: Optional[str] = None) -> Path:
        return self.episodic_dir / f"{date_key or _date_key(self.clock)}.md"

    def load_today_episode(self) -> str:
        path = self.episode_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_episodic(
        self,
        summary: str,
        *,
        date_key: Optional[str] = None,
        source: str,
        input_refs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean = (summary or "").strip()
        if not clean:
            return {"status": "skipped", "reason": "empty_episode"}
        path = self.episode_path(date_key)
        if path.exists():
            existing = path.read_text(encoding="utf-8").rstrip()
        else:
            existing = f"# {path.stem} Episodic Memory"
        block = (
            f"## {_time_key(self.clock)} {source}\n\n"
            f"{clean}\n\n"
            f"refs: `{json.dumps(_json_safe(input_refs or {}), ensure_ascii=False, sort_keys=True)}`"
        )
        self._ensure_parent(path)
        path.write_text(existing + "\n\n" + block.strip() + "\n", encoding="utf-8")
        return {
            "status": "ok",
            "path": str(path),
            "source": source,
            "chars": len(clean),
        }

    def append_candidate_core_update(
        self,
        content: str,
        *,
        source: str,
        status: str = "candidate",
        event_id: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = {
            "ts": _iso_now(self.clock),
            "event_id": event_id,
            "source": source,
            "status": status,
            "content": content,
            "error": _json_safe(error or {}),
        }
        self._ensure_parent(self.candidate_core_updates_file)
        with self.candidate_core_updates_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def propose_candidate_memory(
        self,
        content: str,
        *,
        source: str,
        event_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean = _bounded(content, DEFAULT_MEMORY_ITEM_MAX_CHARS)
        if not clean:
            return {"status": "skipped", "reason": "empty_candidate_memory"}
        ts = _iso_now(self.clock)
        memory_key = _memory_key_from_content(clean)
        correction = _is_memory_correction(clean)
        row = {
            "id": self._new_memory_id(clean, ts),
            "ts": ts,
            "layer": "candidate",
            "status": "candidate",
            "content": clean,
            "source": source,
            "event_id": event_id,
            "session_id": session_id,
            "pinned": False,
            "archived": False,
            "hit_count": 0,
            "last_hit_ts": None,
            "metadata": _json_safe({
                **(metadata or {}),
                "memory_key": memory_key or None,
                "correction": correction,
            }),
        }
        result = self._append_jsonl(self.candidate_memory_file, row)
        if memory_key:
            conflict_reason = (
                "superseded_by_candidate_correction"
                if correction
                else "superseded_by_new_candidate_same_key"
            )
            result["conflicts_quarantined"] = self.quarantine_candidate_conflicts(
                memory_key,
                replacement_content=clean,
                replacement_memory_id=str(row["id"]),
                reason=conflict_reason,
            )
        return result

    def auto_capture_candidate_from_turn(
        self,
        *,
        session_id: str,
        event_id: str,
        user_text: str,
        assistant_text: str = "",
    ) -> Dict[str, Any]:
        preference_candidate = extract_preference_candidate_from_turn(user_text)
        if preference_candidate.get("status") != "candidate":
            return {"status": "skipped", "reason": preference_candidate.get("reason", "no_candidate_memory_signal")}
        return self.propose_candidate_memory(
            str(preference_candidate["content"]),
            source="auto_candidate_extractor",
            event_id=event_id,
            session_id=session_id,
            metadata={
                "raw_user_text": _bounded(user_text, DEFAULT_MEMORY_ITEM_MAX_CHARS),
                "assistant_preview": _bounded(assistant_text, 240),
                "preference_candidate": preference_candidate,
            },
        )

    def _append_memory_event(
        self,
        memory_id: str,
        *,
        action: str,
        event_id: Optional[str] = None,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = {
            "ts": _iso_now(self.clock),
            "memory_id": memory_id,
            "action": action,
            "event_id": event_id,
            "reason": reason,
            "metadata": _json_safe(metadata or {}),
        }
        return self._append_jsonl(self.memory_events_file, row)

    def _candidate_state(self) -> Dict[str, Dict[str, Any]]:
        state: Dict[str, Dict[str, Any]] = {}
        for row in self._iter_jsonl(self.candidate_memory_file):
            memory_id = str(row.get("id", "")).strip()
            if not memory_id:
                continue
            item = dict(row)
            item.setdefault("pinned", False)
            item.setdefault("archived", False)
            item.setdefault("hit_count", 0)
            item.setdefault("status", "candidate")
            state[memory_id] = item

        for event in self._iter_jsonl(self.memory_events_file):
            memory_id = str(event.get("memory_id", "")).strip()
            if memory_id not in state:
                continue
            action = str(event.get("action", ""))
            item = state[memory_id]
            if action == "pin":
                item["pinned"] = True
                item["archived"] = False
                item["status"] = "candidate"
            elif action == "unpin":
                item["pinned"] = False
            elif action == "archive":
                item["pinned"] = False
                item["archived"] = True
                item["status"] = "cold_archive"
            elif action == "approve":
                item["pinned"] = False
                item["archived"] = False
                item["status"] = "approved"
            elif action == "forget":
                item["pinned"] = False
                item["archived"] = True
                item["status"] = "forgotten"
            elif action == "hit":
                item["hit_count"] = int(item.get("hit_count", 0) or 0) + 1
                item["last_hit_ts"] = event.get("ts")
        return state

    def quarantine_candidate_conflicts(
        self,
        memory_key: str,
        *,
        replacement_content: str,
        replacement_memory_id: Optional[str] = None,
        reason: str,
    ) -> Dict[str, Any]:
        key = (memory_key or "").strip()
        if not key:
            return {"status": "skipped", "reason": "missing_memory_key"}
        quarantined: List[Dict[str, Any]] = []
        for item in self._candidate_state().values():
            if item.get("status") != "candidate" or item.get("archived"):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if metadata.get("memory_key") != key:
                continue
            if replacement_memory_id and item.get("id") == replacement_memory_id:
                continue
            event = self._append_memory_event(
                str(item.get("id")),
                action="archive",
                reason=reason,
                metadata={
                    "memory_key": key,
                    "replacement_memory_id": replacement_memory_id,
                    "replacement_preview": _bounded(replacement_content, 240),
                },
            )
            archived = dict(item)
            archived["archived_by_event"] = event
            archived["archive_reason"] = reason
            self._append_jsonl(self.cold_archive_file, archived)
            quarantined.append({"memory_id": item.get("id"), "event": event})
        return {
            "status": "ok",
            "memory_key": key,
            "count": len(quarantined),
            "items": quarantined,
            "archive_path": str(self.cold_archive_file),
        }

    def list_candidate_memories(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        items = list(self._candidate_state().values())
        if not include_archived:
            items = [
                item for item in items
                if item.get("status") == "candidate" and not item.get("archived")
            ]
        items.sort(
            key=lambda item: (
                bool(item.get("pinned")),
                int(item.get("hit_count", 0) or 0),
                str(item.get("last_hit_ts") or item.get("ts") or ""),
            ),
            reverse=True,
        )
        return items[: max(0, limit)]

    def pin_memory(self, memory_id: str, *, reason: str = "operator_pin") -> Dict[str, Any]:
        if memory_id not in self._candidate_state():
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        return {"status": "ok", "event": self._append_memory_event(memory_id, action="pin", reason=reason)}

    def unpin_memory(self, memory_id: str, *, reason: str = "operator_unpin") -> Dict[str, Any]:
        if memory_id not in self._candidate_state():
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        return {"status": "ok", "event": self._append_memory_event(memory_id, action="unpin", reason=reason)}

    def archive_memory(self, memory_id: str, *, reason: str = "operator_archive") -> Dict[str, Any]:
        state = self._candidate_state()
        if memory_id not in state:
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        event = self._append_memory_event(memory_id, action="archive", reason=reason)
        archived = dict(state[memory_id])
        archived["archived_by_event"] = event
        self._append_jsonl(self.cold_archive_file, archived)
        return {"status": "ok", "event": event, "archive_path": str(self.cold_archive_file)}

    def approve_candidate_memory(self, memory_id: str, *, reason: str = "operator_approved_candidate") -> Dict[str, Any]:
        state = self._candidate_state()
        item = state.get(memory_id)
        if item is None:
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        if item.get("status") != "candidate" or item.get("archived"):
            return {"status": "blocked", "reason": f"candidate_not_approvable:{item.get('status')}", "memory_id": memory_id}
        content = re.sub(r"^user_signal:\s*", "", str(item.get("content") or "").strip(), flags=re.IGNORECASE)
        if not content:
            return {"status": "blocked", "reason": "empty_candidate_content", "memory_id": memory_id}
        core_result = self.remember(content, source="operator_candidate_approval")
        event = self._append_memory_event(
            memory_id,
            action="approve",
            reason=reason,
            metadata={"core_result": core_result},
        )
        return {
            "status": "ok",
            "memory_id": memory_id,
            "approved_content": content,
            "core_memory": core_result,
            "event": event,
            "claim_ceiling": "candidate-local operator memory approval only; not durable learning proof",
        }

    def forget_memory(self, memory_id: str, *, reason: str = "operator_forget") -> Dict[str, Any]:
        if memory_id not in self._candidate_state():
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        return {"status": "ok", "event": self._append_memory_event(memory_id, action="forget", reason=reason)}

    def record_memory_hit(
        self,
        memory_id: str,
        *,
        event_id: Optional[str] = None,
        query: str = "",
    ) -> Dict[str, Any]:
        if memory_id not in self._candidate_state():
            return {"status": "failed", "reason": "unknown_memory_id", "memory_id": memory_id}
        return {
            "status": "ok",
            "event": self._append_memory_event(
                memory_id,
                action="hit",
                event_id=event_id,
                reason="context_injection",
                metadata={"query": _bounded(query, 240)},
            ),
        }

    def select_hot_context(
        self,
        *,
        query_text: str = "",
        max_items: int = DEFAULT_HOT_CONTEXT_MAX_ITEMS,
        min_hits: int = DEFAULT_HOT_CONTEXT_MIN_HITS,
    ) -> List[Dict[str, Any]]:
        query_tokens = _query_tokens(query_text)
        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in self._candidate_state().values():
            if item.get("status") != "candidate" or item.get("archived"):
                continue
            content = str(item.get("content", ""))
            hit_count = int(item.get("hit_count", 0) or 0)
            relevance = _relevance_score(content, query_tokens)
            age_days = _age_days(str(item.get("last_hit_ts") or item.get("ts") or ""), clock=self.clock)
            stale_by_age = age_days >= DEFAULT_STALE_PREFERENCE_DECAY_DAYS and not item.get("pinned")
            hit_hot = hit_count >= min_hits and not stale_by_age
            is_hot = bool(item.get("pinned")) or hit_hot or relevance > 0
            if not is_hot:
                continue
            effective_hits = 0 if stale_by_age else hit_count
            score = relevance + effective_hits * 10 + (1000 if item.get("pinned") else 0)
            enriched = dict(item)
            if stale_by_age:
                enriched["stale_preference_decay"] = {
                    "status": "active",
                    "age_days": age_days,
                    "effect": "hit_count_no_longer_promotes_hot_context_without_query_relevance",
                }
            scored.append((score, enriched))
        scored.sort(key=lambda pair: (pair[0], str(pair[1].get("last_hit_ts") or pair[1].get("ts") or "")), reverse=True)
        return [item for _, item in scored[: max(0, max_items)]]

    def build_context(
        self,
        *,
        query_text: str = "",
        core_max_chars: int = DEFAULT_CORE_MAX_CHARS,
        episode_max_chars: int = DEFAULT_EPISODE_MAX_CHARS,
        hot_context_max_items: int = DEFAULT_HOT_CONTEXT_MAX_ITEMS,
    ) -> MemoryContext:
        core = self.load_core()
        episode = self.load_today_episode()
        core_decision = _context_section_decision(core, query_text, section="core")
        episode_decision = _context_section_decision(episode, query_text, section="today_episode")
        hot_items = self.select_hot_context(query_text=query_text, max_items=hot_context_max_items)
        return MemoryContext(
            core=core if core_decision["included"] else "",
            today_episode=episode if episode_decision["included"] else "",
            hot_items=hot_items,
            memory_dir=str(self.memory_dir),
            core_max_chars=core_max_chars,
            episode_max_chars=episode_max_chars,
            injection={
                "schema_version": "ego_operator.memory_context_injection.v1",
                "query_excerpt": _bounded(query_text, 240),
                "core": core_decision,
                "today_episode": episode_decision,
                "hot_context": {
                    "included": bool(hot_items),
                    "count": len(hot_items),
                    "ids": [item.get("id") for item in hot_items],
                    "reason": "pin_hit_or_query_relevance" if hot_items else "no_hot_items",
                },
            },
        )


class TokenTelemetry:
    def __init__(self, log_file: str | Path, *, clock: Clock = _utc_now) -> None:
        self.log_file = Path(log_file)
        self.clock = clock
        self._last_input_tokens = 0

    @staticmethod
    def estimate_tokens_from_messages(messages: List[Dict[str, Any]]) -> int:
        total_chars = 0
        for message in messages:
            total_chars += len(str(message.get("role", "")))
            total_chars += len(str(message.get("content", "")))
        return max(1, total_chars // 4) if total_chars else 0

    @staticmethod
    def _int_from(usage: Dict[str, Any], keys: List[str]) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                return value
        return 0

    def record(
        self,
        *,
        event_id: str,
        model: str,
        provider: str,
        usage: Optional[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        compact_triggered: bool = False,
    ) -> Dict[str, Any]:
        usage_data = usage or {}
        input_tokens = self._int_from(usage_data, ["input_tokens", "prompt_tokens", "input"])
        output_tokens = self._int_from(usage_data, ["output_tokens", "completion_tokens", "output"])
        cache_read = self._int_from(usage_data, ["cache_read_input_tokens", "cache_read"])
        cache_create = self._int_from(usage_data, ["cache_creation_input_tokens", "cache_create"])
        total_tokens = self._int_from(usage_data, ["total_tokens", "total"])

        approx = False
        if input_tokens <= 0:
            input_tokens = self.estimate_tokens_from_messages(messages)
            approx = True
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens + cache_read + cache_create

        self._last_input_tokens = input_tokens + cache_read + cache_create
        row = {
            "ts": _iso_now(self.clock),
            "event_id": event_id,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_create,
            "total_tokens": total_tokens,
            "approximate": approx,
            "compact_triggered": compact_triggered,
        }
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def should_compact(
        self,
        *,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    ) -> bool:
        return self._last_input_tokens > max_context_tokens * threshold


class MemoryCompactor:
    def __init__(
        self,
        store: OperatorMemoryStore,
        *,
        keep_last: int = DEFAULT_KEEP_LAST_MESSAGES,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    ) -> None:
        self.store = store
        self.keep_last = keep_last
        self.max_context_tokens = max_context_tokens
        self.threshold = threshold

    def should_compact(
        self,
        messages: List[Dict[str, Any]],
        *,
        usage: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> bool:
        if force:
            return len(messages) > self.keep_last
        if len(messages) <= self.keep_last:
            return False
        usage_data = usage or {}
        input_tokens = TokenTelemetry._int_from(usage_data, ["input_tokens", "prompt_tokens", "input"])
        if input_tokens <= 0:
            input_tokens = TokenTelemetry.estimate_tokens_from_messages(messages)
        return input_tokens > self.max_context_tokens * self.threshold

    def compact(
        self,
        messages: List[Dict[str, Any]],
        *,
        session_id: str,
        event_id: str,
        usage: Optional[Dict[str, Any]] = None,
        force: bool = False,
        llm: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not self.should_compact(messages, usage=usage, force=force):
            return {"status": "skipped", "reason": "below_compaction_threshold"}
        if len(messages) <= self.keep_last:
            return {"status": "skipped", "reason": "not_enough_messages"}

        old_messages = messages[:-self.keep_last]
        recent_messages = messages[-self.keep_last :]

        if llm is not None:
            llm_result = self._compact_with_llm(old_messages, session_id=session_id, event_id=event_id, llm=llm)
            if llm_result["status"] != "ok":
                return {
                    "status": "error",
                    "reason": "malformed_compaction_output",
                    "kept_messages": messages,
                    "error": llm_result,
                }
            episode = llm_result["episode"]
            candidate = llm_result["candidate_core_update"]
            source = "llm_compactor"
        else:
            episode = self._deterministic_episode(old_messages)
            candidate = self._deterministic_candidate(old_messages)
            source = "deterministic_compactor"

        episode_result = self.store.write_episodic(
            episode,
            source=source,
            input_refs={
                "event_id": event_id,
                "old_message_count": len(old_messages),
                "kept_message_count": len(recent_messages),
            },
        )
        candidate_result = self.store.append_candidate_core_update(
            candidate,
            source=source,
            status="candidate",
            event_id=event_id,
        )
        self.store.append_compact_marker(
            session_id=session_id,
            event_id=event_id,
            metadata={
                "old_message_count": len(old_messages),
                "kept_message_count": len(recent_messages),
                "source": source,
            },
        )
        return {
            "status": "compacted",
            "source": source,
            "old_message_count": len(old_messages),
            "kept_message_count": len(recent_messages),
            "kept_messages": recent_messages,
            "episode": episode_result,
            "candidate_core_update": {
                "path": str(self.store.candidate_core_updates_file),
                "status": candidate_result["status"],
            },
        }

    def _compact_with_llm(
        self,
        old_messages: List[Dict[str, Any]],
        *,
        session_id: str,
        event_id: str,
        llm: Any,
    ) -> Dict[str, Any]:
        prompt = (
            "Compress these EgoOperator operator-memory messages into strict JSON.\n"
            "Return exactly: {\"episode\": \"...\", \"candidate_core_update\": \"...\"}.\n"
            "Do not overwrite MEMORY.md. Candidate core update is for operator review only.\n\n"
            f"session_id={session_id}\nevent_id={event_id}\n"
            f"messages={json.dumps(_json_safe(old_messages), ensure_ascii=False)}"
        )
        try:
            text = llm.complete(prompt)
            data = json.loads(text)
            episode = str(data["episode"]).strip()
            candidate = str(data["candidate_core_update"]).strip()
            if not episode:
                raise ValueError("empty episode")
        except Exception as exc:
            error = {
                "error_type": type(exc).__name__,
                "error": repr(exc),
            }
            self.store.append_candidate_core_update(
                "",
                source="llm_compactor",
                status="error",
                event_id=event_id,
                error=error,
            )
            return {"status": "error", **error}
        return {
            "status": "ok",
            "episode": episode,
            "candidate_core_update": candidate,
        }

    def _deterministic_episode(self, old_messages: List[Dict[str, Any]]) -> str:
        lines = ["Deterministic compaction summary:"]
        for message in old_messages:
            role = str(message.get("role", "?"))
            content = _bounded(str(message.get("content", "")), 240).replace("\n", " ")
            lines.append(f"- {role}: {content}")
        return "\n".join(lines)

    def _deterministic_candidate(self, old_messages: List[Dict[str, Any]]) -> str:
        return (
            "Candidate core update generated by deterministic compaction. "
            f"Review before promotion. old_message_count={len(old_messages)}"
        )
