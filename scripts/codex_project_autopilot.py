#!/usr/bin/env python3
"""Cross-project Codex task-board autopilot helpers."""

from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_PLAN_SCHEMA_PATH = SCRIPT_DIR / "codex_autopilot_plan_proposal_schema.json"

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
    goal_control: dict[str, Any] = field(default_factory=dict)
    epic_rollup: dict[str, Any] = field(default_factory=dict)

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
        goal_control=_require_mapping(
            payload.get("goal_control") or {},
            code="invalid_goal_control",
            message="goal_control must be an object",
        ),
        epic_rollup=_require_mapping(
            payload.get("epic_rollup") or {},
            code="invalid_epic_rollup",
            message="epic_rollup must be an object",
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


def _goal_control_config(contract: ProjectContract) -> dict[str, Any]:
    cfg = dict(contract.goal_control)
    cfg.setdefault("planning_backend", "codex_exec")
    cfg.setdefault("native_goal_enabled", False)
    cfg.setdefault("candidate_issue_limit", 3)
    cfg.setdefault("claim_ceiling", "Codex Autopilot goal-aware meta-control local workflow candidate pass")
    cfg.setdefault(
        "hard_stop_markers",
        [
            "program state",
            "evidence ledger",
            "permissions expansion",
            "permission expansion",
            "memory promotion",
            "mainline demotion",
            "stage card",
            "docs/PROGRAM_STATE_UNIFIED.yaml",
            "artifacts/evidence_ledger",
        ],
    )
    return cfg


def outcome_scoreboard(report: dict[str, Any], *, recent_reports: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    counts = {str(key): int(value) for key, value in (report.get("counts") or {}).items()}
    recent_reports = recent_reports or []
    stop_reasons: dict[str, int] = {}
    verify_failures = 0
    verify_seen = 0
    evidence_complete = 0
    evidence_seen = 0
    for payload in recent_reports:
        reason = str(payload.get("stop_reason") or "")
        if reason:
            stop_reasons[reason] = stop_reasons.get(reason, 0) + 1
        for entry in payload.get("planned") or []:
            if not isinstance(entry, dict):
                continue
            check = entry.get("closeout_check") if isinstance(entry.get("closeout_check"), dict) else {}
            if check:
                evidence_seen += 1
                if check.get("eligible") is True:
                    evidence_complete += 1
            verify = entry.get("verify") if isinstance(entry.get("verify"), dict) else {}
            if verify:
                verify_seen += 1
                if verify.get("passed") is False:
                    verify_failures += 1
    human_required = [
        issue.get("number")
        for issue in report.get("issues") or []
        if (issue.get("classification") or {}).get("class") == "human_required"
    ]
    return {
        "ready_issue_throughput": {
            "done_count": counts.get("done", 0),
            "ready_count": counts.get("ready", 0) + counts.get("research", 0),
            "note": "Board-count proxy; not productivity proof.",
        },
        "blocked_reasons": {
            "class_counts": {
                key: counts.get(key, 0)
                for key in ["unknown", "blocked", "human_required", "aggregate", "parked", "supporting", "high_impact"]
                if counts.get(key, 0)
            },
            "recent_stop_reasons": stop_reasons,
        },
        "reopened_issue_count": {
            "status": "unknown",
            "reason": "GitHub issue reopen events are not queried in v3.",
        },
        "human_required_aging": {
            "status": "unknown",
            "issue_numbers": human_required[:20],
            "reason": "Project item age is not part of the current gh item-list payload.",
        },
        "verify_failure_rate": {
            "status": "known" if verify_seen else "unknown",
            "failures": verify_failures,
            "total": verify_seen,
        },
        "closeout_evidence_completeness": {
            "status": "known" if evidence_seen else "unknown",
            "eligible_packets": evidence_complete,
            "total_packets": evidence_seen,
        },
    }


def command_goal_status(client: github_project_task.GhClient, contract: ProjectContract, *, report_dir: Path) -> dict[str, Any]:
    report = build_report(client, contract)
    selected = select_next(report)
    recent_reports = load_run_reports(report_dir, limit=int(_goal_control_config(contract).get("recent_report_limit") or 8))
    ready_issues = [
        issue
        for issue in report.get("issues", [])
        if (issue.get("classification") or {}).get("autopilot_allowed") is True
    ]
    return {
        "status": "ok",
        "control_plane": "goal-aware",
        "project": report.get("project"),
        "counts": report.get("counts"),
        "ready_issue_count": len(ready_issues),
        "next_issue": selected,
        "human_required": [
            {"number": issue.get("number"), "title": issue.get("title"), "project_status": issue.get("project_status")}
            for issue in report.get("issues", [])
            if (issue.get("classification") or {}).get("class") == "human_required"
        ],
        "highest_risk": goal_highest_risk(report),
        "outcome_scoreboard": outcome_scoreboard(report, recent_reports=recent_reports),
        "goal_control": _goal_control_config(contract),
        "claim_ceiling": _goal_control_config(contract).get("claim_ceiling"),
    }


def goal_highest_risk(report: dict[str, Any]) -> dict[str, Any]:
    priority = ["high_impact", "unknown", "human_required", "blocked", "aggregate", "parked"]
    issues = report.get("issues") or []
    for cls in priority:
        matches = [issue for issue in issues if (issue.get("classification") or {}).get("class") == cls]
        if matches:
            return {
                "class": cls,
                "count": len(matches),
                "sample": [
                    {"number": item.get("number"), "title": item.get("title"), "reason": (item.get("classification") or {}).get("reason")}
                    for item in matches[:5]
                ],
            }
    return {"class": "none", "count": 0, "sample": []}


def goal_refresh_packet(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    issue_ref: str | None = None,
    report_dir: Path,
) -> dict[str, Any]:
    report = build_report(client, contract)
    selected = select_next(report)
    issue_payload = None
    if issue_ref:
        issue_payload = command_classify_issue(client, contract, issue_ref)
    recent_reports = load_run_reports(report_dir, limit=int(_goal_control_config(contract).get("recent_report_limit") or 8))
    return {
        "status": "ok",
        "project": report.get("project"),
        "goal_control": _goal_control_config(contract),
        "board_counts": report.get("counts"),
        "issues": report.get("issues"),
        "ready_issue": selected,
        "issue": issue_payload,
        "highest_risk": goal_highest_risk(report),
        "recent_reports": [
            {
                "status": item.get("status"),
                "mode": item.get("mode"),
                "stop_reason": item.get("stop_reason"),
                "report_path": item.get("report_path"),
            }
            for item in recent_reports[:8]
        ],
        "outcome_scoreboard": outcome_scoreboard(report, recent_reports=recent_reports),
        "claim_ceiling": _goal_control_config(contract).get("claim_ceiling"),
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
        "goal_control": contract.goal_control,
        "epic_rollup": contract.epic_rollup,
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


def text_digest(text: str, *, max_chars: int = 280) -> dict[str, Any]:
    if len(text) <= max_chars:
        return {"text": text, "chars": len(text), "truncated": False}
    head_len = max(80, max_chars // 2)
    tail_len = max(60, max_chars - head_len - 40)
    omitted = max(0, len(text) - head_len - tail_len)
    return {
        "head": text[:head_len],
        "tail": text[-tail_len:] if tail_len else "",
        "chars": len(text),
        "omitted": omitted,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "truncated": True,
    }


def format_digest_text(text: str, *, max_chars: int = 220) -> str:
    digest = text_digest(text, max_chars=max_chars)
    if not digest.get("truncated"):
        return str(digest.get("text") or "").strip()
    head = str(digest.get("head") or "").replace("\n", "\\n")
    tail = str(digest.get("tail") or "").replace("\n", "\\n")
    return (
        f"{head} ... {tail} "
        f"(chars={digest['chars']}, omitted={digest['omitted']}, sha256={str(digest['sha256'])[:12]})"
    )


def extract_markdown_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^(?:##\s+{re.escape(heading)}|{re.escape(heading)}\s*:)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(body)
    if not match:
        return ""
    rest = body[match.end() :]
    next_heading = re.search(
        r"^(?:##\s+|[A-Za-z][A-Za-z0-9 /_-]{0,80}\s*:).*$",
        rest,
        flags=re.MULTILINE,
    )
    if next_heading:
        rest = rest[: next_heading.start()]
    return rest.strip()


def section_bullets(section: str) -> list[str]:
    bullets = []
    for line in section.splitlines():
        text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if text:
            bullets.append(text)
    return bullets


def issue_closeout_evidence_items(issue: dict[str, Any]) -> list[dict[str, Any]]:
    body = str(issue.get("body") or "")
    items = []
    for heading in ("Closeout evidence", "Evidence", "Implementation evidence", "Human evidence"):
        section = extract_markdown_section(body, heading)
        if not section:
            continue
        for bullet in section_bullets(section):
            bullet_cf = bullet.casefold()
            if (
                "planner proposal" in bullet_cf
                or "plan proposal" in bullet_cf
                or "candidate issue" in bullet_cf
                or "candidate task" in bullet_cf
            ):
                items.append(
                    {
                        "type": "planner_proposal",
                        "source": f"issue_body:{heading}",
                        "status": "proposal_only",
                        "summary": bullet,
                    }
                )
                continue
            items.append(
                {
                    "type": "issue_evidence",
                    "source": f"issue_body:{heading}",
                    "status": "pass",
                    "summary": bullet,
                }
            )
    return items


def acceptance_results(issue: dict[str, Any], *, eligible: bool, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    section = extract_markdown_section(str(issue.get("body") or ""), "Acceptance gate")
    bullets = section_bullets(section)
    if not bullets:
        bullets = ["Acceptance gate not listed in issue body."]
    status = "pass" if eligible and evidence_items else "unknown"
    return [{"gate": bullet, "status": status} for bullet in bullets[:8]]


def issue_current_meaning(issue: dict[str, Any]) -> str:
    if issue.get("current_meaning"):
        return str(issue.get("current_meaning"))
    body = str(issue.get("body") or "")
    meaning = extract_markdown_section(body, "Current meaning")
    if meaning:
        clean_lines = []
        for line in meaning.splitlines():
            if re.match(r"\s*(?:observation|evidence)[ _-]?class\s*[:：]", line, flags=re.IGNORECASE):
                break
            if not line.strip() and clean_lines:
                break
            if line.strip():
                clean_lines.append(line.strip())
        return format_digest_text(" ".join(clean_lines or meaning.split()), max_chars=240)
    return str(issue.get("title") or "Issue target unavailable")


def collect_implementation_refs(runner: CommandRunner) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "branch": None,
        "head_commit": None,
        "head_commit_short": None,
        "push_status": "unknown",
        "changed_files": [],
        "change_source": "unknown",
    }

    def run_optional(args: list[str]) -> CommandResult | None:
        try:
            result = runner.run(args)
        except Exception:
            return None
        return result if result.returncode == 0 else None

    branch = run_optional(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        refs["branch"] = branch.stdout.strip() or None

    head = run_optional(["git", "rev-parse", "HEAD"])
    if head:
        full = head.stdout.strip()
        refs["head_commit"] = full or None
        refs["head_commit_short"] = full[:12] if full else None

    status = run_optional(["git", "status", "-sb"])
    if status:
        first_line = (status.stdout.splitlines() or [""])[0]
        if "ahead" in first_line:
            refs["push_status"] = "ahead"
        elif "behind" in first_line:
            refs["push_status"] = "behind"
        elif first_line:
            refs["push_status"] = "synced_or_unknown"

    dirty = run_optional(["git", "status", "--short", "--untracked-files=all"])
    dirty_files: list[str] = []
    if dirty:
        for line in dirty.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:] if len(line) > 3 else line.strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            dirty_files.append(path.strip())
    if dirty_files:
        refs["changed_files"] = dirty_files[:40]
        refs["change_source"] = "worktree_dirty"
        return refs

    changed = run_optional(["git", "show", "--name-only", "--format=", "--diff-filter=ACMR", "HEAD"])
    if changed:
        refs["changed_files"] = [line.strip() for line in changed.stdout.splitlines() if line.strip()][:40]
        if refs["changed_files"]:
            refs["change_source"] = "git_head"
    return refs


def verify_evidence_items(verify: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not verify:
        return []
    items = []
    for result in verify.get("results") or []:
        if not isinstance(result, dict):
            continue
        command = " ".join(str(part) for part in result.get("command") or [])
        stdout = str(result.get("stdout_preview") or "")
        stderr = str(result.get("stderr_preview") or "")
        summary_bits = []
        if stdout.strip():
            summary_bits.append(f"stdout: {format_digest_text(stdout, max_chars=160)}")
        if stderr.strip():
            summary_bits.append(f"stderr: {format_digest_text(stderr, max_chars=160)}")
        items.append(
            {
                "type": "verification",
                "source": f"verify_profile:{verify.get('profile')}",
                "command": command,
                "status": "pass" if result.get("passed") else "fail",
                "summary": "; ".join(summary_bits) if summary_bits else f"returncode={result.get('returncode')}",
            }
        )
    return items


def implementation_evidence_items(refs: dict[str, Any]) -> list[dict[str, Any]]:
    files = [str(path) for path in refs.get("changed_files") or []]
    if not files:
        return []
    preview = ", ".join(files[:8])
    if len(files) > 8:
        preview += f", ... (+{len(files) - 8} more)"
    return [
        {
            "type": "implementation",
            "source": refs.get("change_source") or "implementation",
            "status": "pass",
            "summary": f"{refs.get('change_source') or 'implementation'} changes tracked files: {preview}",
            "path": refs.get("head_commit_short"),
        }
    ]


def observation_boundary(observation_class: str) -> dict[str, Any]:
    if observation_class == "deterministic_local":
        return {
            "class": observation_class,
            "can_claim": "local deterministic workflow candidate pass",
            "cannot_claim": "real user perception, runtime efficacy, live autonomy, durable memory efficacy, or consciousness",
        }
    if observation_class == "research":
        return {
            "class": observation_class,
            "can_claim": "bounded research/report candidate pass",
            "cannot_claim": "runtime efficacy, human perception, stable product benefit, live autonomy, durable memory efficacy, or consciousness",
        }
    if observation_class == "scripted_real_entry":
        return {
            "class": observation_class,
            "can_claim": "scripted real-entry candidate pass",
            "cannot_claim": "human preference, long-run stability, live autonomy, durable memory efficacy, or consciousness",
        }
    if observation_class == "scripted_with_llm_judge":
        return {
            "class": observation_class,
            "can_claim": "scripted candidate pass with reviewer-bounded judgment",
            "cannot_claim": "human preference, stable product benefit, live autonomy, durable memory efficacy, or consciousness",
        }
    return {
        "class": observation_class,
        "can_claim": "none without additional gate",
        "cannot_claim": "automatic closeout",
    }


def build_closeout_evidence_packet(
    *,
    issue: dict[str, Any],
    observation_class: str,
    verify: dict[str, Any] | None,
    implementation_refs: dict[str, Any],
    reviewer: dict[str, Any] | None,
    eligible: bool,
) -> dict[str, Any]:
    evidence_items = []
    evidence_items.extend(issue_closeout_evidence_items(issue))
    evidence_items.extend(verify_evidence_items(verify))
    evidence_items.extend(implementation_evidence_items(implementation_refs))
    if reviewer:
        evidence_items.append(
            {
                "type": "reviewer",
                "source": "llm_reviewer",
                "status": "pass" if reviewer.get("verdict") == "closeout_allowed" else "blocked",
                "summary": "; ".join(str(reason) for reason in reviewer.get("reasons") or []) or str(reviewer.get("reason") or ""),
            }
        )
    return {
        "evidence_items": evidence_items,
        "implementation_refs": implementation_refs,
        "acceptance_result": acceptance_results(issue, eligible=eligible, evidence_items=evidence_items),
        "observation_boundary": observation_boundary(observation_class),
        "residuals": [
            "No human-observable or durable product claim is made unless explicit human evidence is cited."
        ],
    }


def closeout_evidence_blockers(observation_class: str, evidence_packet: dict[str, Any]) -> list[dict[str, Any]]:
    items = [item for item in evidence_packet.get("evidence_items") or [] if isinstance(item, dict)]
    passed_verify = any(item.get("type") == "verification" and item.get("status") == "pass" for item in items)
    issue_specific = any(item.get("type") in {"issue_evidence", "implementation", "reviewer"} for item in items)
    blockers = []
    if observation_class == "deterministic_local":
        if not passed_verify:
            blockers.append({"reason": "closeout_evidence_missing_verification"})
        if not issue_specific:
            blockers.append({"reason": "closeout_evidence_missing_issue_specific_item"})
    elif observation_class == "research":
        if not passed_verify:
            blockers.append({"reason": "closeout_evidence_missing_verification"})
        research_evidence = any(
            item.get("type") == "issue_evidence"
            and re.search(r"(research|matrix|report|inventory|scan|artifact|研究|矩阵|报告|清单)", str(item.get("summary") or ""), re.I)
            for item in items
        )
        if not research_evidence:
            blockers.append({"reason": "closeout_evidence_missing_research_report_item"})
    elif observation_class == "scripted_real_entry":
        if not passed_verify:
            blockers.append({"reason": "closeout_evidence_missing_verification"})
        real_entry = any(
            item.get("type") == "issue_evidence"
            and re.search(r"(scripted|real[-_ ]?entry|entrypoint|report|smoke|入口|报告)", str(item.get("summary") or ""), re.I)
            for item in items
        )
        if not real_entry:
            blockers.append({"reason": "closeout_evidence_missing_scripted_real_entry_item"})
    return blockers


def closeout_comment_draft(packet: dict[str, Any]) -> str:
    issue = packet.get("issue") or {}
    verify = packet.get("verify") or {}
    claim = packet.get("claim_ceiling") or "local workflow candidate pass"
    evidence_packet = packet.get("evidence_packet") or {}
    implementation = evidence_packet.get("implementation_refs") or {}
    acceptance = evidence_packet.get("acceptance_result") or []
    evidence_items = evidence_packet.get("evidence_items") or []
    residuals = evidence_packet.get("residuals") or []
    boundary = evidence_packet.get("observation_boundary") or {}

    changed_files = implementation.get("changed_files") or []
    changed_summary = ", ".join(str(path) for path in changed_files[:8]) if changed_files else "not captured"
    if len(changed_files) > 8:
        changed_summary += f", ... (+{len(changed_files) - 8} more)"

    lines = [
        f"Closeout for #{issue.get('number')}: {issue.get('title')}",
        "",
        "Result: local candidate pass.",
        "",
        "What changed:",
        f"- Addressed target: {issue_current_meaning(issue)}",
        "- Closed this issue against the Project contract with an evidence packet, not only an eligibility flag.",
        f"- Observation boundary: `{boundary.get('can_claim') or packet.get('observation_class')}`.",
        "",
        "Acceptance evidence:",
    ]
    for row in acceptance[:8]:
        lines.append(f"- [{row.get('status')}] {row.get('gate')}")
    lines.extend(["", "Verification:"])
    for item in evidence_items:
        if not isinstance(item, dict) or item.get("type") != "verification":
            continue
        command = item.get("command") or "(command unavailable)"
        lines.append(f"- `{command}` -> {item.get('status')} ({item.get('summary')})")
    if not any(isinstance(item, dict) and item.get("type") == "verification" for item in evidence_items):
        lines.append("- No verification evidence captured.")
    lines.extend(
        [
            "",
            "Implementation refs:",
            f"- change_source: `{implementation.get('change_source') or 'unknown'}`",
            f"- changed_files: {changed_summary}",
            f"- commit: `{implementation.get('head_commit_short') or 'unknown'}`",
            f"- branch: `{implementation.get('branch') or 'unknown'}`",
            f"- push_status: `{implementation.get('push_status') or 'unknown'}`",
            f"- dirty_gate: `{(packet.get('dirty_gate') or {}).get('status')}`",
        ]
    )
    reviewer = packet.get("llm_reviewer")
    if reviewer:
        lines.extend(["", "Reviewer:", f"- llm_reviewer_verdict: `{reviewer.get('verdict')}`"])
    issue_specific = [
        item for item in evidence_items if isinstance(item, dict) and item.get("type") in {"issue_evidence", "implementation", "reviewer"}
    ]
    if issue_specific:
        lines.extend(["", "Evidence refs:"])
        for item in issue_specific[:6]:
            lines.append(f"- {item.get('source')}: {item.get('summary')}")
    lines.extend(["", "Residuals:"])
    for residual in residuals[:5]:
        lines.append(f"- {residual}")
    lines.extend(
        [
            "",
            "Claim ceiling:",
            f"`{claim}`",
            "",
            "Not claimed:",
            "full unattended autonomous development, stable productivity gain, product runtime efficacy, live autonomy, durable memory efficacy, or consciousness.",
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

    implementation_refs = collect_implementation_refs(runner) if verify and verify.get("passed") else {}
    evidence_packet = build_closeout_evidence_packet(
        issue=issue,
        observation_class=observation_class,
        verify=verify,
        implementation_refs=implementation_refs,
        reviewer=None,
        eligible=False,
    )
    if not blocked_reasons:
        blocked_reasons.extend(closeout_evidence_blockers(observation_class, evidence_packet))

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
            "current_meaning": issue_current_meaning(issue),
        },
        "project_item": classified.get("project_item"),
        "classification": classification,
        "observation_class": observation_class,
        "claim_ceiling": claim_ceiling,
        "dirty_gate": dirty,
        "verify": verify,
        "evidence_packet": evidence_packet,
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
        evidence_packet = build_closeout_evidence_packet(
            issue=issue,
            observation_class=observation_class,
            verify=verify,
            implementation_refs=implementation_refs,
            reviewer=reviewer,
            eligible=False,
        )
        packet["evidence_packet"] = evidence_packet
    elif not closeout_allowed and not needs_llm_review:
        blocked_reasons.append({"reason": "observation_class_not_closeout_allowed", "observation_class": observation_class})

    eligible = not blocked_reasons and (closeout_allowed or (needs_llm_review and reviewer and reviewer.get("verdict") == "closeout_allowed"))
    evidence_packet = build_closeout_evidence_packet(
        issue=issue,
        observation_class=observation_class,
        verify=verify,
        implementation_refs=implementation_refs,
        reviewer=reviewer,
        eligible=eligible,
    )
    packet["evidence_packet"] = evidence_packet
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


def build_operator_digest(payload: dict[str, Any]) -> dict[str, Any]:
    stop_reason = str(payload.get("stop_reason") or "")
    status = str(payload.get("status") or "unknown")
    mode = str(payload.get("mode") or "unknown")
    planned_entries = [entry for entry in (payload.get("planned") or []) if isinstance(entry, dict)]
    issue_summaries = []
    for entry in planned_entries:
        issue = entry.get("issue") if isinstance(entry.get("issue"), dict) else {}
        issue_summaries.append(
            {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "action": entry.get("dry_run_action")
                or ("closed" if entry.get("closeout") else None)
                or "inspected",
            }
        )

    needs_user: list[str] = []
    if stop_reason == "autopilot_pause_required":
        needs_user.append("Reframe the task or create a timeboxed operator cut before continuing.")
    elif stop_reason in {"dirty_worktree_unsafe", "dirty_scope_unsafe"}:
        needs_user.append("Resolve or baseline unsafe dirty worktree changes before continuing.")
    elif stop_reason == "no_ready_issue":
        needs_user.append("Create or normalize a ready issue with acceptance gate, rollback, and claim ceiling.")
    elif stop_reason == "l5_execute_not_implemented":
        needs_user.append("Use a human/Codex implementation rollout; this mode only emits eligibility packets.")
    elif status == "stopped" and stop_reason:
        needs_user.append(f"Inspect stop reason `{stop_reason}` before retrying.")

    if not needs_user and planned_entries:
        needs_user.append("No immediate user action required for this dry-run report.")
    if not needs_user:
        needs_user.append("No ready action was selected.")

    summary_bits = [f"Autopilot {mode} run {status}"]
    if stop_reason:
        summary_bits.append(f"stop_reason={stop_reason}")
    if issue_summaries:
        summary_bits.append(
            "issues="
            + ", ".join(
                f"#{item['number']}:{item['action']}" if item.get("number") else str(item.get("action"))
                for item in issue_summaries[:5]
            )
        )
    return {
        "summary": "; ".join(summary_bits),
        "issue_count": len(issue_summaries),
        "issues": issue_summaries,
        "needs_user": needs_user,
        "claim_ceiling": "operator digest only; not execution proof or product efficacy",
    }


def finalize_run_loop_payload(payload: dict[str, Any], *, write_report: bool, report_dir: Path) -> dict[str, Any]:
    payload["operator_digest"] = build_operator_digest(payload)
    if write_report:
        payload["report_path"] = write_run_report(payload, report_dir=report_dir)
    return payload


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


def candidate_issue_proposals_from_report(
    contract: ProjectContract,
    report: dict[str, Any],
    *,
    max_issues: int | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, int(max_issues or _goal_control_config(contract).get("candidate_issue_limit") or 3))
    proposals: list[dict[str, Any]] = []
    issue_priority = {
        "unknown": 0,
        "epic": 1,
        "aggregate": 2,
        "research": 3,
        "human_required": 4,
    }
    candidates = []
    for issue in report.get("issues") or []:
        cls = str((issue.get("classification") or {}).get("class") or "")
        if cls not in issue_priority:
            continue
        candidates.append((issue_priority[cls], int(issue.get("number") or 999999), issue))
    candidates.sort(key=lambda item: (item[0], item[1]))

    prefix = preferred_ready_prefix(contract)
    for _, _, source in candidates[:limit]:
        cls = str((source.get("classification") or {}).get("class") or "")
        number = source.get("number")
        title = str(source.get("title") or "untitled")
        if cls == "unknown":
            meaning = f"Normalize and scope #{number}: {title}"
            observation_class = "deterministic_local"
        elif cls == "epic":
            meaning = f"Create first executable slice from #{number}: {title}"
            observation_class = "deterministic_local"
        elif cls == "aggregate":
            meaning = f"Split one narrow ready repair from aggregate #{number}: {title}"
            observation_class = "deterministic_local"
        elif cls == "research":
            meaning = f"Turn research #{number} into a bounded inventory/report task: {title}"
            observation_class = "deterministic_local"
        else:
            meaning = f"Prepare human smoke packet for #{number}: {title}"
            observation_class = "human_required"
        proposals.append(
            {
                "source_issue": {
                    "number": number,
                    "title": title,
                    "classification": source.get("classification"),
                    "url": source.get("url"),
                },
                "title": compact_issue_title(prefix, meaning),
                "project_status": "Todo",
                "observation_class": observation_class,
                "acceptance_gate": "The issue body contains canonical source, current meaning, acceptance gate, rollback, and claim ceiling.",
                "rollback": "Close the candidate as superseded/not planned if the framing is wrong.",
                "claim_ceiling": "Candidate issue proposal only; not implementation proof or product efficacy.",
                "body": decomposition_issue_body(
                    canonical_source=f"Generated from Project issue #{number}: {source.get('url')}",
                    current_meaning=meaning,
                    observation_class=observation_class,
                ),
            }
        )

    if not proposals:
        meaning = "Create the next ready issue from the current Project goal/status gap"
        proposals.append(
            {
                "source_issue": None,
                "title": compact_issue_title(prefix, meaning),
                "project_status": "Todo",
                "observation_class": "deterministic_local",
                "acceptance_gate": "A scoped ready issue exists with canonical source, current meaning, acceptance gate, rollback, and claim ceiling.",
                "rollback": "Close as not planned if the Project already has a better ready issue.",
                "claim_ceiling": "Candidate issue proposal only; not implementation proof or product efficacy.",
                "body": decomposition_issue_body(
                    canonical_source="Generated from goal-aware Autopilot no-ready Project state",
                    current_meaning=meaning,
                    observation_class="deterministic_local",
                ),
            }
        )
    return proposals


def _proposal_required_field_errors(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = []
    required = ["title", "observation_class", "acceptance_gate", "rollback", "claim_ceiling"]
    for index, proposal in enumerate(proposals):
        for field_name in required:
            if not str(proposal.get(field_name) or "").strip():
                errors.append({"index": index, "reason": "missing_generated_issue_field", "field": field_name})
        body = str(proposal.get("body") or "")
        if body:
            for section in REQUIRED_DECOMPOSITION_SECTIONS:
                if section not in body:
                    errors.append({"index": index, "reason": "missing_generated_issue_body_section", "section": section})
    return errors


def command_propose_ready_issues(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    dry_run: bool,
    max_issues: int,
) -> dict[str, Any]:
    if not dry_run:
        raise AutopilotError("mutation_not_implemented", "v3 propose-ready-issues only supports --dry-run")
    report = build_report(client, contract)
    proposals = candidate_issue_proposals_from_report(contract, report, max_issues=max_issues)
    review = review_decomposition_proposals([{"title": item.get("title"), "body": item.get("body")} for item in proposals])
    field_errors = _proposal_required_field_errors(proposals)
    return {
        "status": "ok" if not field_errors and review.get("verdict") == "proposal_set_ready" else "blocked",
        "mode": "dry_run",
        "proposal_count": len(proposals),
        "proposals": proposals,
        "reviewer_check": review,
        "field_errors": field_errors,
        "claim_ceiling": _goal_control_config(contract).get("claim_ceiling"),
    }


def planner_hard_stop_reasons(contract: ProjectContract, planner_payload: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = _goal_control_config(contract)
    reasons = []
    protected_markers = [path.rstrip("/") for path in contract.protected_paths]

    def marker_is_negated(text: str, marker: str) -> bool:
        text_cf = text.casefold()
        marker_cf = marker.casefold()
        index = text_cf.find(marker_cf)
        if index < 0:
            return False
        context = text_cf[max(0, index - 160) : index + len(marker_cf) + 160]
        negators = [
            "do not",
            "don't",
            "without",
            "avoid",
            "avoiding",
            " no ",
            " not ",
            "cannot",
            "can't",
            "unless",
            "forbid",
            "forbidden",
            "discard",
            "untouched",
            "unchanged",
            "no issue",
            "stop condition",
            "non-goal",
            "not proof",
            "no proof",
            "不",
            "不得",
            "不能",
        ]
        return any(token in context for token in negators)

    def scan(value: Any, *, path: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                if key_text in {"stop_conditions", "non_goals"}:
                    continue
                scan(item, path=f"{path}.{key_text}" if path else key_text)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                scan(item, path=f"{path}[{index}]")
            return
        if not isinstance(value, str):
            return
        for marker in _as_list(cfg.get("hard_stop_markers")):
            if marker.casefold() in value.casefold() and not marker_is_negated(value, marker):
                reasons.append({"reason": "planner_hard_stop_marker", "marker": marker, "path": path})
        for protected in protected_markers:
            if protected.casefold() in value.casefold() and not marker_is_negated(value, protected):
                reasons.append({"reason": "planner_protected_path_marker", "path": protected, "field": path})

    scan(planner_payload)
    return reasons


def call_planner_backend(
    contract: ProjectContract,
    packet: dict[str, Any],
    *,
    runner: CommandRunner,
) -> dict[str, Any]:
    cfg = _goal_control_config(contract)
    backend = str(cfg.get("planning_backend") or "codex_exec")
    prompt = (
        "You are a conservative project-planning backend for Codex Autopilot.\n"
        "Return JSON only matching the provided schema. Generate proposals only; do not claim implementation evidence.\n"
        "Every candidate issue must include acceptance_gate, rollback, claim_ceiling, and observation_class.\n"
        "Do not propose changes to protected paths, program state, evidence ledger, permissions expansion, memory promotion, "
        "mainline/demotion, or Stage Card items as auto-executable work.\n\n"
        f"Packet:\n{json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2)}"
    )
    if backend == "native_goal":
        if not bool(cfg.get("native_goal_enabled")):
            return {
                "status": "planning_backend_unavailable",
                "backend": backend,
                "reason": "native_goal_backend_disabled_until_stable_api_exists",
            }
        return {
            "status": "planning_backend_unavailable",
            "backend": backend,
            "reason": "native_goal_backend_not_implemented",
        }
    if backend != "codex_exec":
        return {"status": "planning_backend_unavailable", "backend": backend, "reason": "unsupported_planning_backend"}

    result = runner.run(
        [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(DEFAULT_PLAN_SCHEMA_PATH),
            prompt,
        ]
    )
    if result.returncode != 0:
        return {
            "status": "planning_backend_unavailable",
            "backend": backend,
            "returncode": result.returncode,
            "stderr_preview": result.stderr[-1000:],
            "stdout_preview": result.stdout[-1000:],
        }
    parsed = _extract_json_object(result.stdout)
    if not parsed:
        return {
            "status": "planning_backend_unavailable",
            "backend": backend,
            "reason": "planner_invalid_json",
            "stdout_preview": result.stdout[-1000:],
        }
    parsed.setdefault("status", "ok")
    parsed["backend"] = backend
    return parsed


def _planner_candidate_issues(planner_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = planner_payload.get("candidate_issues")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def command_goal_refresh(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    issue_ref: str | None,
    report_dir: Path,
) -> dict[str, Any]:
    return goal_refresh_packet(client, contract, issue_ref=issue_ref, report_dir=report_dir)


def command_plan_proposal(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    issue_ref: str | None,
    board: bool,
    goal: str | None,
    goal_file: str | None,
    dry_run: bool,
    runner: CommandRunner,
    report_dir: Path,
) -> dict[str, Any]:
    if not dry_run:
        raise AutopilotError("mutation_not_implemented", "v3 plan-proposal only supports --dry-run")
    packet = goal_refresh_packet(client, contract, issue_ref=issue_ref, report_dir=report_dir)
    goal_text = read_goal_input(goal, goal_file)
    if goal_text:
        packet["explicit_goal"] = goal_text
    packet["scope"] = "board" if board or not issue_ref else "issue"
    deterministic_candidates = candidate_issue_proposals_from_report(
        contract,
        {"issues": packet.get("issues") or [], "counts": packet.get("board_counts") or {}},
        max_issues=int(_goal_control_config(contract).get("candidate_issue_limit") or 3),
    )
    planner_payload = call_planner_backend(contract, packet, runner=runner)
    blocked_reasons = []
    if planner_payload.get("status") == "planning_backend_unavailable":
        return {
            "status": "planning_backend_unavailable",
            "mode": "dry_run",
            "planner": planner_payload,
            "fallback_candidate_issues": deterministic_candidates,
            "claim_ceiling": _goal_control_config(contract).get("claim_ceiling"),
        }
    blocked_reasons.extend(planner_hard_stop_reasons(contract, planner_payload))
    field_errors = _proposal_required_field_errors(_planner_candidate_issues(planner_payload))
    blocked_reasons.extend(field_errors)
    return {
        "status": "blocked" if blocked_reasons else "ok",
        "mode": "dry_run",
        "planner": planner_payload,
        "candidate_issues": _planner_candidate_issues(planner_payload),
        "fallback_candidate_issues": deterministic_candidates if not _planner_candidate_issues(planner_payload) else [],
        "blocked_reasons": blocked_reasons,
        "claim_ceiling": _goal_control_config(contract).get("claim_ceiling"),
    }


def _epic_rollup_config(contract: ProjectContract) -> dict[str, Any]:
    cfg = dict(contract.epic_rollup)
    cfg.setdefault("parent_marker", "Parent epic")
    cfg.setdefault("child_title_prefixes", ["EgoRoadmap:", "Research:"])
    cfg.setdefault("closeout_claim_ceiling", "Codex autopilot epic rollup and real-task execution local workflow candidate pass")
    cfg.setdefault("block_child_classes", ["human_required", "high_impact", "blocked", "unknown"])
    return cfg


def parent_epic_marker(body: str, *, marker: str) -> dict[str, Any]:
    pattern = re.compile(rf"^\s*{re.escape(marker)}\s*:\s*#?(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
    parents = sorted({int(match.group(1)) for match in pattern.finditer(body or "")})
    if not parents:
        return {"status": "missing", "parent": None, "parents": []}
    if len(parents) > 1:
        return {"status": "conflict", "parent": None, "parents": parents}
    return {"status": "ok", "parent": parents[0], "parents": parents}


def append_parent_epic_marker(body: str, *, marker: str, epic_number: int) -> tuple[str, dict[str, Any]]:
    parsed = parent_epic_marker(body, marker=marker)
    if parsed["status"] == "conflict":
        return body, parsed
    if parsed["status"] == "ok":
        if parsed["parent"] == epic_number:
            return body, {"status": "unchanged", "parent": epic_number}
        return body, {"status": "conflict", "parent": parsed["parent"], "expected_parent": epic_number}
    suffix = f"{marker}: #{epic_number}"
    clean = (body or "").rstrip()
    updated = f"{clean}\n\n{suffix}\n" if clean else f"{suffix}\n"
    return updated, {"status": "appended", "parent": epic_number}


def _is_epic_issue(contract: ProjectContract, issue: dict[str, Any]) -> bool:
    title = str(issue.get("title") or "").casefold()
    return _starts_with_any(title, _as_list(contract.task_classification.get("epic_title_prefixes")))


def _is_epic_child_issue(contract: ProjectContract, issue: dict[str, Any]) -> bool:
    title = str(issue.get("title") or "").casefold()
    prefixes = _as_list(_epic_rollup_config(contract).get("child_title_prefixes"))
    return _starts_with_any(title, prefixes)


def project_issue_records(client: github_project_task.GhClient, contract: ProjectContract) -> list[dict[str, Any]]:
    cfg = contract.github_config()
    records = []
    for item in load_items(client, cfg):
        issue = dict(item_issue(item))
        if issue.get("type") and issue.get("type") != "Issue":
            continue
        issue_ref = issue.get("number") or issue.get("url")
        if issue_ref is not None and "body" not in issue:
            full = issue_view_full(client, cfg, str(issue_ref))
            issue.update(full)
        classification = classify_issue(contract, issue, item)
        records.append(
            {
                "item": item,
                "issue": issue,
                "classification": classification,
                "project_status": item.get("status"),
            }
        )
    return records


def build_epic_rollups(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    cfg = _epic_rollup_config(contract)
    marker = str(cfg.get("parent_marker") or "Parent epic")
    records = project_issue_records(client, contract)
    epics: dict[int, dict[str, Any]] = {}
    current_epic: int | None = None
    assignments: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for record in records:
        issue = record["issue"]
        number = issue.get("number")
        if number is None:
            continue
        number = int(number)
        if _is_epic_issue(contract, issue):
            current_epic = number
            epics[number] = {
                "number": number,
                "title": issue.get("title"),
                "url": issue.get("url"),
                "state": issue.get("state"),
                "project_status": record.get("project_status"),
                "classification": record.get("classification"),
                "children": [],
                "child_counts": {},
                "human_blockers": [],
                "open_blockers": [],
            }
            continue
        if not _is_epic_child_issue(contract, issue):
            continue
        parsed = parent_epic_marker(str(issue.get("body") or ""), marker=marker)
        inferred = current_epic
        parent = parsed.get("parent")
        source = "explicit" if parent else "inferred"
        if parsed["status"] == "conflict":
            conflicts.append({"issue": number, "title": issue.get("title"), "reason": "conflicting_parent_markers", "parents": parsed["parents"]})
            continue
        if parent and inferred and parent != inferred:
            conflicts.append(
                {
                    "issue": number,
                    "title": issue.get("title"),
                    "reason": "parent_marker_disagrees_with_project_order",
                    "parent": parent,
                    "inferred_parent": inferred,
                }
            )
        if parent is None:
            parent = inferred
        if parent is None:
            conflicts.append({"issue": number, "title": issue.get("title"), "reason": "no_parent_epic_available"})
            continue
        child = {
            "number": number,
            "title": issue.get("title"),
            "url": issue.get("url"),
            "state": issue.get("state"),
            "project_status": record.get("project_status"),
            "classification": record.get("classification"),
            "parent_epic": parent,
            "parent_source": source,
            "parent_marker": parsed,
        }
        assignments.append(child)
        if parent in epics:
            epics[parent]["children"].append(child)
        else:
            conflicts.append({"issue": number, "title": issue.get("title"), "reason": "parent_epic_not_on_board", "parent": parent})

    block_classes = set(_as_list(cfg.get("block_child_classes")))
    for epic in epics.values():
        counts: dict[str, int] = {}
        for child in epic["children"]:
            cls = str((child.get("classification") or {}).get("class") or "unknown")
            counts[cls] = counts.get(cls, 0) + 1
            if cls == "human_required":
                epic["human_blockers"].append(child)
            elif cls != "done":
                epic["open_blockers"].append(child)
        epic["child_counts"] = counts
        if not epic["children"]:
            rollup_state = "needs_child_issue"
        elif epic["human_blockers"]:
            rollup_state = "blocked_by_human"
        elif any(str((child.get("classification") or {}).get("class")) in block_classes for child in epic["children"] if str((child.get("classification") or {}).get("class")) != "done"):
            rollup_state = "blocked_by_child"
        elif epic["open_blockers"]:
            rollup_state = "has_open_children"
        else:
            rollup_state = "complete"
        already_closed = str(epic.get("state") or "").upper() == "CLOSED" or epic.get("project_status") == "Done"
        epic["rollup_state"] = "already_done" if already_closed and rollup_state == "complete" else rollup_state
        epic["eligible_closeout"] = rollup_state == "complete" and not already_closed

    summary_counts: dict[str, int] = {}
    for epic in epics.values():
        state = str(epic["rollup_state"])
        summary_counts[state] = summary_counts.get(state, 0) + 1
    return {
        "status": "ok",
        "parent_marker": marker,
        "epics": list(epics.values()),
        "assignments": assignments,
        "conflicts": conflicts,
        "summary": {
            "epic_count": len(epics),
            "assignment_count": len(assignments),
            "conflict_count": len(conflicts),
            "rollup_states": summary_counts,
            "eligible_closeout_epics": [epic["number"] for epic in epics.values() if epic.get("eligible_closeout")],
        },
        "claim_ceiling": cfg.get("closeout_claim_ceiling"),
    }


def command_epic_report(client: github_project_task.GhClient, contract: ProjectContract) -> dict[str, Any]:
    return build_epic_rollups(client, contract)


def command_normalize_parent_links(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    cfg = contract.github_config()
    marker = str(_epic_rollup_config(contract).get("parent_marker") or "Parent epic")
    records = project_issue_records(client, contract)
    current_epic: int | None = None
    planned = []
    blocked = []

    for record in records:
        issue = record["issue"]
        number = issue.get("number")
        if number is None:
            continue
        number = int(number)
        if _is_epic_issue(contract, issue):
            current_epic = number
            continue
        if not _is_epic_child_issue(contract, issue):
            continue
        if current_epic is None:
            blocked.append({"issue": number, "reason": "no_inferred_parent_epic", "title": issue.get("title")})
            continue
        body = str(issue.get("body") or "")
        updated, result = append_parent_epic_marker(body, marker=marker, epic_number=current_epic)
        if result["status"] == "conflict":
            blocked.append({"issue": number, "reason": "parent_marker_conflict", "title": issue.get("title"), "details": result})
            continue
        action = "append_parent_marker" if result["status"] == "appended" else "noop"
        planned.append(
            {
                "issue": number,
                "title": issue.get("title"),
                "parent_epic": current_epic,
                "action": action,
                "old_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "new_body_sha256": hashlib.sha256(updated.encode("utf-8")).hexdigest(),
                "body": updated if action == "append_parent_marker" else None,
            }
        )

    if blocked:
        return {"status": "blocked", "mode": "dry_run" if dry_run else "execute", "blocked": blocked, "planned": planned}

    edited = []
    if not dry_run:
        for item in planned:
            if item["action"] != "append_parent_marker":
                continue
            client.run(["issue", "edit", str(item["issue"]), "--repo", cfg.repo, "--body", str(item["body"])])
            edited.append({"issue": item["issue"], "parent_epic": item["parent_epic"]})
    redacted = [{key: value for key, value in item.items() if key != "body"} for item in planned]
    return {
        "status": "ok",
        "mode": "dry_run" if dry_run else "execute",
        "planned": redacted,
        "edited": edited,
        "edited_count": len(edited),
        "claim_ceiling": _epic_rollup_config(contract).get("closeout_claim_ceiling"),
    }


def epic_by_number(report: dict[str, Any], epic_number: int) -> dict[str, Any] | None:
    for epic in report.get("epics") or []:
        if int(epic.get("number") or -1) == epic_number:
            return epic
    return None


def epic_closeout_comment(epic: dict[str, Any], contract: ProjectContract) -> str:
    children = epic.get("children") or []
    lines = [
        f"Closeout for Epic #{epic.get('number')}: {epic.get('title')}",
        "",
        "Result: epic rollup complete.",
        "",
        "Rollup evidence:",
    ]
    for child in children:
        lines.append(f"- [done] #{child.get('number')} {child.get('title')}")
    lines.extend(
        [
            "",
            "Verification:",
            "- `epic-report` / `epic-closeout-check` confirmed all child issues are Done and no human-required child blocks this epic.",
            "",
            "Claim ceiling:",
            f"`{_epic_rollup_config(contract).get('closeout_claim_ceiling')}`",
            "",
            "Not claimed:",
            "full unattended autonomous development, stable productivity gain, runtime efficacy, live autonomy, durable memory efficacy, or consciousness.",
        ]
    )
    return "\n".join(lines)


def command_epic_closeout_check(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    epic_ref: str,
) -> dict[str, Any]:
    try:
        epic_number = int(str(epic_ref).lstrip("#"))
    except ValueError:
        raise AutopilotError("invalid_epic_ref", f"Epic ref must be an issue number: {epic_ref}")
    report = build_epic_rollups(client, contract)
    epic = epic_by_number(report, epic_number)
    if not epic:
        return {"status": "blocked", "eligible": False, "blocked_reasons": [{"reason": "epic_not_found", "epic": epic_number}], "report": report}
    blocked_reasons = []
    if epic.get("rollup_state") != "complete":
        blocked_reasons.append({"reason": "epic_rollup_not_complete", "rollup_state": epic.get("rollup_state")})
    if report.get("conflicts"):
        blocked_reasons.append({"reason": "epic_parent_conflicts_present", "conflict_count": len(report.get("conflicts") or [])})
    eligible = not blocked_reasons
    return {
        "status": "eligible" if eligible else "blocked",
        "eligible": eligible,
        "epic": epic,
        "blocked_reasons": blocked_reasons,
        "closeout_comment": epic_closeout_comment(epic, contract) if eligible else None,
        "claim_ceiling": _epic_rollup_config(contract).get("closeout_claim_ceiling"),
    }


def command_epic_closeout_once(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    epic_ref: str,
    *,
    dry_run: bool,
    execute: bool,
) -> dict[str, Any]:
    if dry_run and execute:
        raise AutopilotError("invalid_epic_closeout_mode", "Choose either --dry-run or --execute, not both")
    packet = command_epic_closeout_check(client, contract, epic_ref)
    if not packet.get("eligible"):
        return {"status": "stopped", "stop_reason": "epic_closeout_not_eligible", "packet": packet}
    effective_dry_run = not execute
    cfg = contract.github_config(dry_run=effective_dry_run)
    status = str(contract.auto_closeout.get("done_status") or "Done")
    result = github_project_task.command_closeout(
        client,
        cfg,
        argparse.Namespace(issue=str(packet["epic"]["number"]), status=status, comment=str(packet["closeout_comment"]), comment_file=None),
    )
    return {
        "status": "ok",
        "mode": "dry_run" if effective_dry_run else "execute",
        "packet": packet,
        "closeout": result,
    }


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
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

    pause = pause_gate(contract, report_dir=report_dir)
    if pause.get("pause_required"):
        payload = {
            "status": "stopped",
            "stop_reason": "autopilot_pause_required",
            "pause_gate": pause,
            "planned": [],
        }
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

    gate = dirty_gate(contract, runner, baseline_path)
    if gate["status"] != "ok":
        payload = {
            "status": "stopped",
            "stop_reason": gate["stop_reason"],
            "dirty_gate": gate,
            "planned": [],
        }
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

    report = build_report(client, contract)
    ready = [
        issue
        for issue in report.get("issues", [])
        if issue.get("classification", {}).get("autopilot_allowed") is True
    ]
    if not ready:
        epic_rollup = build_epic_rollups(client, contract)
        closeout_epics = epic_rollup.get("summary", {}).get("eligible_closeout_epics") or []
        if closeout_epics:
            epic_ref = str(closeout_epics[0])
            if execute:
                closeout = command_epic_closeout_once(
                    client,
                    contract,
                    epic_ref,
                    dry_run=False,
                    execute=True,
                )
                payload = {
                    "status": "ok",
                    "mode": "plan",
                    "dry_run": False,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "planned": [{"epic": epic_ref, "closeout": closeout}],
                    "stop_reason": "epic_closeout_executed",
                }
                return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)
            payload = {
                "status": "stopped",
                "stop_reason": "no_ready_issue_epic_closeout_available",
                "counts": report["counts"],
                "epic_rollup": {
                    "summary": epic_rollup.get("summary"),
                    "next_epic": closeout_epics[0],
                    "dry_run_action": "would_close_epic",
                },
                "planned": [],
            }
            return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)
        proposals = candidate_issue_proposals_from_report(
            contract,
            report,
            max_issues=min(max_issues or 1, int(_goal_control_config(contract).get("candidate_issue_limit") or 3)),
        )
        payload = {
            "status": "stopped",
            "stop_reason": "no_ready_issue",
            "counts": report["counts"],
            "epic_rollup": {
                "summary": epic_rollup.get("summary"),
                "human_blocked_epics": [
                    epic.get("number")
                    for epic in epic_rollup.get("epics") or []
                    if epic.get("rollup_state") == "blocked_by_human"
                ],
                "needs_child_issue_epics": [
                    epic.get("number")
                    for epic in epic_rollup.get("epics") or []
                    if epic.get("rollup_state") == "needs_child_issue"
                ],
            },
            "plan_stage": {
                "status": "candidate_issues_proposed",
                "note": "No ready issue was available; goal-aware mode generated dry-run candidate issue drafts instead of looping.",
                "candidate_issues": proposals,
            },
            "planned": [],
        }
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

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
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

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
            return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)
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
        return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)

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
    return finalize_run_loop_payload(payload, write_report=write_report, report_dir=report_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-project Codex autopilot helpers")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH), help="Path to project contract YAML")
    parser.add_argument("--baseline-path", default=str(DEFAULT_BASELINE_PATH), help="Path to local dirty baseline JSON")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Path to local autopilot run reports")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("report")
    subparsers.add_parser("plan-next")
    subparsers.add_parser("goal-status")
    goal_refresh = subparsers.add_parser("goal-refresh")
    goal_refresh.add_argument("--issue")

    plan_proposal = subparsers.add_parser("plan-proposal")
    plan_proposal.add_argument("--issue")
    plan_proposal.add_argument("--board", action="store_true")
    plan_proposal.add_argument("--goal")
    plan_proposal.add_argument("--goal-file")
    plan_proposal.add_argument("--dry-run", action="store_true")

    propose_ready = subparsers.add_parser("propose-ready-issues")
    propose_ready.add_argument("--dry-run", action="store_true")
    propose_ready.add_argument("--max-issues", type=int, default=3)

    subparsers.add_parser("baseline")
    subparsers.add_parser("diff-scope")
    subparsers.add_parser("pause-check")
    subparsers.add_parser("epic-report")

    normalize_parents = subparsers.add_parser("normalize-parent-links")
    normalize_parents.add_argument("--dry-run", action="store_true")
    normalize_parents.add_argument("--execute", action="store_true")

    epic_check = subparsers.add_parser("epic-closeout-check")
    epic_check.add_argument("--epic", required=True)

    epic_once = subparsers.add_parser("epic-closeout-once")
    epic_once.add_argument("--epic", required=True)
    epic_once.add_argument("--dry-run", action="store_true")
    epic_once.add_argument("--execute", action="store_true")

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
    if args.command == "goal-status":
        return command_goal_status(client, contract, report_dir=Path(args.report_dir))
    if args.command == "goal-refresh":
        return command_goal_refresh(client, contract, issue_ref=args.issue, report_dir=Path(args.report_dir))
    if args.command == "plan-proposal":
        return command_plan_proposal(
            client,
            contract,
            issue_ref=args.issue,
            board=bool(args.board),
            goal=args.goal,
            goal_file=args.goal_file,
            dry_run=bool(args.dry_run),
            runner=runner,
            report_dir=Path(args.report_dir),
        )
    if args.command == "propose-ready-issues":
        return command_propose_ready_issues(
            client,
            contract,
            dry_run=bool(args.dry_run),
            max_issues=args.max_issues,
        )
    if args.command == "classify-issue":
        return command_classify_issue(client, contract, args.issue)
    if args.command == "baseline":
        return command_baseline(contract, baseline_path=Path(args.baseline_path), runner=runner)
    if args.command == "diff-scope":
        return command_diff_scope(contract, baseline_path=Path(args.baseline_path), runner=runner)
    if args.command == "pause-check":
        return command_pause_check(contract, report_dir=Path(args.report_dir))
    if args.command == "epic-report":
        return command_epic_report(client, contract)
    if args.command == "normalize-parent-links":
        if bool(args.dry_run) and bool(args.execute):
            raise AutopilotError("invalid_parent_link_mode", "Choose either --dry-run or --execute, not both")
        return command_normalize_parent_links(client, contract, dry_run=not bool(args.execute))
    if args.command == "epic-closeout-check":
        return command_epic_closeout_check(client, contract, args.epic)
    if args.command == "epic-closeout-once":
        return command_epic_closeout_once(
            client,
            contract,
            args.epic,
            dry_run=bool(args.dry_run),
            execute=bool(args.execute),
        )
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
