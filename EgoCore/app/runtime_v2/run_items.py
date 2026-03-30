from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import hashlib
import re
import time
from typing import Any, Dict, List, Optional


EXPLICIT_OUTPUT_FILENAME_RE = re.compile(r"(?<![A-Za-z0-9_.\\/\\-])([A-Za-z0-9][A-Za-z0-9 _.-]{0,120}\.[A-Za-z0-9]{1,8})")
WINDOWS_TARGET_DIRECTORY_RE = re.compile(r"([A-Za-z]:\\[^\"\n\r]+?)(?=\s*目录下)")
LOOKALIKE_PAGE_RE = re.compile(r"参照\s*([A-Za-z0-9_-]+)\s*的?\s*html页面", re.IGNORECASE)
VERIFY_PREVIOUS_FILE_RE = re.compile(r"读取(?:这个|该)?文件确认内容")
FIRST_LINE_RE = re.compile(r"第一行是\s*([^\n，。,]+)")
SECOND_LINE_RE = re.compile(r"第二行是\s*([^\n，。,]+)")
THIRD_LINE_RE = re.compile(r"第三行是\s*([^\n，。,]+)")


def _normalize_slug(text: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", text.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "output"


def _path_content_hash(path: Path) -> Optional[str]:
    try:
        if not path.exists() or not path.is_file():
            return None
        if path.stat().st_size > 65536:
            return None
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except Exception:
        return None


@dataclass
class VerificationBaseline:
    path: str
    exists: bool
    mtime_ns: Optional[int] = None
    size: Optional[int] = None
    content_hash: Optional[str] = None

    @classmethod
    def capture(cls, path: str) -> "VerificationBaseline":
        file_path = Path(path)
        if not file_path.exists():
            return cls(path=path, exists=False)
        stat = file_path.stat()
        return cls(
            path=path,
            exists=True,
            mtime_ns=getattr(stat, "st_mtime_ns", None),
            size=stat.st_size,
            content_hash=_path_content_hash(file_path),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "mtime_ns": self.mtime_ns,
            "size": self.size,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["VerificationBaseline"]:
        if not data:
            return None
        return cls(
            path=str(data.get("path") or ""),
            exists=bool(data.get("exists")),
            mtime_ns=data.get("mtime_ns"),
            size=data.get("size"),
            content_hash=data.get("content_hash"),
        )


@dataclass
class RunItem:
    item_id: str
    order_index: int
    kind: str
    description: str
    canonical_path: Optional[str] = None
    status: str = "pending"
    baseline_snapshot: Optional[VerificationBaseline] = None
    verification_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0
    last_progress_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    verified_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "order_index": self.order_index,
            "kind": self.kind,
            "description": self.description,
            "canonical_path": self.canonical_path,
            "status": self.status,
            "baseline_snapshot": self.baseline_snapshot.to_dict() if self.baseline_snapshot else None,
            "verification_result": self.verification_result,
            "metadata": dict(self.metadata),
            "attempt_count": self.attempt_count,
            "last_progress_at": self.last_progress_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "verified_at": self.verified_at,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["RunItem"]:
        if not data:
            return None
        return cls(
            item_id=str(data.get("item_id") or ""),
            order_index=int(data.get("order_index") or 0),
            kind=str(data.get("kind") or "file_write"),
            description=str(data.get("description") or ""),
            canonical_path=data.get("canonical_path"),
            status=str(data.get("status") or "pending"),
            baseline_snapshot=VerificationBaseline.from_dict(data.get("baseline_snapshot")),
            verification_result=data.get("verification_result"),
            metadata=dict(data.get("metadata") or {}),
            attempt_count=int(data.get("attempt_count") or 0),
            last_progress_at=data.get("last_progress_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            verified_at=data.get("verified_at"),
        )


@dataclass
class RunConflictState:
    existing_run_id: Optional[str]
    existing_objective: str
    incoming_text: str
    incoming_run_items: List[Dict[str, Any]]
    requested_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "existing_run_id": self.existing_run_id,
            "existing_objective": self.existing_objective,
            "incoming_text": self.incoming_text,
            "incoming_run_items": list(self.incoming_run_items),
            "requested_at": self.requested_at,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["RunConflictState"]:
        if not data:
            return None
        return cls(
            existing_run_id=data.get("existing_run_id"),
            existing_objective=str(data.get("existing_objective") or ""),
            incoming_text=str(data.get("incoming_text") or ""),
            incoming_run_items=list(data.get("incoming_run_items") or []),
            requested_at=float(data.get("requested_at") or time.time()),
        )


@dataclass
class RunEvent:
    event_type: str
    text: str
    item_id: Optional[str] = None
    item_label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "text": self.text,
            "item_id": self.item_id,
            "item_label": self.item_label,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
        }


@dataclass
class CompletionGateResult:
    passed: bool
    reason: str
    pending_items: List[str] = field(default_factory=list)
    verification_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "pending_items": list(self.pending_items),
            "verification_result": self.verification_result,
        }


def build_run_item_started_text(item: RunItem) -> str:
    path_name = Path(item.canonical_path).name if item.canonical_path else item.description
    if item.kind == "file_verify":
        return f"开始验证 {path_name}。"
    return f"开始处理 {path_name}。"


def build_run_item_verified_text(item: RunItem) -> str:
    path_name = Path(item.canonical_path).name if item.canonical_path else item.description
    return f"已验证 {path_name}。"


def infer_target_directory(*, text: str, ingress_context: Optional[Dict[str, Any]] = None, last_explicit_target: Optional[str] = None) -> Optional[Path]:
    ingress_context = ingress_context or {}
    requested_output = ingress_context.get("requested_output") or {}
    resolved_target = ingress_context.get("resolved_target") or {}

    for candidate in (
        requested_output.get("target_directory"),
        requested_output.get("directory_path"),
        resolved_target.get("path"),
        last_explicit_target,
    ):
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        path = Path(candidate.strip())
        return path if path.suffix == "" else path.parent

    match = WINDOWS_TARGET_DIRECTORY_RE.search(text or "")
    if match:
        return Path(match.group(1))
    return None


def _build_canonical_path(base_dir: Optional[Path], filename: str) -> str:
    path = Path(filename)
    if path.is_absolute() or base_dir is None:
        return str(path)
    return str(base_dir / filename)


def _parse_expected_lines(text: str) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    for pattern, index in ((FIRST_LINE_RE, 1), (SECOND_LINE_RE, 2), (THIRD_LINE_RE, 3)):
        match = pattern.search(text or "")
        if not match:
            continue
        raw = match.group(1).strip()
        if raw == "当前日期":
            lines.append({"line_index": str(index), "kind": "current_date"})
        else:
            lines.append({"line_index": str(index), "kind": "literal", "value": raw})
    return lines


def _build_file_item(filename: str, *, base_dir: Optional[Path], text: str, position: int) -> Dict[str, Any]:
    lowered = filename.lower()
    if lowered.endswith((".html", ".htm")):
        kind = "page_generate"
    elif lowered.endswith(".py"):
        kind = "script_generate"
    else:
        kind = "file_write"

    metadata: Dict[str, Any] = {}
    if kind == "file_write":
        expected_lines = _parse_expected_lines(text)
        if expected_lines:
            metadata["expected_lines"] = expected_lines

    return {
        "position": position,
        "kind": kind,
        "description": f"创建 {filename}",
        "canonical_path": _build_canonical_path(base_dir, filename),
        "metadata": metadata,
    }


def _build_page_item(theme: str, *, base_dir: Optional[Path], position: int) -> Dict[str, Any]:
    slug = _normalize_slug(theme)
    filename = f"{slug}_lookalike.html"
    return {
        "position": position,
        "kind": "page_generate",
        "description": f"创建 {filename}",
        "canonical_path": _build_canonical_path(base_dir, filename),
        "metadata": {"theme": theme, "auto_named": True},
    }


def build_run_items_from_request(text: str, *, ingress_context: Optional[Dict[str, Any]] = None, last_explicit_target: Optional[str] = None) -> List[RunItem]:
    base_dir = infer_target_directory(text=text, ingress_context=ingress_context, last_explicit_target=last_explicit_target)
    timeline: List[Dict[str, Any]] = []

    for match in EXPLICIT_OUTPUT_FILENAME_RE.finditer(text or ""):
        candidate = match.group(1).strip().strip("\"'`")
        lowered = candidate.lower()
        if lowered.endswith((".txt", ".py", ".html", ".htm", ".md", ".json", ".js", ".css")):
            timeline.append(
                {
                    "event_type": "candidate",
                    "position": match.start(),
                    "payload": _build_file_item(candidate, base_dir=base_dir, text=text, position=match.start()),
                }
            )

    for match in LOOKALIKE_PAGE_RE.finditer(text or ""):
        theme = match.group(1).strip()
        timeline.append(
            {
                "event_type": "candidate",
                "position": match.start(),
                "payload": _build_page_item(theme, base_dir=base_dir, position=match.start()),
            }
        )

    for match in VERIFY_PREVIOUS_FILE_RE.finditer(text or ""):
        timeline.append(
            {
                "event_type": "verify_previous_file",
                "position": match.start(),
                "payload": {"position": match.start()},
            }
        )

    timeline.sort(key=lambda item: item["position"])
    run_items: List[RunItem] = []
    latest_verifiable_item: Optional[RunItem] = None

    for event in timeline:
        if event["event_type"] == "verify_previous_file":
            if latest_verifiable_item is None:
                continue
            verify_item = RunItem(
                item_id=(
                    f"item_{len(run_items) + 1:02d}_verify_"
                    f"{_normalize_slug(Path(latest_verifiable_item.canonical_path or latest_verifiable_item.description).stem)}"
                ),
                order_index=len(run_items),
                kind="file_verify",
                description=f"验证 {Path(latest_verifiable_item.canonical_path or latest_verifiable_item.description).name}",
                canonical_path=latest_verifiable_item.canonical_path,
                metadata=dict(latest_verifiable_item.metadata or {}),
            )
            verify_item.metadata["verify_source_item_id"] = latest_verifiable_item.item_id
            verify_item.metadata["position"] = event["position"]
            run_items.append(verify_item)
            continue

        candidate = event["payload"]
        canonical_path = str(candidate["canonical_path"])
        duplicate = next(
            (
                item
                for item in run_items
                if (item.canonical_path or "").lower() == canonical_path.lower() and item.kind == candidate["kind"]
            ),
            None,
        )
        if duplicate is not None:
            latest_verifiable_item = duplicate
            continue

        item = RunItem(
            item_id=f"item_{len(run_items) + 1:02d}_{_normalize_slug(Path(canonical_path).name or candidate['description'])}",
            order_index=len(run_items),
            kind=str(candidate["kind"]),
            description=str(candidate["description"]),
            canonical_path=canonical_path,
            metadata=dict(candidate.get("metadata") or {}),
        )
        item.metadata["position"] = event["position"]
        run_items.append(item)
        latest_verifiable_item = item

    run_items.sort(key=lambda item: item.metadata.get("position", item.order_index))
    for index, item in enumerate(run_items):
        item.order_index = index
        item.metadata.pop("position", None)
    return run_items


def build_output_obligations(run_items: List[RunItem]) -> List[Dict[str, Any]]:
    obligations: List[Dict[str, Any]] = []
    seen_paths = set()
    for item in run_items:
        if not item.canonical_path:
            continue
        path_key = item.canonical_path.lower()
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        obligations.append(
            {
                "name": Path(item.canonical_path).name,
                "path": item.canonical_path,
                "status": item.status,
                "item_id": item.item_id,
                "kind": item.kind,
            }
        )
    return obligations


def current_date_string() -> str:
    return date.today().isoformat()


def _expected_lines_match(path: Path, expected_lines: List[Dict[str, str]]) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False
    for spec in expected_lines:
        index = int(spec.get("line_index") or 0) - 1
        if index < 0 or index >= len(lines):
            return False
        actual = lines[index].strip()
        if spec.get("kind") == "current_date":
            if actual != current_date_string():
                return False
        else:
            if actual != str(spec.get("value") or "").strip():
                return False
    return True


def path_changed_from_baseline(path: Path, baseline: Optional[VerificationBaseline]) -> bool:
    if baseline is None:
        return path.exists()
    if not path.exists():
        return False
    if not baseline.exists:
        return True
    stat = path.stat()
    current_mtime_ns = getattr(stat, "st_mtime_ns", None)
    current_hash = _path_content_hash(path)
    return any(
        (
            current_mtime_ns != baseline.mtime_ns,
            stat.st_size != baseline.size,
            current_hash is not None and baseline.content_hash is not None and current_hash != baseline.content_hash,
        )
    )


def verify_run_item(item: RunItem) -> Dict[str, Any]:
    path_value = item.canonical_path
    if not path_value:
        return {
            "passed": False,
            "reason": "missing_canonical_path",
            "evidence": {},
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "passed": False,
            "reason": "run_item_missing",
            "evidence": {"path": str(path)},
        }

    if item.kind in {"file_write", "script_generate", "page_generate"} and not path_changed_from_baseline(path, item.baseline_snapshot):
        return {
            "passed": False,
            "reason": "run_item_not_updated",
            "evidence": {"path": str(path)},
        }

    expected_lines = list((item.metadata or {}).get("expected_lines") or [])
    if expected_lines and not _expected_lines_match(path, expected_lines):
        return {
            "passed": False,
            "reason": "run_item_content_mismatch",
            "evidence": {"path": str(path)},
        }

    if item.kind == "page_generate":
        if path.suffix.lower() not in {".html", ".htm"}:
            return {
                "passed": False,
                "reason": "run_item_invalid_extension",
                "evidence": {"path": str(path)},
            }
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return {
                "passed": False,
                "reason": "run_item_unreadable",
                "evidence": {"path": str(path)},
            }
        lowered = content.lower()
        if "<html" not in lowered and "<!doctype html" not in lowered:
            return {
                "passed": False,
                "reason": "run_item_semantic_invalid",
                "evidence": {"path": str(path)},
            }

    if item.kind == "file_verify" and expected_lines:
        if not _expected_lines_match(path, expected_lines):
            return {
                "passed": False,
                "reason": "run_item_verify_failed",
                "evidence": {"path": str(path)},
            }

    return {
        "passed": True,
        "reason": "run_item_verified",
        "evidence": {"path": str(path)},
    }
