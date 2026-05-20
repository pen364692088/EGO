#!/usr/bin/env python3
"""Cross-project Codex task-board autopilot helpers."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT_PATH = ROOT / ".codex" / "project_contract.yaml"
DEFAULT_BASELINE_PATH = ROOT / ".codex" / "autopilot" / "dirty_baseline.json"
DEFAULT_REPORT_DIR = ROOT / ".codex" / "autopilot" / "runs"
DEFAULT_REVIEW_SCHEMA_PATH = SCRIPT_DIR / "codex_autopilot_closeout_review_schema.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import github_project_task  # noqa: E402

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised only when PyYAML is absent.
    yaml = None


class AutopilotError(Exception):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class ProjectContract:
    path: Path
    name: str
    repo: str
    owner: str
    project_number: str
    status_field: str
    default_branch: str
    verify_profiles: dict[str, Any] = field(default_factory=dict)
    protected_paths: list[str] = field(default_factory=list)
    allowed_mutation_paths: list[str] = field(default_factory=list)
    commit_policy: dict[str, Any] = field(default_factory=dict)
    task_classification: dict[str, Any] = field(default_factory=dict)
    observation_classes: dict[str, Any] = field(default_factory=dict)
    auto_closeout: dict[str, Any] = field(default_factory=dict)
    auto_execute: dict[str, Any] = field(default_factory=dict)
    auto_pause: dict[str, Any] = field(default_factory=dict)

    def github_config(self, *, dry_run: bool = False) -> github_project_task.Config:
        return github_project_task.Config(
            repo=self.repo,
            owner=self.owner,
            project_number=self.project_number,
            status_field=self.status_field,
            dry_run=dry_run,
        )


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> CommandResult:
        merged_env = None
        if env:
            merged_env = os.environ.copy()
            merged_env.update({str(key): str(value) for key, value in env.items()})
        try:
            completed = subprocess.run(
                args,
                cwd=ROOT,
                env=merged_env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return CommandResult(args=args, returncode=127, stdout="", stderr=str(exc))
        return CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


@dataclass(frozen=True)
class DirtyEntry:
    status: str
    path: str
    line: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "path": self.path,
            "line": self.line,
            "signature": self.signature,
        }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _require_mapping(payload: Any, *, code: str, message: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AutopilotError(code, message)
    return payload


def load_contract(path: Path) -> ProjectContract:
    if not path.exists():
        raise AutopilotError("missing_project_contract", f"Project contract not found: {path}")
    if yaml is None:
        raise AutopilotError("yaml_unavailable", "PyYAML is required to read project_contract.yaml")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload = _require_mapping(raw, code="invalid_project_contract", message="Project contract must be a YAML object")
    project = _require_mapping(
        payload.get("project"),
        code="missing_project_section",
        message="Project contract is missing project section",
    )
    board = _require_mapping(
        payload.get("github_project"),
        code="missing_github_project_section",
        message="Project contract is missing github_project section",
    )

    missing = [
        name
        for name, value in {
            "project.repo": project.get("repo"),
            "github_project.owner": board.get("owner"),
            "github_project.number": board.get("number"),
            "github_project.status_field": board.get("status_field"),
        }.items()
        if value in (None, "")
    ]
    if missing:
        raise AutopilotError("missing_project_contract_fields", "Project contract is missing required fields", fields=missing)

    return ProjectContract(
        path=path,
        name=str(project.get("name") or Path.cwd().name),
        repo=str(project["repo"]),
        owner=str(board["owner"]),
        project_number=str(board["number"]),
        status_field=str(board["status_field"]),
        default_branch=str(project.get("default_branch") or "main"),
        verify_profiles=_require_mapping(payload.get("verify_profiles") or {}, code="invalid_verify_profiles", message="verify_profiles must be an object"),
        protected_paths=_as_list(payload.get("protected_paths")),
        allowed_mutation_paths=_as_list(payload.get("allowed_mutation_paths")),
        commit_policy=_require_mapping(payload.get("commit_policy") or {}, code="invalid_commit_policy", message="commit_policy must be an object"),
        task_classification=_require_mapping(
            payload.get("task_classification") or {},
            code="invalid_task_classification",
            message="task_classification must be an object",
        ),
        observation_classes=_require_mapping(
            payload.get("observation_classes") or {},
            code="invalid_observation_classes",
            message="observation_classes must be an object",
        ),
        auto_closeout=_require_mapping(
            payload.get("auto_closeout") or {},
            code="invalid_auto_closeout",
            message="auto_closeout must be an object",
        ),
        auto_execute=_require_mapping(
            payload.get("auto_execute") or {},
            code="invalid_auto_execute",
            message="auto_execute must be an object",
        ),
        auto_pause=_require_mapping(
            payload.get("auto_pause") or {},
            code="invalid_auto_pause",
            message="auto_pause must be an object",
        ),
    )


def issue_view_full(client: github_project_task.GhClient, cfg: github_project_task.Config, issue: str) -> dict[str, Any]:
    return github_project_task.gh_json(
        client,
        [
            "issue",
            "view",
            issue,
            "--repo",
            cfg.repo,
            "--json",
            "number,title,state,url,body",
        ],
    )


def _casefold(value: Any) -> str:
    return str(value or "").casefold()


def _starts_with_any(value: str, prefixes: list[str]) -> bool:
    return any(value.startswith(prefix.casefold()) for prefix in prefixes)


def _contains_any(value: str, needles: list[str]) -> bool:
    return any(needle.casefold() in value for needle in needles)


def _path_from_status_line(line: str) -> tuple[str, str]:
    status = line[:2]
    path = line[3:] if len(line) > 3 else line
    path = path.strip().strip('"')
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip().strip('"')
    return status, path


def _path_allowed(path: str, prefixes: list[str]) -> bool:
    cleaned = path.strip().strip('"').rstrip("/")
    normalized = cleaned.replace("\\", "/")
    allowed = [prefix.rstrip("/").replace("\\", "/") for prefix in prefixes]
    return any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in allowed)


def _entry_signature(path: str, status: str) -> str:
    fs_path = ROOT / path
    try:
        stat = fs_path.lstat()
    except FileNotFoundError:
        return f"{status}:missing"
    if fs_path.is_symlink():
        return f"{status}:symlink:{fs_path.readlink()}:{stat.st_mtime_ns}"
    if fs_path.is_file():
        return f"{status}:file:{stat.st_size}:{stat.st_mtime_ns}"
    if fs_path.is_dir():
        return f"{status}:dir:{stat.st_mtime_ns}"
    return f"{status}:missing"


def dirty_entries(runner: CommandRunner) -> list[DirtyEntry]:
    result = runner.run(["git", "status", "--short", "--untracked-files=all"])
    if result.returncode != 0:
        raise AutopilotError(
            "git_status_failed",
            "Unable to inspect git status",
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    entries = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status, path = _path_from_status_line(line)
        entries.append(DirtyEntry(status=status, path=path, line=line, signature=_entry_signature(path, status)))
    return entries


def write_baseline(path: Path, entries: list[DirtyEntry], contract: ProjectContract) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "created_at_unix": int(time.time()),
        "repo_root": str(ROOT),
        "contract_path": str(contract.path),
        "entry_count": len(entries),
        "entries": [entry.to_dict() for entry in entries],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def read_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AutopilotError("missing_dirty_baseline", f"Dirty baseline not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AutopilotError("invalid_dirty_baseline", f"Dirty baseline is not valid JSON: {path}") from exc
    if not isinstance(payload.get("entries"), list):
        raise AutopilotError("invalid_dirty_baseline", "Dirty baseline has no entries array", path=str(path))
    return payload


def diff_scope_summary(contract: ProjectContract, baseline_path: Path, runner: CommandRunner) -> dict[str, Any]:
    baseline = read_baseline(baseline_path)
    baseline_by_path = {
        str(entry.get("path")): str(entry.get("signature"))
        for entry in baseline.get("entries", [])
        if isinstance(entry, dict)
    }
    current = dirty_entries(runner)
    unchanged_preexisting = []
    changed_preexisting_scoped = []
    changed_preexisting_unsafe = []
    new_scoped = []
    new_unsafe = []
    allowed = contract.allowed_mutation_paths

    for entry in current:
        previous_signature = baseline_by_path.get(entry.path)
        allowed_path = _path_allowed(entry.path, allowed)
        if previous_signature == entry.signature:
            unchanged_preexisting.append(entry.to_dict())
        elif previous_signature is None and allowed_path:
            new_scoped.append(entry.to_dict())
        elif previous_signature is None:
            new_unsafe.append(entry.to_dict())
        elif allowed_path:
            changed_preexisting_scoped.append(entry.to_dict())
        else:
            changed_preexisting_unsafe.append(entry.to_dict())

    return {
        "status": "ok",
        "baseline_path": str(baseline_path),
        "baseline_entry_count": int(baseline.get("entry_count") or len(baseline_by_path)),
        "current_entry_count": len(current),
        "counts": {
            "unchanged_preexisting": len(unchanged_preexisting),
            "changed_preexisting_scoped": len(changed_preexisting_scoped),
            "changed_preexisting_unsafe": len(changed_preexisting_unsafe),
            "new_scoped": len(new_scoped),
            "new_unsafe": len(new_unsafe),
        },
        "unsafe": {
            "count": len(changed_preexisting_unsafe) + len(new_unsafe),
            "changed_preexisting_sample": changed_preexisting_unsafe[:20],
            "new_sample": new_unsafe[:20],
        },
        "scoped": {
            "count": len(changed_preexisting_scoped) + len(new_scoped),
            "changed_preexisting_sample": changed_preexisting_scoped[:20],
            "new_sample": new_scoped[:20],
        },
    }


def classify_issue(contract: ProjectContract, issue: dict[str, Any], item: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = contract.task_classification
    title = str(issue.get("title") or ((item or {}).get("title")) or "")
    body = str(issue.get("body") or (item or {}).get("body") or "")
    content = item.get("content") if isinstance(item, dict) else None
    if isinstance(content, dict) and not body:
        body = str(content.get("body") or "")

    status = str((item or {}).get("status") or "")
    content_state = content.get("state") if isinstance(content, dict) else None
    state = str(issue.get("state") or content_state or "")
    haystack = f"{title}\n{body}".casefold()
    title_cf = title.casefold()

    if state.upper() == "CLOSED" or status == "Done":
        return {"class": "done", "reason": "issue_closed_or_project_done", "autopilot_allowed": False}

    if _starts_with_any(title_cf, _as_list(rules.get("parked_title_prefixes"))):
        return {"class": "parked", "reason": "parked_title_prefix", "autopilot_allowed": False}

    if _starts_with_any(title_cf, _as_list(rules.get("supporting_title_prefixes"))):
        return {"class": "supporting", "reason": "supporting_title_prefix", "autopilot_allowed": False}

    if _contains_any(title_cf, _as_list(rules.get("aggregate_title_contains"))):
        return {"class": "aggregate", "reason": "aggregate_or_backlog_marker", "autopilot_allowed": False}

    if _contains_any(title_cf, _as_list(rules.get("human_required_title_contains"))):
        return {"class": "human_required", "reason": "human_observation_marker", "autopilot_allowed": False}

    observation_match = re.search(
        r"observation[_ -]?class\s*[:：]\s*`?([A-Za-z0-9_-]+)`?",
        haystack,
        flags=re.IGNORECASE,
    )
    if observation_match and observation_match.group(1).casefold() == "human_required":
        return {"class": "human_required", "reason": "human_observation_class", "autopilot_allowed": False}

    if _contains_any(title_cf, _as_list(rules.get("high_impact_title_contains"))):
        return {"class": "high_impact", "reason": "high_impact_marker", "autopilot_allowed": False}

    ready_statuses = set(_as_list(rules.get("ready_project_statuses")) or ["In Progress", "Todo"])
    if status and status not in ready_statuses:
        return {"class": "blocked", "reason": "project_status_not_ready", "autopilot_allowed": False, "project_status": status}

    if _starts_with_any(title_cf, _as_list(rules.get("epic_title_prefixes"))):
        return {"class": "epic", "reason": "epic_title_prefix", "autopilot_allowed": False}

    ready_prefix = _starts_with_any(title_cf, _as_list(rules.get("ready_title_prefixes")))
    research_prefix = _starts_with_any(title_cf, _as_list(rules.get("research_title_prefixes")))
    markers = [marker.casefold() for marker in _as_list(rules.get("ready_body_markers"))]
    marker_hits = [marker for marker in markers if marker in haystack]

    if research_prefix and marker_hits:
        return {
            "class": "research",
            "reason": "research_prefix_and_acceptance_markers",
            "autopilot_allowed": True,
            "marker_hits": marker_hits,
        }

    if research_prefix:
        return {"class": "blocked", "reason": "research_prefix_without_acceptance_markers", "autopilot_allowed": False}

    if ready_prefix and marker_hits:
        return {
            "class": "ready",
            "reason": "ready_prefix_and_acceptance_markers",
            "autopilot_allowed": True,
            "marker_hits": marker_hits,
        }

    if ready_prefix:
        return {"class": "blocked", "reason": "ready_prefix_without_acceptance_markers", "autopilot_allowed": False}

    return {"class": "unknown", "reason": "no_matching_classification_rule", "autopilot_allowed": False}


def item_issue(item: dict[str, Any]) -> dict[str, Any]:
    content = item.get("content")
    if isinstance(content, dict):
        return content
    return {"title": item.get("title"), "url": item.get("content.url")}


def load_items(client: github_project_task.GhClient, cfg: github_project_task.Config) -> list[dict[str, Any]]:
    return github_project_task.project_items(client, cfg)


def build_report(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    cfg = contract.github_config()
    items = load_items(client, cfg)
    issue_entries = []
    counts: dict[str, int] = {}
    for item in items:
        issue = item_issue(item)
        if issue.get("type") and issue.get("type") != "Issue":
            continue
        classification = classify_issue(contract, issue, item)
        cls = classification["class"]
        counts[cls] = counts.get(cls, 0) + 1
        issue_entries.append(
            {
                "number": issue.get("number"),
                "title": issue.get("title") or item.get("title"),
                "state": issue.get("state"),
                "url": issue.get("url"),
                "project_status": item.get("status"),
                "classification": classification,
            }
        )

    return {
        "status": "ok",
        "project": {
            "name": contract.name,
            "repo": contract.repo,
            "owner": contract.owner,
            "project_number": contract.project_number,
        },
        "counts": counts,
        "issues": issue_entries,
    }


def select_next(report: dict[str, Any]) -> dict[str, Any] | None:
    status_rank = {"In Progress": 0, "Todo": 1}
    ready = [
        issue
        for issue in report.get("issues", [])
        if issue.get("classification", {}).get("autopilot_allowed") is True
    ]
    ready.sort(key=lambda item: (status_rank.get(str(item.get("project_status")), 99), int(item.get("number") or 999999)))
    return ready[0] if ready else None


def command_doctor(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    result = github_project_task.command_doctor(client, contract.github_config(), argparse.Namespace())
    return {
        "status": "ok",
        "contract": contract_summary(contract),
        "github": result,
        "verify_profiles": sorted(contract.verify_profiles),
        "observation_classes": sorted(contract.observation_classes),
    }


def command_report(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    return build_report(client, contract)


def command_plan_next(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    report = build_report(client, contract)
    selected = select_next(report)
    if not selected:
        return {
            "status": "stopped",
            "stop_reason": "no_ready_issue",
            "counts": report["counts"],
            "next_issue": None,
        }
    return {
        "status": "ok",
        "next_issue": selected,
        "selection_reason": selected["classification"]["reason"],
    }


def command_classify_issue(client: github_project_task.GhClient, contract: ProjectContract, issue_ref: str) -> dict[str, Any]:
    cfg = contract.github_config()
    issue = issue_view_full(client, cfg, issue_ref)
    item = github_project_task.find_project_item(load_items(client, cfg), issue)
    classification = classify_issue(contract, issue, item)
    return {
        "status": "ok",
        "issue": issue,
        "project_item": {
            "id": item.get("id"),
            "status": item.get("status"),
            "title": item.get("title"),
        }
        if item
        else None,
        "classification": classification,
    }


def contract_summary(contract: ProjectContract) -> dict[str, Any]:
    return {
        "path": str(contract.path),
        "name": contract.name,
        "repo": contract.repo,
        "project": {
            "owner": contract.owner,
            "number": contract.project_number,
            "status_field": contract.status_field,
        },
        "default_branch": contract.default_branch,
        "protected_paths": contract.protected_paths,
        "allowed_mutation_paths": contract.allowed_mutation_paths,
        "commit_policy": contract.commit_policy,
        "auto_closeout": contract.auto_closeout,
        "auto_execute": contract.auto_execute,
        "auto_pause": contract.auto_pause,
    }


def worktree_dirty_summary(contract: ProjectContract, runner: CommandRunner) -> dict[str, Any]:
    entries = dirty_entries(runner)
    unsafe = [entry.line for entry in entries if not _path_allowed(entry.path, contract.allowed_mutation_paths)]

    return {
        "total_dirty": len(entries),
        "unsafe_dirty": len(unsafe),
        "unsafe_sample": unsafe[:20],
    }


def dirty_gate(contract: ProjectContract, runner: CommandRunner, baseline_path: Path) -> dict[str, Any]:
    if baseline_path.exists():
        summary = diff_scope_summary(contract, baseline_path, runner)
        unsafe_count = int(summary["unsafe"]["count"])
        return {
            "status": "ok" if unsafe_count == 0 else "blocked",
            "mode": "baseline_diff",
            "summary": summary,
            "stop_reason": None if unsafe_count == 0 else "dirty_scope_unsafe",
        }
    dirty = worktree_dirty_summary(contract, runner)
    return {
        "status": "ok" if dirty["unsafe_dirty"] == 0 else "blocked",
        "mode": "raw_dirty",
        "summary": dirty,
        "stop_reason": None if dirty["unsafe_dirty"] == 0 else "dirty_worktree_unsafe",
    }


def _issue_text(issue: dict[str, Any]) -> str:
    return f"{issue.get('title') or ''}\n{issue.get('body') or ''}"


def issue_observation_class(contract: ProjectContract, issue: dict[str, Any]) -> str:
    text = _issue_text(issue)
    patterns = [
        r"observation[_ -]?class\s*[:：]\s*`?([A-Za-z0-9_-]+)`?",
        r"evidence[_ -]?class\s*[:：]\s*`?([A-Za-z0-9_-]+)`?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return str(contract.auto_closeout.get("default_observation_class") or "deterministic_local")


def issue_hard_stop_reasons(contract: ProjectContract, issue: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    title = str(issue.get("title") or "").casefold()
    body = str(issue.get("body") or "").casefold()
    for marker in _as_list(contract.auto_closeout.get("hard_stop_title_contains")):
        if marker.casefold() in title:
            reasons.append({"reason": "hard_stop_title_marker", "marker": marker})
    for marker in _as_list(contract.auto_closeout.get("hard_stop_body_markers")):
        if marker.casefold() in body:
            reasons.append({"reason": "hard_stop_body_marker", "marker": marker})
    return reasons


def command_verify_profile(contract: ProjectContract, profile: str, *, runner: CommandRunner) -> dict[str, Any]:
    profile_cfg = contract.verify_profiles.get(profile)
    if not isinstance(profile_cfg, dict):
        raise AutopilotError("missing_verify_profile", f"Verify profile not found: {profile}", profile=profile)
    commands = profile_cfg.get("commands")
    if not isinstance(commands, list) or not commands:
        raise AutopilotError("invalid_verify_profile", f"Verify profile has no commands: {profile}", profile=profile)

    results = []
    all_passed = True
    started = time.monotonic()
    for index, spec in enumerate(commands):
        if not isinstance(spec, dict):
            raise AutopilotError("invalid_verify_command", "Verify command spec must be an object", profile=profile, index=index)
        command = spec.get("command")
        if not isinstance(command, list) or not command:
            raise AutopilotError("invalid_verify_command", "Verify command must be a non-empty list", profile=profile, index=index)
        label = str(spec.get("label") or f"command_{index + 1}")
        env = spec.get("env") if isinstance(spec.get("env"), dict) else None
        result = runner.run([str(part) for part in command], env={str(k): str(v) for k, v in (env or {}).items()} if env else None)
        passed = result.returncode == 0
        all_passed = all_passed and passed
        results.append(
            {
                "label": label,
                "command": [str(part) for part in command],
                "returncode": result.returncode,
                "passed": passed,
                "stdout_preview": result.stdout[-2000:],
                "stderr_preview": result.stderr[-2000:],
            }
        )

    return {
        "status": "ok" if all_passed else "failed",
        "profile": profile,
        "passed": all_passed,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "results": results,
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def llm_reviewer(contract: ProjectContract, packet: dict[str, Any], *, runner: CommandRunner) -> dict[str, Any]:
    prompt = (
        "You are a conservative closeout reviewer for a Codex GitHub Project autopilot.\n"
        "Return JSON only. Verdict must be closeout_allowed or closeout_blocked.\n"
        "You may only make the decision stricter; never override hard-stop gates.\n\n"
        f"Packet:\n{json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2)}"
    )
    result = runner.run(
        [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(DEFAULT_REVIEW_SCHEMA_PATH),
            prompt,
        ]
    )
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "verdict": "closeout_blocked",
            "reason": "llm_reviewer_unavailable",
            "returncode": result.returncode,
            "stderr_preview": result.stderr[-1000:],
            "stdout_preview": result.stdout[-1000:],
        }
    parsed = _extract_json_object(result.stdout)
    if not parsed:
        return {
            "status": "unavailable",
            "verdict": "closeout_blocked",
            "reason": "llm_reviewer_invalid_json",
            "stdout_preview": result.stdout[-1000:],
        }
    verdict = str(parsed.get("verdict") or "")
    if verdict not in {"closeout_allowed", "closeout_blocked"}:
        parsed["verdict"] = "closeout_blocked"
        parsed["reason"] = parsed.get("reason") or "llm_reviewer_invalid_verdict"
    parsed.setdefault("status", "ok")
    return parsed


def closeout_comment_draft(packet: dict[str, Any]) -> str:
    issue = packet.get("issue") or {}
    verify = packet.get("verify") or {}
    claim = packet.get("claim_ceiling") or "local workflow candidate pass"
    lines = [
        f"Closeout for #{issue.get('number')}: {issue.get('title')}",
        "",
        "Autopilot L3 closeout eligibility passed.",
        f"- observation_class: `{packet.get('observation_class')}`",
        f"- verify_profile: `{verify.get('profile')}`",
        f"- verify_status: `{verify.get('status')}`",
        f"- dirty_gate: `{(packet.get('dirty_gate') or {}).get('status')}`",
    ]
    reviewer = packet.get("llm_reviewer")
    if reviewer:
        lines.append(f"- llm_reviewer_verdict: `{reviewer.get('verdict')}`")
    lines.extend(
        [
            "",
            f"Claim: `{claim}`.",
            "",
            "Not claimed: full unattended autonomous development, stable productivity gain, product runtime efficacy, live autonomy, durable memory efficacy, or consciousness.",
        ]
    )
    return "\n".join(lines)


def closeout_packet(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    classified = command_classify_issue(client, contract, issue_ref)
    issue = classified["issue"]
    classification = classified["classification"]
    observation_class = issue_observation_class(contract, issue)
    claim_ceiling = str(contract.auto_closeout.get("claim_ceiling") or "Codex autopilot local closeout candidate pass")
    blocked_reasons: list[dict[str, Any]] = []

    hard_stop_classes = set(_as_list(contract.auto_closeout.get("hard_stop_classes")))
    if classification.get("class") in hard_stop_classes or classification.get("autopilot_allowed") is not True:
        blocked_reasons.append(
            {
                "reason": "issue_class_not_auto_closeable",
                "class": classification.get("class"),
                "classification_reason": classification.get("reason"),
            }
        )
    project_item = classified.get("project_item") or {}
    project_status = project_item.get("status")
    if project_status != "In Progress":
        blocked_reasons.append(
            {
                "reason": "project_status_not_in_progress_for_closeout",
                "project_status": project_status,
            }
        )
    blocked_reasons.extend(issue_hard_stop_reasons(contract, issue))

    dirty = dirty_gate(contract, runner, baseline_path)
    if dirty.get("status") != "ok":
        blocked_reasons.append({"reason": dirty.get("stop_reason") or "dirty_gate_blocked", "dirty_gate": dirty})

    observation_cfg = contract.observation_classes.get(observation_class)
    if not isinstance(observation_cfg, dict):
        blocked_reasons.append({"reason": "unknown_observation_class", "observation_class": observation_class})
        observation_cfg = {}

    verify = None
    reviewer = None
    profile_map = contract.auto_closeout.get("observation_verify_profiles")
    profile = None
    if isinstance(profile_map, dict):
        profile = profile_map.get(observation_class)
    profile = str(profile or "autopilot_full")

    if not blocked_reasons:
        try:
            verify = command_verify_profile(contract, profile, runner=runner)
        except AutopilotError as exc:
            verify = {"status": "error", "error": exc.code, "message": exc.message, **exc.details}
            blocked_reasons.append({"reason": "verify_profile_error", "error": exc.code})
        if verify and not verify.get("passed"):
            blocked_reasons.append({"reason": "verify_profile_failed", "profile": profile})

    llm_classes = set(_as_list(contract.auto_closeout.get("llm_review_observation_classes")))
    needs_llm_review = observation_class in llm_classes
    closeout_allowed = bool(observation_cfg.get("closeout_allowed"))

    packet: dict[str, Any] = {
        "status": "blocked",
        "issue": {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "url": issue.get("url"),
        },
        "project_item": classified.get("project_item"),
        "classification": classification,
        "observation_class": observation_class,
        "claim_ceiling": claim_ceiling,
        "dirty_gate": dirty,
        "verify": verify,
        "blocked_reasons": blocked_reasons,
    }

    if needs_llm_review and not blocked_reasons:
        reviewer_packet = json.loads(json.dumps(packet, ensure_ascii=False))
        reviewer_packet["status"] = "pending_llm_review"
        reviewer_packet["review_note"] = (
            "This packet is awaiting the LLM reviewer verdict. Do not block solely "
            "because the GitHub issue is still open, the Project item is still In Progress, "
            "or the pre-review packet status is not already eligible. Only block for missing "
            "evidence, failed verification, hard-stop markers, unsafe dirty scope, or overclaim."
        )
        reviewer = llm_reviewer(contract, reviewer_packet, runner=runner)
        packet["llm_reviewer"] = reviewer
        if reviewer.get("verdict") != "closeout_allowed":
            blocked_reasons.append({"reason": reviewer.get("reason") or "llm_reviewer_blocked"})
    elif not closeout_allowed and not needs_llm_review:
        blocked_reasons.append({"reason": "observation_class_not_closeout_allowed", "observation_class": observation_class})

    eligible = not blocked_reasons and (closeout_allowed or (needs_llm_review and reviewer and reviewer.get("verdict") == "closeout_allowed"))
    packet["blocked_reasons"] = blocked_reasons
    packet["eligible"] = eligible
    packet["status"] = "eligible" if eligible else "blocked"
    packet["closeout_comment"] = closeout_comment_draft(packet) if eligible else None
    return packet


def _auto_execute_config(contract: ProjectContract) -> dict[str, Any]:
    cfg = dict(contract.auto_execute)
    cfg.setdefault("claim_ceiling", "Codex autopilot ready-issue executor gate local candidate pass")
    cfg.setdefault("require_project_status", "In Progress")
    cfg.setdefault("allowed_observation_classes", ["deterministic_local"])
    cfg.setdefault(
        "blocked_observation_classes",
        [
            "scripted_with_llm_judge",
            "human_required",
            "aggregate",
            "parked",
            "supporting",
            "unknown",
            "high_impact",
        ],
    )
    cfg.setdefault(
        "hard_stop_classes",
        _as_list(contract.auto_closeout.get("hard_stop_classes"))
        or ["human_required", "aggregate", "parked", "supporting", "unknown", "high_impact", "blocked"],
    )
    cfg.setdefault(
        "hard_stop_title_contains",
        _as_list(contract.auto_closeout.get("hard_stop_title_contains")),
    )
    cfg.setdefault(
        "hard_stop_body_markers",
        _as_list(contract.auto_closeout.get("hard_stop_body_markers")),
    )
    cfg.setdefault("observation_verify_profiles", contract.auto_closeout.get("observation_verify_profiles") or {})
    return cfg


def issue_auto_execute_hard_stop_reasons(
    contract: ProjectContract,
    issue: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons = list(issue_hard_stop_reasons(contract, issue))
    seen = {(reason.get("reason"), reason.get("marker")) for reason in reasons}
    title = str(issue.get("title") or "").casefold()
    body = str(issue.get("body") or "").casefold()
    for marker in _as_list(cfg.get("hard_stop_title_contains")):
        key = ("hard_stop_title_marker", marker)
        if marker.casefold() in title and key not in seen:
            reasons.append({"reason": "hard_stop_title_marker", "marker": marker})
            seen.add(key)
    for marker in _as_list(cfg.get("hard_stop_body_markers")):
        key = ("hard_stop_body_marker", marker)
        if marker.casefold() in body and key not in seen:
            reasons.append({"reason": "hard_stop_body_marker", "marker": marker})
            seen.add(key)
    return reasons


def executor_plan_steps(issue_ref: str, verify_profile: str | None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"step": "claim_issue_in_progress", "issue": issue_ref},
        {"step": "load_issue_contract", "source": "GitHub issue body + .codex/project_contract.yaml"},
        {"step": "confirm_dirty_scope", "gate": "dirty_gate"},
        {"step": "implement_scoped_patch", "note": "requires a Codex implementation rollout; not executed by executor-check"},
    ]
    if verify_profile:
        steps.append({"step": "run_required_verify_profile", "profile": verify_profile})
    steps.extend(
        [
            {"step": "run_closeout_check", "command": f"closeout-check --issue {issue_ref}"},
            {"step": "closeout_if_eligible", "gate": "L3 closeout oracle"},
        ]
    )
    return steps


def executor_packet(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    classified = command_classify_issue(client, contract, issue_ref)
    issue = classified["issue"]
    classification = classified["classification"]
    observation_class = issue_observation_class(contract, issue)
    cfg = _auto_execute_config(contract)
    blocked_reasons: list[dict[str, Any]] = []

    hard_stop_classes = set(_as_list(cfg.get("hard_stop_classes")))
    if classification.get("class") in hard_stop_classes or classification.get("autopilot_allowed") is not True:
        blocked_reasons.append(
            {
                "reason": "issue_class_not_auto_executable",
                "class": classification.get("class"),
                "classification_reason": classification.get("reason"),
            }
        )

    project_item = classified.get("project_item") or {}
    required_status = str(cfg.get("require_project_status") or "In Progress")
    project_status = project_item.get("status")
    if project_status != required_status:
        blocked_reasons.append(
            {
                "reason": "project_status_not_in_progress_for_l5_execute",
                "project_status": project_status,
                "required_status": required_status,
            }
        )

    blocked_observation_classes = set(_as_list(cfg.get("blocked_observation_classes")))
    allowed_observation_classes = set(_as_list(cfg.get("allowed_observation_classes")))
    if observation_class in blocked_observation_classes:
        blocked_reasons.append(
            {"reason": "observation_class_not_auto_executable", "observation_class": observation_class}
        )
    elif allowed_observation_classes and observation_class not in allowed_observation_classes:
        blocked_reasons.append(
            {
                "reason": "observation_class_not_l5_allowed",
                "observation_class": observation_class,
                "allowed_observation_classes": sorted(allowed_observation_classes),
            }
        )

    blocked_reasons.extend(issue_auto_execute_hard_stop_reasons(contract, issue, cfg))

    dirty = dirty_gate(contract, runner, baseline_path)
    if dirty.get("status") != "ok":
        blocked_reasons.append({"reason": dirty.get("stop_reason") or "dirty_gate_blocked", "dirty_gate": dirty})

    profile_map = cfg.get("observation_verify_profiles")
    verify_profile = None
    if isinstance(profile_map, dict):
        verify_profile = profile_map.get(observation_class)
    verify_profile = str(verify_profile or "")
    if not verify_profile:
        blocked_reasons.append({"reason": "missing_l5_verify_profile", "observation_class": observation_class})
    elif verify_profile not in contract.verify_profiles:
        blocked_reasons.append(
            {
                "reason": "unknown_l5_verify_profile",
                "observation_class": observation_class,
                "verify_profile": verify_profile,
            }
        )

    eligible = not blocked_reasons
    return {
        "status": "eligible" if eligible else "blocked",
        "eligible": eligible,
        "issue": {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "url": issue.get("url"),
        },
        "project_item": classified.get("project_item"),
        "classification": classification,
        "observation_class": observation_class,
        "verify_profile": verify_profile or None,
        "claim_ceiling": str(cfg.get("claim_ceiling")),
        "dirty_gate": dirty,
        "blocked_reasons": blocked_reasons,
        "execution_plan": executor_plan_steps(issue_ref, verify_profile or None) if eligible else [],
        "note": (
            "L5 executor gate is read-only in v1: it authorizes a bounded Codex rollout plan, "
            "not direct unattended code mutation."
        ),
    }


def write_run_report(payload: dict[str, Any], *, report_dir: Path = DEFAULT_REPORT_DIR) -> str:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = report_dir / f"{stamp}-autopilot-run.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return str(path)


def report_contains_test_claim(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "claim_ceiling" and str(item).startswith("Test "):
                return True
            if report_contains_test_claim(item):
                return True
    if isinstance(value, list):
        return any(report_contains_test_claim(item) for item in value)
    return False


def _auto_pause_config(contract: ProjectContract) -> dict[str, Any]:
    cfg = dict(contract.auto_pause)
    cfg.setdefault("enabled", True)
    cfg.setdefault("recent_report_limit", 8)
    cfg.setdefault("repeated_failure_threshold", 3)
    cfg.setdefault("repeated_issue_threshold", 3)
    cfg.setdefault(
        "pausing_stop_reasons",
        [
            "dirty_worktree_unsafe",
            "dirty_scope_unsafe",
            "closeout_not_eligible",
            "issue_not_ready",
            "no_ready_issue",
            "l5_execute_not_implemented",
        ],
    )
    return cfg


def load_run_reports(report_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    if not report_dir.exists():
        return []
    paths = sorted(report_dir.glob("*-autopilot-run.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    reports = []
    for path in paths[: max(0, limit)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            if report_contains_test_claim(payload):
                continue
            payload.setdefault("report_path", str(path))
            reports.append(payload)
    return reports


def report_issue_refs(report: dict[str, Any]) -> list[str]:
    refs = []
    for entry in report.get("planned") or []:
        if not isinstance(entry, dict):
            continue
        issue = entry.get("issue")
        if isinstance(issue, dict):
            ref = issue.get("number") or issue.get("title")
            if ref is not None:
                refs.append(str(ref))
    return refs


def pause_gate_from_reports(
    reports: list[dict[str, Any]],
    *,
    repeated_failure_threshold: int,
    repeated_issue_threshold: int,
    pausing_stop_reasons: list[str],
) -> dict[str, Any]:
    reasons = []
    recent_stop_reasons = [str(report.get("stop_reason") or "") for report in reports if report.get("stop_reason")]
    if recent_stop_reasons:
        first = recent_stop_reasons[0]
        repeated = 0
        for reason in recent_stop_reasons:
            if reason != first:
                break
            repeated += 1
        if repeated >= repeated_failure_threshold and first in set(pausing_stop_reasons):
            reasons.append(
                {
                    "reason": "repeated_failure_stop_reason",
                    "stop_reason": first,
                    "count": repeated,
                    "threshold": repeated_failure_threshold,
                }
            )

    recent_issue_refs = []
    for report in reports:
        refs = report_issue_refs(report)
        recent_issue_refs.append(refs[0] if refs else "")
    if recent_issue_refs and recent_issue_refs[0]:
        first_issue = recent_issue_refs[0]
        repeated_issue = 0
        for ref in recent_issue_refs:
            if ref != first_issue:
                break
            repeated_issue += 1
        if repeated_issue >= repeated_issue_threshold:
            reasons.append(
                {
                    "reason": "zeno_trap_repeated_issue",
                    "issue": first_issue,
                    "count": repeated_issue,
                    "threshold": repeated_issue_threshold,
                }
            )

    return {
        "status": "paused" if reasons else "ok",
        "pause_required": bool(reasons),
        "recent_report_count": len(reports),
        "reasons": reasons,
        "next_action": "reframe_or_create_operator_cut" if reasons else "continue",
    }


def pause_gate(contract: ProjectContract, *, report_dir: Path) -> dict[str, Any]:
    cfg = _auto_pause_config(contract)
    if not bool(cfg.get("enabled")):
        return {
            "status": "ok",
            "pause_required": False,
            "recent_report_count": 0,
            "reasons": [],
            "next_action": "continue",
            "disabled": True,
        }
    reports = load_run_reports(report_dir, limit=int(cfg.get("recent_report_limit") or 8))
    return pause_gate_from_reports(
        reports,
        repeated_failure_threshold=int(cfg.get("repeated_failure_threshold") or 3),
        repeated_issue_threshold=int(cfg.get("repeated_issue_threshold") or 3),
        pausing_stop_reasons=_as_list(cfg.get("pausing_stop_reasons")),
    )


def structured_issue_body(issue: dict[str, Any]) -> str:
    title = str(issue.get("title") or "Untitled task")
    body = str(issue.get("body") or "").strip()
    source = f"Original GitHub issue #{issue.get('number')}: {issue.get('url')}"
    if "命令行工具" in title or "run command" in body.casefold() or "run_command" in body:
        current_meaning = (
            "EgoOperator command-line capability needs a structured runtime contract: low-risk read-only "
            "inspection commands should be available through a controlled tool path, while modification, "
            "deletion, shell mutation, and broad execution still require operator authorization."
        )
        acceptance = (
            "- Read-only directory inspection can be performed through a registered command/tool path.\n"
            "- Mutation-capable commands remain gated by approval.\n"
            "- If the tool is unavailable, the agent returns a structured runtime capability error and does not claim it can execute.\n"
            "- Tests cover read-only allowed behavior, mutation blocked behavior, and user authorization messaging."
        )
        rollback = "Revert the command-tool exposure and tests; leave existing permission gates unchanged."
        ceiling = (
            "EgoOperator command-tool availability local candidate pass; not broad shell autonomy, stable user benefit, "
            "runtime efficacy, live autonomy, or consciousness."
        )
    else:
        current_meaning = "Normalize this unstructured task into a scoped implementation issue before any autopilot execution."
        acceptance = (
            "- Canonical source, current meaning, acceptance gate, rollback, and claim ceiling are explicit.\n"
            "- Autopilot classifies the resulting issue as ready only if the project contract allows it."
        )
        rollback = "Close the normalized issue as not planned or restore the original body if the framing is wrong."
        ceiling = "Structured task normalization only; not implementation proof."
    return (
        "This issue is a GitHub Project operating card, not the canonical authority source.\n\n"
        f"## Canonical source\n{source}\n\n"
        f"## Current meaning\n{current_meaning}\n\n"
        f"## Original observation\n{body or '(no body provided)'}\n\n"
        f"## Acceptance gate\n{acceptance}\n\n"
        "## Non-goals\n"
        "- Do not bypass existing runtime gates.\n"
        "- Do not modify program state or evidence ledger.\n"
        "- Do not treat local tests as real-provider or human-observable proof.\n\n"
        f"## Claim ceiling\n{ceiling}\n\n"
        f"## Rollback / close condition\n{rollback}\n"
    )


REQUIRED_DECOMPOSITION_SECTIONS = [
    "## Canonical source",
    "## Current meaning",
    "## Acceptance gate",
    "## Non-goals",
    "## Claim ceiling",
    "## Rollback / close condition",
]

OVERCLAIM_MARKERS = [
    "consciousness",
    "independent awareness",
    "stable user benefit",
    "runtime efficacy",
    "live autonomy",
    "durable memory efficacy",
    "真正意识",
    "独立意识",
    "自主意识",
    "稳定用户收益",
]


def goal_summary(goal: str) -> str:
    for line in goal.splitlines():
        text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if text:
            return text[:120]
    return "Untitled goal"


def goal_units(goal: str, *, max_issues: int) -> list[str]:
    units = []
    for line in goal.splitlines():
        match = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$", line)
        if match:
            units.append(match.group(1).strip())
    if not units:
        summary = goal_summary(goal)
        units = [
            f"{summary}: contract and acceptance gate",
            f"{summary}: scoped implementation primitive",
            f"{summary}: scripted or human-observable evaluation gate",
        ]
    return units[: max(1, max_issues)]


def _slug_words(text: str, *, max_words: int = 9) -> str:
    words = re.findall(r"[\w\u4e00-\u9fff]+", text, flags=re.UNICODE)
    if not words:
        return "scoped task"
    return " ".join(words[:max_words])


def compact_issue_title(prefix: str, meaning: str, *, max_chars: int = 96) -> str:
    title = f"{prefix} {_slug_words(meaning)}".strip()
    if len(title) <= max_chars:
        return title
    return title[: max_chars - 1].rstrip() + "…"


def preferred_ready_prefix(contract: ProjectContract) -> str:
    prefixes = _as_list(contract.task_classification.get("ready_title_prefixes"))
    return prefixes[0] if prefixes else "Codex Task:"


def decomposition_issue_body(
    *,
    canonical_source: str,
    current_meaning: str,
    observation_class: str,
) -> str:
    return (
        "This issue is a GitHub Project operating card, not the canonical authority source.\n\n"
        f"## Canonical source\n{canonical_source}\n\n"
        f"## Current meaning\n{current_meaning}\n\n"
        f"Observation class: {observation_class}\n\n"
        "## Acceptance gate\n"
        "- The scoped output directly addresses the current meaning.\n"
        "- Deterministic or scripted evidence is attached for non-human observation classes.\n"
        "- `python3 scripts/codex_project_autopilot.py closeout-check --issue <this>` returns a bounded eligibility packet before closeout.\n\n"
        "## Non-goals\n"
        "- Do not bypass project contract, proposal, gate, trace, or protected-path rules.\n"
        "- Do not modify program state or evidence ledger unless a separate Stage Card explicitly permits it.\n"
        "- Do not treat local/scripted proof as human-observable or durable product efficacy.\n\n"
        "## Claim ceiling\n"
        "Local proposal or implementation candidate only; not stable user benefit, runtime efficacy, live autonomy, durable memory efficacy, independent awareness, or consciousness.\n\n"
        "## Rollback / close condition\n"
        "Revert the scoped implementation or close as superseded/not planned if the task framing fails the acceptance gate.\n"
    )


def review_decomposition_proposals(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    findings = []
    for index, proposal in enumerate(proposals):
        body = str(proposal.get("body") or "")
        title = str(proposal.get("title") or "")
        for section in REQUIRED_DECOMPOSITION_SECTIONS:
            if section not in body:
                findings.append({"index": index, "title": title, "reason": "missing_required_section", "section": section})
        for line_number, line in enumerate(body.splitlines(), start=1):
            line_cf = line.casefold()
            negated = any(token in line_cf for token in ["not ", "do not", "不得", "不能", "non-goal", "not stable"])
            for marker in OVERCLAIM_MARKERS:
                if marker.casefold() in line_cf and not negated:
                    findings.append(
                        {
                            "index": index,
                            "title": title,
                            "reason": "possible_overclaim",
                            "marker": marker,
                            "line": line_number,
                        }
                    )
    return {
        "verdict": "proposal_set_ready" if not findings else "needs_revision",
        "finding_count": len(findings),
        "findings": findings,
    }


def decompose_goal(
    contract: ProjectContract,
    *,
    goal: str,
    canonical_source: str,
    title_prefix: str | None,
    max_issues: int,
    observation_class: str,
) -> dict[str, Any]:
    if not goal.strip():
        raise AutopilotError("missing_goal", "decompose-goal requires --goal text or --goal-file content")
    prefix = title_prefix or preferred_ready_prefix(contract)
    units = goal_units(goal, max_issues=max_issues)
    proposals = []
    for index, unit in enumerate(units, start=1):
        meaning = unit.strip()
        title = compact_issue_title(prefix, meaning)
        proposals.append(
            {
                "index": index,
                "title": title,
                "project_status": "Todo",
                "observation_class": observation_class,
                "body": decomposition_issue_body(
                    canonical_source=canonical_source,
                    current_meaning=meaning,
                    observation_class=observation_class,
                ),
            }
        )
    review = review_decomposition_proposals(proposals)
    return {
        "status": "ok",
        "goal_summary": goal_summary(goal),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "reviewer_check": review,
        "claim_ceiling": "Task decomposition proposal generation only; not GitHub issue creation or execution proof.",
    }


def read_goal_input(goal: str | None, goal_file: str | None) -> str:
    if goal and goal_file:
        raise AutopilotError("ambiguous_goal_input", "Use either --goal or --goal-file, not both")
    if goal_file:
        return Path(goal_file).read_text(encoding="utf-8")
    return goal or ""


def command_baseline(contract: ProjectContract, *, baseline_path: Path, runner: CommandRunner) -> dict[str, Any]:
    entries = dirty_entries(runner)
    payload = write_baseline(baseline_path, entries, contract)
    return {
        "status": "ok",
        "baseline_path": str(baseline_path),
        "entry_count": payload["entry_count"],
        "note": "local operational state only; not repo authority or evidence ledger",
    }


def command_diff_scope(contract: ProjectContract, *, baseline_path: Path, runner: CommandRunner) -> dict[str, Any]:
    return diff_scope_summary(contract, baseline_path, runner)


def command_pause_check(contract: ProjectContract, *, report_dir: Path) -> dict[str, Any]:
    return pause_gate(contract, report_dir=report_dir)


def command_normalize_issue(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    if not dry_run:
        raise AutopilotError("mutation_not_implemented", "v2 normalize-issue only supports --dry-run")
    issue = issue_view_full(client, contract.github_config(), issue_ref)
    return {
        "status": "ok",
        "mode": "dry_run",
        "issue": {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "url": issue.get("url"),
        },
        "proposed_body": structured_issue_body(issue),
    }


def command_decompose_goal(
    contract: ProjectContract,
    *,
    goal: str | None,
    goal_file: str | None,
    canonical_source: str | None,
    title_prefix: str | None,
    max_issues: int,
    observation_class: str,
) -> dict[str, Any]:
    return decompose_goal(
        contract,
        goal=read_goal_input(goal, goal_file),
        canonical_source=canonical_source or "Generated from decompose-goal input",
        title_prefix=title_prefix,
        max_issues=max_issues,
        observation_class=observation_class,
    )


def command_run_once(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    dry_run: bool,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    if not dry_run:
        raise AutopilotError("mutation_not_implemented", "v2 run-once only supports --dry-run")
    classified = command_classify_issue(client, contract, issue_ref)
    classification = classified["classification"]
    if classification.get("autopilot_allowed") is not True:
        return {
            "status": "stopped",
            "stop_reason": "issue_not_ready",
            "issue": classified["issue"],
            "classification": classification,
            "planned": [],
        }
    gate = dirty_gate(contract, runner, baseline_path)
    if gate["status"] != "ok":
        return {
            "status": "stopped",
            "stop_reason": gate["stop_reason"],
            "issue": classified["issue"],
            "classification": classification,
            "dirty_gate": gate,
            "planned": [],
        }
    return {
        "status": "ok",
        "mode": "dry_run",
        "issue": classified["issue"],
        "classification": classification,
        "dirty_gate": gate,
        "planned": [
            {"step": "load_issue", "issue": issue_ref},
            {"step": "confirm_scope", "source": "project_contract"},
            {"step": "run_target_verification", "profile": "autopilot_target"},
            {"step": "implement_scoped_patch", "note": "not executed in v2 dry-run"},
            {"step": "run_full_verification", "profile": "autopilot_full"},
        ],
    }


def command_closeout_check(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    return closeout_packet(client, contract, issue_ref, baseline_path=baseline_path, runner=runner)


def command_executor_check(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    return executor_packet(client, contract, issue_ref, baseline_path=baseline_path, runner=runner)


def command_closeout_once(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    issue_ref: str,
    *,
    dry_run: bool,
    execute: bool,
    baseline_path: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    if dry_run and execute:
        raise AutopilotError("invalid_closeout_mode", "Choose either --dry-run or --execute, not both")
    effective_dry_run = not execute
    packet = closeout_packet(client, contract, issue_ref, baseline_path=baseline_path, runner=runner)
    if not packet.get("eligible"):
        return {
            "status": "stopped",
            "stop_reason": "closeout_not_eligible",
            "packet": packet,
            "planned": [],
        }

    status = str(contract.auto_closeout.get("done_status") or "Done")
    comment = str(packet["closeout_comment"])
    if effective_dry_run:
        cfg = contract.github_config(dry_run=True)
        planned = github_project_task.command_closeout(
            client,
            cfg,
            argparse.Namespace(issue=issue_ref, status=status, comment=comment, comment_file=None),
        )
        return {
            "status": "ok",
            "mode": "dry_run",
            "packet": packet,
            "planned": planned.get("planned", []),
        }

    cfg = contract.github_config(dry_run=False)
    result = github_project_task.command_closeout(
        client,
        cfg,
        argparse.Namespace(issue=issue_ref, status=status, comment=comment, comment_file=None),
    )
    return {
        "status": "ok",
        "mode": "execute",
        "packet": packet,
        "closeout": result,
    }


def command_run_loop(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    dry_run: bool,
    execute: bool,
    mode: str,
    max_issues: int,
    max_minutes: int,
    baseline_path: Path,
    runner: CommandRunner,
    write_report: bool,
    report_dir: Path,
) -> dict[str, Any]:
    if dry_run and execute:
        raise AutopilotError("invalid_run_loop_mode", "Choose either --dry-run or --execute, not both")
    effective_dry_run = not execute
    started = time.monotonic()
    if max_issues <= 0 or max_minutes <= 0:
        payload = {
            "status": "stopped",
            "stop_reason": "budget_exhausted",
            "max_issues": max_issues,
            "max_minutes": max_minutes,
            "planned": [],
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    pause = pause_gate(contract, report_dir=report_dir)
    if pause.get("pause_required"):
        payload = {
            "status": "stopped",
            "stop_reason": "autopilot_pause_required",
            "pause_gate": pause,
            "planned": [],
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    gate = dirty_gate(contract, runner, baseline_path)
    if gate["status"] != "ok":
        payload = {
            "status": "stopped",
            "stop_reason": gate["stop_reason"],
            "dirty_gate": gate,
            "planned": [],
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    report = build_report(client, contract)
    ready = [
        issue
        for issue in report.get("issues", [])
        if issue.get("classification", {}).get("autopilot_allowed") is True
    ]
    if not ready:
        payload = {
            "status": "stopped",
            "stop_reason": "no_ready_issue",
            "counts": report["counts"],
            "planned": [],
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    status_rank = {"In Progress": 0, "Todo": 1}
    ready.sort(key=lambda item: (status_rank.get(str(item.get("project_status")), 99), int(item.get("number") or 999999)))
    selected = ready[:max_issues]

    if mode == "l3-closeout":
        planned = []
        closed = []
        for item in selected:
            issue_ref = str(item.get("number"))
            packet = closeout_packet(client, contract, issue_ref, baseline_path=baseline_path, runner=runner)
            entry: dict[str, Any] = {
                "issue": item,
                "closeout_check": {
                    "status": packet.get("status"),
                    "eligible": packet.get("eligible"),
                    "blocked_reasons": packet.get("blocked_reasons"),
                    "claim_ceiling": packet.get("claim_ceiling"),
                },
            }
            if packet.get("eligible") and execute:
                result = command_closeout_once(
                    client,
                    contract,
                    issue_ref,
                    dry_run=False,
                    execute=True,
                    baseline_path=baseline_path,
                    runner=runner,
                )
                entry["closeout"] = result.get("closeout")
                closed.append(issue_ref)
            elif packet.get("eligible"):
                entry["dry_run_action"] = "would_closeout"
            else:
                entry["dry_run_action"] = "would_skip"
            planned.append(entry)
        payload = {
            "status": "ok",
            "mode": "l3-closeout",
            "dry_run": effective_dry_run,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "planned": planned,
            "closed": closed,
            "stop_reason": "max_issues_reached" if len(ready) > max_issues else "ready_queue_exhausted",
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    if mode == "l5-executor":
        if execute:
            payload = {
                "status": "stopped",
                "mode": "l5-executor",
                "dry_run": False,
                "stop_reason": "l5_execute_not_implemented",
                "planned": [],
                "note": "L5 v1 only emits executor eligibility packets; it does not mutate code unattended.",
            }
            if write_report:
                payload["report_path"] = write_run_report(payload, report_dir=report_dir)
            return payload
        planned = []
        for item in selected:
            issue_ref = str(item.get("number"))
            packet = executor_packet(client, contract, issue_ref, baseline_path=baseline_path, runner=runner)
            planned.append(
                {
                    "issue": item,
                    "executor_check": {
                        "status": packet.get("status"),
                        "eligible": packet.get("eligible"),
                        "blocked_reasons": packet.get("blocked_reasons"),
                        "claim_ceiling": packet.get("claim_ceiling"),
                        "verify_profile": packet.get("verify_profile"),
                    },
                    "dry_run_action": "would_enter_bounded_rollout" if packet.get("eligible") else "would_skip",
                }
            )
        payload = {
            "status": "ok",
            "mode": "l5-executor",
            "dry_run": True,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "planned": planned,
            "stop_reason": "max_issues_reached" if len(ready) > max_issues else "ready_queue_exhausted",
        }
        if write_report:
            payload["report_path"] = write_run_report(payload, report_dir=report_dir)
        return payload

    planned = [
        {
            "issue": item,
            "dry_run_action": "would_run_once",
            "note": "plan mode does not mutate code, GitHub Project state, commits, or close issues",
        }
        for item in selected
    ]
    payload = {
        "status": "ok",
        "mode": "plan",
        "dry_run": effective_dry_run,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "planned": planned,
        "stop_reason": "max_issues_reached" if len(ready) > max_issues else "ready_queue_exhausted",
    }
    if write_report:
        payload["report_path"] = write_run_report(payload, report_dir=report_dir)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-project Codex autopilot helpers")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH), help="Path to project contract YAML")
    parser.add_argument("--baseline-path", default=str(DEFAULT_BASELINE_PATH), help="Path to local dirty baseline JSON")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Path to local autopilot run reports")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("report")
    subparsers.add_parser("plan-next")
    subparsers.add_parser("baseline")
    subparsers.add_parser("diff-scope")
    subparsers.add_parser("pause-check")

    verify_profile = subparsers.add_parser("verify-profile")
    verify_profile.add_argument("--profile", required=True)

    classify = subparsers.add_parser("classify-issue")
    classify.add_argument("--issue", required=True)

    normalize = subparsers.add_parser("normalize-issue")
    normalize.add_argument("--issue", required=True)
    normalize.add_argument("--dry-run", action="store_true")

    decompose = subparsers.add_parser("decompose-goal")
    decompose.add_argument("--goal")
    decompose.add_argument("--goal-file")
    decompose.add_argument("--canonical-source")
    decompose.add_argument("--title-prefix")
    decompose.add_argument("--max-issues", type=int, default=6)
    decompose.add_argument("--observation-class", default="deterministic_local")

    once = subparsers.add_parser("run-once")
    once.add_argument("--issue", required=True)
    once.add_argument("--dry-run", action="store_true")

    closeout_check = subparsers.add_parser("closeout-check")
    closeout_check.add_argument("--issue", required=True)

    executor_check = subparsers.add_parser("executor-check")
    executor_check.add_argument("--issue", required=True)

    closeout_once = subparsers.add_parser("closeout-once")
    closeout_once.add_argument("--issue", required=True)
    closeout_once.add_argument("--dry-run", action="store_true")
    closeout_once.add_argument("--execute", action="store_true")

    loop = subparsers.add_parser("run-loop")
    loop.add_argument("--dry-run", action="store_true")
    loop.add_argument("--execute", action="store_true")
    loop.add_argument("--mode", choices=["plan", "l3-closeout", "l5-executor"], default="plan")
    loop.add_argument("--max-issues", type=int, default=1)
    loop.add_argument("--max-minutes", type=int, default=10)
    loop.add_argument("--write-report", action="store_true")
    return parser


def write_json(payload: dict[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    stream.write("\n")


def dispatch(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    args: argparse.Namespace,
    *,
    runner: CommandRunner,
) -> dict[str, Any]:
    if args.command == "doctor":
        return command_doctor(client, contract)
    if args.command == "report":
        return command_report(client, contract)
    if args.command == "plan-next":
        return command_plan_next(client, contract)
    if args.command == "classify-issue":
        return command_classify_issue(client, contract, args.issue)
    if args.command == "baseline":
        return command_baseline(contract, baseline_path=Path(args.baseline_path), runner=runner)
    if args.command == "diff-scope":
        return command_diff_scope(contract, baseline_path=Path(args.baseline_path), runner=runner)
    if args.command == "pause-check":
        return command_pause_check(contract, report_dir=Path(args.report_dir))
    if args.command == "verify-profile":
        return command_verify_profile(contract, args.profile, runner=runner)
    if args.command == "normalize-issue":
        return command_normalize_issue(client, contract, args.issue, dry_run=bool(args.dry_run))
    if args.command == "decompose-goal":
        return command_decompose_goal(
            contract,
            goal=args.goal,
            goal_file=args.goal_file,
            canonical_source=args.canonical_source,
            title_prefix=args.title_prefix,
            max_issues=args.max_issues,
            observation_class=args.observation_class,
        )
    if args.command == "run-once":
        return command_run_once(
            client,
            contract,
            args.issue,
            dry_run=bool(args.dry_run),
            baseline_path=Path(args.baseline_path),
            runner=runner,
        )
    if args.command == "closeout-check":
        return command_closeout_check(
            client,
            contract,
            args.issue,
            baseline_path=Path(args.baseline_path),
            runner=runner,
        )
    if args.command == "executor-check":
        return command_executor_check(
            client,
            contract,
            args.issue,
            baseline_path=Path(args.baseline_path),
            runner=runner,
        )
    if args.command == "closeout-once":
        return command_closeout_once(
            client,
            contract,
            args.issue,
            dry_run=bool(args.dry_run),
            execute=bool(args.execute),
            baseline_path=Path(args.baseline_path),
            runner=runner,
        )
    if args.command == "run-loop":
        return command_run_loop(
            client,
            contract,
            dry_run=bool(args.dry_run),
            execute=bool(args.execute),
            mode=str(args.mode),
            max_issues=args.max_issues,
            max_minutes=args.max_minutes,
            baseline_path=Path(args.baseline_path),
            runner=runner,
            write_report=bool(args.write_report),
            report_dir=Path(args.report_dir),
        )
    raise AutopilotError("unknown_command", f"Unknown command: {args.command}")


def main(
    argv: list[str] | None = None,
    *,
    client: github_project_task.GhClient | None = None,
    runner: CommandRunner | None = None,
    stdout: TextIO | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    try:
        contract = load_contract(Path(args.contract))
        payload = dispatch(client or github_project_task.GhClient(), contract, args, runner=runner or CommandRunner())
        write_json(payload, out)
        return 0
    except AutopilotError as exc:
        write_json({"status": "error", "error": exc.code, "message": exc.message, **exc.details}, out)
        return 2
    except github_project_task.UserError as exc:
        write_json({"status": "error", "error": exc.code, "message": exc.message, **exc.details}, out)
        return 2
    except github_project_task.GhCommandError as exc:
        write_json(
            {
                "status": "error",
                "error": "gh_command_failed",
                "message": str(exc),
                "returncode": exc.returncode,
                "gh_args": exc.args_list,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
            out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
