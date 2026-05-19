#!/usr/bin/env python3
"""Cross-project Codex task-board autopilot L0/L1 helpers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT_PATH = ROOT / ".codex" / "project_contract.yaml"

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
    def run(self, args: list[str]) -> CommandResult:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


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

    if _contains_any(haystack, _as_list(rules.get("aggregate_title_contains"))):
        return {"class": "aggregate", "reason": "aggregate_or_backlog_marker", "autopilot_allowed": False}

    if _contains_any(haystack, _as_list(rules.get("human_required_title_contains"))):
        return {"class": "human_required", "reason": "human_observation_marker", "autopilot_allowed": False}

    if _contains_any(haystack, _as_list(rules.get("high_impact_title_contains"))):
        return {"class": "high_impact", "reason": "high_impact_marker", "autopilot_allowed": False}

    ready_statuses = set(_as_list(rules.get("ready_project_statuses")) or ["In Progress", "Todo"])
    ready_prefix = _starts_with_any(title_cf, _as_list(rules.get("ready_title_prefixes")))
    markers = [marker.casefold() for marker in _as_list(rules.get("ready_body_markers"))]
    marker_hits = [marker for marker in markers if marker in haystack]

    if status and status not in ready_statuses:
        return {"class": "blocked", "reason": "project_status_not_ready", "autopilot_allowed": False, "project_status": status}

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
        if issue.get("classification", {}).get("class") == "ready"
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
    }


def worktree_dirty_summary(contract: ProjectContract, runner: CommandRunner) -> dict[str, Any]:
    result = runner.run(["git", "status", "--short"])
    if result.returncode != 0:
        raise AutopilotError(
            "git_status_failed",
            "Unable to inspect git status",
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    allowed = [path.rstrip("/") for path in contract.allowed_mutation_paths]
    unsafe = []
    for line in lines:
        path = line[3:] if len(line) > 3 else line
        path = path.strip().strip('"')
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in allowed):
            unsafe.append(line)

    return {
        "total_dirty": len(lines),
        "unsafe_dirty": len(unsafe),
        "unsafe_sample": unsafe[:20],
    }


def command_run_loop(
    client: github_project_task.GhClient,
    contract: ProjectContract,
    *,
    dry_run: bool,
    max_issues: int,
    max_minutes: int,
    runner: CommandRunner,
) -> dict[str, Any]:
    if not dry_run:
        raise AutopilotError("mutation_not_implemented", "v1 run-loop only supports --dry-run")
    started = time.monotonic()
    if max_issues <= 0 or max_minutes <= 0:
        return {
            "status": "stopped",
            "stop_reason": "budget_exhausted",
            "max_issues": max_issues,
            "max_minutes": max_minutes,
            "planned": [],
        }

    dirty = worktree_dirty_summary(contract, runner)
    if dirty["unsafe_dirty"]:
        return {
            "status": "stopped",
            "stop_reason": "dirty_worktree_unsafe",
            "dirty": dirty,
            "planned": [],
        }

    report = build_report(client, contract)
    ready = [
        issue
        for issue in report.get("issues", [])
        if issue.get("classification", {}).get("class") == "ready"
    ]
    if not ready:
        return {
            "status": "stopped",
            "stop_reason": "no_ready_issue",
            "counts": report["counts"],
            "planned": [],
        }

    status_rank = {"In Progress": 0, "Todo": 1}
    ready.sort(key=lambda item: (status_rank.get(str(item.get("project_status")), 99), int(item.get("number") or 999999)))
    planned = [
        {
            "issue": item,
            "dry_run_action": "would_run_once",
            "note": "v1 does not mutate code, GitHub Project state, commits, or close issues",
        }
        for item in ready[:max_issues]
    ]
    return {
        "status": "ok",
        "mode": "dry_run",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "planned": planned,
        "stop_reason": "max_issues_reached" if len(ready) > max_issues else "ready_queue_exhausted",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-project Codex autopilot L0/L1 helpers")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH), help="Path to project contract YAML")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("report")
    subparsers.add_parser("plan-next")

    classify = subparsers.add_parser("classify-issue")
    classify.add_argument("--issue", required=True)

    loop = subparsers.add_parser("run-loop")
    loop.add_argument("--dry-run", action="store_true")
    loop.add_argument("--max-issues", type=int, default=1)
    loop.add_argument("--max-minutes", type=int, default=10)
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
    if args.command == "run-loop":
        return command_run_loop(
            client,
            contract,
            dry_run=bool(args.dry_run),
            max_issues=args.max_issues,
            max_minutes=args.max_minutes,
            runner=runner,
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
