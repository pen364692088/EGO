from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_report_path(process_kind: str) -> Path:
    root = _repo_root()
    return root / "EgoCore" / "artifacts" / "proto_self_v2" / f"LIVE_{process_kind.upper()}_PROCESS_VERSION.json"


def _run_git(repo_root: Path, args: Iterable[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def build_live_process_version_record(
    *,
    process_kind: str,
    argv: Optional[Iterable[str]] = None,
    cwd: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else _repo_root()
    status_porcelain = _run_git(resolved_repo_root, ["status", "--short"])
    return {
        "schema_version": "egocore.live_process_version.v1",
        "observed_at": datetime.now().isoformat(),
        "process_kind": process_kind,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "python_executable": sys.executable,
        "argv": list(argv if argv is not None else sys.argv),
        "cwd": cwd or os.getcwd(),
        "repo_root": str(resolved_repo_root),
        "git_commit_sha": _run_git(resolved_repo_root, ["rev-parse", "HEAD"]),
        "git_commit_short": _run_git(resolved_repo_root, ["rev-parse", "--short", "HEAD"]),
        "git_branch": _run_git(resolved_repo_root, ["branch", "--show-current"]),
        "git_dirty": bool(status_porcelain),
    }


def write_live_process_version_report(
    *,
    process_kind: str,
    argv: Optional[Iterable[str]] = None,
    cwd: Optional[str] = None,
    repo_root: Optional[Path] = None,
    report_path: Optional[Path] = None,
) -> Path:
    record = build_live_process_version_record(
        process_kind=process_kind,
        argv=argv,
        cwd=cwd,
        repo_root=repo_root,
    )
    path = Path(report_path) if report_path is not None else _default_report_path(process_kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
