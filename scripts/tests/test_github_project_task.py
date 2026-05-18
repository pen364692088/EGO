from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "github_project_task.py"
spec = importlib.util.spec_from_file_location("github_project_task", MODULE_PATH)
github_project_task = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = github_project_task
spec.loader.exec_module(github_project_task)


PROJECT = {
    "id": "PVT_project",
    "number": 1,
    "title": "EGO main task",
    "url": "https://github.com/users/pen364692088/projects/1",
}
FIELDS = {
    "fields": [
        {
            "id": "FIELD_status",
            "name": "Status",
            "type": "ProjectV2SingleSelectField",
            "options": [
                {"id": "OPT_todo", "name": "Todo"},
                {"id": "OPT_progress", "name": "In Progress"},
                {"id": "OPT_done", "name": "Done"},
            ],
        }
    ]
}
ISSUE = {
    "number": 1,
    "title": "测试任务版",
    "state": "OPEN",
    "url": "https://github.com/pen364692088/EGO/issues/1",
}
ITEM_TODO = {
    "id": "ITEM_1",
    "title": "测试任务版",
    "status": "Todo",
    "content": {**ISSUE, "type": "Issue", "repository": "pen364692088/EGO"},
}
ITEM_PROGRESS = {**ITEM_TODO, "status": "In Progress"}


class FakeGh(github_project_task.GhClient):
    def __init__(self, responses: dict[tuple[str, ...], list[str] | str]) -> None:
        self.responses = {
            key: list(value) if isinstance(value, list) else [value]
            for key, value in responses.items()
        }
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: list[str]) -> str:
        key = tuple(args)
        self.calls.append(key)
        if key not in self.responses or not self.responses[key]:
            raise AssertionError(f"Unexpected gh call: {args}")
        return self.responses[key].pop(0)


def run_cli(fake: FakeGh, argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    code = github_project_task.main(argv, client=fake, stdout=out)
    return code, json.loads(out.getvalue())


def j(payload: dict) -> str:
    return json.dumps(payload)


def base_responses(*, items: list[dict] | None = None) -> dict[tuple[str, ...], list[str] | str]:
    return {
        ("project", "view", "1", "--owner", "pen364692088", "--format", "json"): j(PROJECT),
        ("project", "field-list", "1", "--owner", "pen364692088", "--format", "json"): j(FIELDS),
        (
            "project",
            "item-list",
            "1",
            "--owner",
            "pen364692088",
            "--limit",
            "200",
            "--format",
            "json",
        ): j({"items": items if items is not None else [ITEM_TODO]}),
        (
            "issue",
            "view",
            "1",
            "--repo",
            "pen364692088/EGO",
            "--json",
            "number,title,state,url",
        ): j(ISSUE),
    }


def test_doctor_success(monkeypatch) -> None:
    monkeypatch.setattr(github_project_task.shutil, "which", lambda name: "/usr/bin/gh")
    responses = base_responses()
    responses[("--version",)] = "gh version 2.92.0\n"
    responses[("auth", "status")] = (
        "github.com\n"
        "  ✓ Logged in to github.com account pen364692088\n"
        "  - Token scopes: 'gist', 'project', 'read:org', 'repo'\n"
    )
    fake = FakeGh(responses)

    code, payload = run_cli(fake, ["doctor"])

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["status_field"]["options"] == ["Todo", "In Progress", "Done"]


def test_doctor_reports_missing_project_scope(monkeypatch) -> None:
    monkeypatch.setattr(github_project_task.shutil, "which", lambda name: "/usr/bin/gh")
    fake = FakeGh(
        {
            ("--version",): "gh version 2.92.0\n",
            ("auth", "status"): "github.com\n  ✓ Logged in to github.com account pen364692088\n",
        }
    )

    code, payload = run_cli(fake, ["doctor"])

    assert code == 2
    assert payload["error"] == "missing_project_scope"


def test_create_issue_adds_project_item_and_sets_status() -> None:
    responses = base_responses(items=[])
    responses[(
        "issue",
        "create",
        "--repo",
        "pen364692088/EGO",
        "--title",
        "New task",
        "--body",
        "Body",
    )] = ISSUE["url"] + "\n"
    responses[(
        "issue",
        "view",
        ISSUE["url"],
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url",
    )] = j(ISSUE)
    responses[(
        "project",
        "item-add",
        "1",
        "--owner",
        "pen364692088",
        "--url",
        ISSUE["url"],
    )] = ""
    responses[(
        "project",
        "item-list",
        "1",
        "--owner",
        "pen364692088",
        "--limit",
        "200",
        "--format",
        "json",
    )] = [j({"items": []}), j({"items": [ITEM_TODO]}), j({"items": [ITEM_PROGRESS]})]
    responses[(
        "project",
        "item-edit",
        "--id",
        "ITEM_1",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_progress",
    )] = ""
    fake = FakeGh(responses)

    code, payload = run_cli(fake, ["create", "--title", "New task", "--body", "Body", "--status", "progress"])

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["created"] is True
    assert payload["project_item"]["status"] == "In Progress"
    assert (
        "project",
        "item-edit",
        "--id",
        "ITEM_1",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_progress",
    ) in fake.calls


def test_set_status_calls_item_edit_and_verifies_readback() -> None:
    responses = base_responses(items=[ITEM_TODO])
    responses[(
        "project",
        "item-list",
        "1",
        "--owner",
        "pen364692088",
        "--limit",
        "200",
        "--format",
        "json",
    )] = [j({"items": [ITEM_TODO]}), j({"items": [ITEM_PROGRESS]})]
    responses[(
        "project",
        "item-edit",
        "--id",
        "ITEM_1",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_progress",
    )] = ""
    fake = FakeGh(responses)

    code, payload = run_cli(fake, ["set-status", "--issue", "1", "--status", "In Progress"])

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["project_item"]["status"] == "In Progress"


def test_verify_is_read_only() -> None:
    fake = FakeGh(base_responses(items=[ITEM_PROGRESS]))

    code, payload = run_cli(fake, ["verify", "--issue", "1", "--expect-status", "In Progress"])

    assert code == 0
    assert payload["status"] == "ok"
    assert not any(call[:2] == ("project", "item-edit") for call in fake.calls)
    assert not any(call[:2] == ("project", "item-add") for call in fake.calls)


def test_unknown_status_is_rejected() -> None:
    fake = FakeGh(base_responses(items=[ITEM_TODO]))

    code, payload = run_cli(fake, ["set-status", "--issue", "1", "--status", "Blocked"])

    assert code == 2
    assert payload["error"] == "unknown_status"
    assert payload["available_statuses"] == ["Done", "In Progress", "Todo"]


def test_create_dry_run_does_not_call_gh() -> None:
    fake = FakeGh({})

    code, payload = run_cli(fake, ["--dry-run", "create", "--title", "Dry task", "--status", "Todo"])

    assert code == 0
    assert payload["status"] == "dry_run"
    assert fake.calls == []
