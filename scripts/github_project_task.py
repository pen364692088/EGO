#!/usr/bin/env python3
"""Thin GitHub Issue + Project v2 task wrapper for Codex operators."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, TextIO


DEFAULT_REPO = "pen364692088/EGO"
DEFAULT_OWNER = "pen364692088"
DEFAULT_PROJECT_NUMBER = "1"
DEFAULT_STATUS_FIELD = "Status"

STATUS_ALIASES = {
    "todo": "Todo",
    "pending": "Todo",
    "progress": "In Progress",
    "in_progress": "In Progress",
    "in-progress": "In Progress",
    "done": "Done",
}


class UserError(Exception):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class GhCommandError(Exception):
    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str) -> None:
        super().__init__(stderr.strip() or stdout.strip() or f"gh exited {returncode}")
        self.args_list = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class Config:
    repo: str
    owner: str
    project_number: str
    status_field: str
    dry_run: bool = False


class GhClient:
    def run(self, args: list[str]) -> str:
        completed = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GhCommandError(args, completed.returncode, completed.stdout, completed.stderr)
        return completed.stdout


def _json_loads(text: str, *, command: str) -> dict[str, Any]:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise UserError(
            "invalid_gh_json",
            f"gh {command} did not return valid JSON",
            raw=text,
        ) from exc
    if not isinstance(payload, dict):
        raise UserError("invalid_gh_json", f"gh {command} returned non-object JSON", raw=text)
    return payload


def gh_json(client: GhClient, args: list[str]) -> dict[str, Any]:
    return _json_loads(client.run(args), command=" ".join(args[:2]))


def normalize_status(raw: str, options: list[dict[str, Any]]) -> tuple[str, str]:
    names = {str(option.get("name", "")): str(option.get("id", "")) for option in options}
    if raw in names:
        return raw, names[raw]

    normalized_names = {name.casefold(): name for name in names}
    alias_key = raw.strip().replace(" ", "_").casefold()
    canonical = STATUS_ALIASES.get(alias_key)
    if canonical and canonical in names:
        return canonical, names[canonical]

    casefold_name = raw.strip().casefold()
    if casefold_name in normalized_names:
        canonical = normalized_names[casefold_name]
        return canonical, names[canonical]

    raise UserError(
        "unknown_status",
        f"Unknown status: {raw}",
        available_statuses=sorted(names),
    )


def project_view(client: GhClient, cfg: Config) -> dict[str, Any]:
    return gh_json(
        client,
        ["project", "view", cfg.project_number, "--owner", cfg.owner, "--format", "json"],
    )


def field_list(client: GhClient, cfg: Config) -> list[dict[str, Any]]:
    payload = gh_json(
        client,
        ["project", "field-list", cfg.project_number, "--owner", cfg.owner, "--format", "json"],
    )
    fields = payload.get("fields")
    if not isinstance(fields, list):
        raise UserError("missing_project_fields", "Project field-list response has no fields array")
    return fields


def status_field(client: GhClient, cfg: Config) -> dict[str, Any]:
    for field in field_list(client, cfg):
        if field.get("name") == cfg.status_field:
            options = field.get("options")
            if not isinstance(options, list):
                raise UserError(
                    "status_field_not_single_select",
                    f"Project field {cfg.status_field!r} has no single-select options",
                )
            return field
    raise UserError("status_field_not_found", f"Project field not found: {cfg.status_field}")


def issue_view(client: GhClient, cfg: Config, issue: str) -> dict[str, Any]:
    return gh_json(
        client,
        [
            "issue",
            "view",
            issue,
            "--repo",
            cfg.repo,
            "--json",
            "number,title,state,url",
        ],
    )


def project_items(client: GhClient, cfg: Config, *, limit: int = 200) -> list[dict[str, Any]]:
    payload = gh_json(
        client,
        [
            "project",
            "item-list",
            cfg.project_number,
            "--owner",
            cfg.owner,
            "--limit",
            str(limit),
            "--format",
            "json",
        ],
    )
    items = payload.get("items")
    if not isinstance(items, list):
        raise UserError("missing_project_items", "Project item-list response has no items array")
    return items


def find_project_item(items: list[dict[str, Any]], issue: dict[str, Any]) -> dict[str, Any] | None:
    issue_url = issue.get("url")
    issue_number = issue.get("number")
    for item in items:
        content = item.get("content")
        if not isinstance(content, dict):
            continue
        if issue_url and content.get("url") == issue_url:
            return item
        if issue_number and content.get("number") == issue_number and content.get("type") == "Issue":
            return item
    return None


def ensure_project_item(client: GhClient, cfg: Config, issue: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    found = find_project_item(project_items(client, cfg), issue)
    if found:
        return found, False

    if cfg.dry_run:
        return {
            "id": "<dry-run-item-id>",
            "status": None,
            "content": issue,
            "dry_run": True,
        }, True

    client.run(
        [
            "project",
            "item-add",
            cfg.project_number,
            "--owner",
            cfg.owner,
            "--url",
            str(issue["url"]),
        ]
    )
    found = find_project_item(project_items(client, cfg), issue)
    if not found:
        raise UserError(
            "project_item_not_found_after_add",
            "Issue was added to project but could not be found in item-list",
            issue=issue,
        )
    return found, True


def set_project_status(
    client: GhClient,
    cfg: Config,
    *,
    item: dict[str, Any],
    status_name: str,
    status_option_id: str,
    project_id: str,
    field_id: str,
) -> dict[str, Any]:
    current = item.get("status")
    if current == status_name:
        return {"changed": False, "observed_status": current}

    if cfg.dry_run:
        return {
            "changed": True,
            "dry_run": True,
            "planned_status": status_name,
            "observed_status": current,
        }

    client.run(
        [
            "project",
            "item-edit",
            "--id",
            str(item["id"]),
            "--project-id",
            project_id,
            "--field-id",
            field_id,
            "--single-select-option-id",
            status_option_id,
        ]
    )
    return {"changed": True, "observed_status": current}


def command_doctor(client: GhClient, cfg: Config, _args: argparse.Namespace) -> dict[str, Any]:
    gh_path = shutil.which("gh")
    if not gh_path:
        raise UserError("gh_not_found", "gh is not available on PATH")

    version = client.run(["--version"]).splitlines()[0]
    auth = client.run(["auth", "status"])
    if "Logged in to github.com account" not in auth:
        raise UserError("gh_not_logged_in", "gh auth status did not report an active login")
    if "project" not in auth:
        raise UserError("missing_project_scope", "gh token is missing project scope")

    project = project_view(client, cfg)
    field = status_field(client, cfg)
    return {
        "status": "ok",
        "gh_path": gh_path,
        "gh_version": version,
        "repo": cfg.repo,
        "project": {
            "id": project.get("id"),
            "number": project.get("number"),
            "owner": cfg.owner,
            "title": project.get("title"),
            "url": project.get("url"),
        },
        "status_field": {
            "id": field.get("id"),
            "name": field.get("name"),
            "options": [option.get("name") for option in field.get("options", [])],
        },
    }


def command_verify(client: GhClient, cfg: Config, args: argparse.Namespace) -> dict[str, Any]:
    issue = issue_view(client, cfg, args.issue)
    item = find_project_item(project_items(client, cfg), issue)
    if not item:
        raise UserError("project_item_not_found", "Issue is not in the configured project", issue=issue)

    observed = item.get("status")
    if args.expect_status:
        field = status_field(client, cfg)
        expected, _ = normalize_status(args.expect_status, field["options"])
        if observed != expected:
            raise UserError(
                "status_mismatch",
                f"Expected status {expected!r}, observed {observed!r}",
                expected_status=expected,
                observed_status=observed,
                issue=issue,
                item_id=item.get("id"),
            )

    return {
        "status": "ok",
        "issue": issue,
        "project_item": {
            "id": item.get("id"),
            "status": observed,
            "title": item.get("title"),
        },
    }


def command_add(client: GhClient, cfg: Config, args: argparse.Namespace) -> dict[str, Any]:
    issue = issue_view(client, cfg, args.issue)
    item, added = ensure_project_item(client, cfg, issue)
    status_result: dict[str, Any] | None = None

    if args.status:
        project = project_view(client, cfg)
        field = status_field(client, cfg)
        status_name, option_id = normalize_status(args.status, field["options"])
        status_result = set_project_status(
            client,
            cfg,
            item=item,
            status_name=status_name,
            status_option_id=option_id,
            project_id=str(project["id"]),
            field_id=str(field["id"]),
        )
        if not cfg.dry_run:
            item = find_project_item(project_items(client, cfg), issue) or item

    return {
        "status": "dry_run" if cfg.dry_run else "ok",
        "issue": issue,
        "project_item": {
            "id": item.get("id"),
            "status": item.get("status"),
            "added": added,
        },
        "status_update": status_result,
    }


def command_set_status(client: GhClient, cfg: Config, args: argparse.Namespace) -> dict[str, Any]:
    issue = issue_view(client, cfg, args.issue)
    project = project_view(client, cfg)
    field = status_field(client, cfg)
    status_name, option_id = normalize_status(args.status, field["options"])
    item, added = ensure_project_item(client, cfg, issue)

    status_result = set_project_status(
        client,
        cfg,
        item=item,
        status_name=status_name,
        status_option_id=option_id,
        project_id=str(project["id"]),
        field_id=str(field["id"]),
    )
    if not cfg.dry_run:
        item = find_project_item(project_items(client, cfg), issue) or item
        observed = item.get("status")
        if observed != status_name:
            raise UserError(
                "status_write_not_observed",
                f"Status write did not read back as {status_name!r}",
                expected_status=status_name,
                observed_status=observed,
            )

    return {
        "status": "dry_run" if cfg.dry_run else "ok",
        "issue": issue,
        "project_item": {
            "id": item.get("id"),
            "status": item.get("status") if not cfg.dry_run else status_name,
            "added": added,
        },
        "status_update": status_result,
    }


def command_create(client: GhClient, cfg: Config, args: argparse.Namespace) -> dict[str, Any]:
    if cfg.dry_run:
        return {
            "status": "dry_run",
            "planned": [
                {"gh": ["issue", "create", "--repo", cfg.repo, "--title", args.title, "--body", args.body]},
                {"gh": ["project", "item-add", cfg.project_number, "--owner", cfg.owner, "--url", "<issue-url>"]},
                *(
                    [
                        {
                            "gh": [
                                "project",
                                "item-edit",
                                "--id",
                                "<project-item-id>",
                                "--project-id",
                                "<project-id>",
                                "--field-id",
                                "<status-field-id>",
                                "--single-select-option-id",
                                "<status-option-id>",
                            ],
                            "status": args.status,
                        }
                    ]
                    if args.status
                    else []
                ),
            ],
        }

    create_output = client.run(
        ["issue", "create", "--repo", cfg.repo, "--title", args.title, "--body", args.body]
    )
    issue_url = next(
        (line.strip() for line in reversed(create_output.splitlines()) if line.strip().startswith("http")),
        None,
    )
    if not issue_url:
        raise UserError("issue_create_url_not_found", "gh issue create did not return an issue URL", raw=create_output)
    add_args = argparse.Namespace(issue=issue_url, status=args.status)
    result = command_add(client, cfg, add_args)
    result["created"] = True
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage GitHub issues as Project v2 task items.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo, default: {DEFAULT_REPO}")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help=f"Project owner, default: {DEFAULT_OWNER}")
    parser.add_argument(
        "--project-number",
        default=DEFAULT_PROJECT_NUMBER,
        help=f"Project number, default: {DEFAULT_PROJECT_NUMBER}",
    )
    parser.add_argument(
        "--status-field",
        default=DEFAULT_STATUS_FIELD,
        help=f"Project status field name, default: {DEFAULT_STATUS_FIELD}",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan mutations without writing GitHub state")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Check gh auth and Project v2 access")

    create = subparsers.add_parser("create", help="Create an issue, add it to Project, and optionally set status")
    create.add_argument("--title", required=True)
    create.add_argument("--body", default="")
    create.add_argument("--status")

    add = subparsers.add_parser("add", help="Add an existing issue to Project and optionally set status")
    add.add_argument("--issue", required=True)
    add.add_argument("--status")

    set_status = subparsers.add_parser("set-status", help="Set Project Status for an issue")
    set_status.add_argument("--issue", required=True)
    set_status.add_argument("--status", required=True)

    verify = subparsers.add_parser("verify", help="Verify an issue's Project item and status")
    verify.add_argument("--issue", required=True)
    verify.add_argument("--expect-status")
    return parser


def dispatch(client: GhClient, cfg: Config, args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "doctor":
        return command_doctor(client, cfg, args)
    if args.command == "create":
        return command_create(client, cfg, args)
    if args.command == "add":
        return command_add(client, cfg, args)
    if args.command == "set-status":
        return command_set_status(client, cfg, args)
    if args.command == "verify":
        return command_verify(client, cfg, args)
    raise UserError("unknown_command", f"Unknown command: {args.command}")


def write_json(payload: dict[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    stream.write("\n")


def main(argv: list[str] | None = None, *, client: GhClient | None = None, stdout: TextIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = Config(
        repo=args.repo,
        owner=args.owner,
        project_number=args.project_number,
        status_field=args.status_field,
        dry_run=args.dry_run,
    )
    out = stdout or sys.stdout
    gh_client = client or GhClient()
    try:
        write_json(dispatch(gh_client, cfg, args), out)
        return 0
    except UserError as exc:
        write_json({"status": "error", "error": exc.code, "message": exc.message, **exc.details}, out)
        return 2
    except GhCommandError as exc:
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
