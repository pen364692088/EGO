from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "codex_project_autopilot.py"
spec = importlib.util.spec_from_file_location("codex_project_autopilot", MODULE_PATH)
codex_project_autopilot = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = codex_project_autopilot
spec.loader.exec_module(codex_project_autopilot)


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


def j(payload: dict) -> str:
    return json.dumps(payload)


def issue(number: int, title: str, *, body: str = "", state: str = "OPEN") -> dict:
    return {
        "number": number,
        "title": title,
        "state": state,
        "url": f"https://github.com/pen364692088/EGO/issues/{number}",
        "body": body,
        "type": "Issue",
        "repository": "pen364692088/EGO",
    }


READY_BODY = """## Acceptance gate
Runs in dry-run mode.

## Claim ceiling
Local workflow only.

## Rollback
Revert the script.
"""

ISSUE_HUMAN = issue(3, "EgoOperator: real-provider human operator trial v2", body=READY_BODY)
ISSUE_BACKLOG = issue(5, "EgoOperator: memory/gate/tool UX repair backlog from human trial", body=READY_BODY)
ISSUE_PARKED = issue(10, "Parked: WP17/MVP22 continuity lane decision gate", body=READY_BODY)
ISSUE_SUPPORTING = issue(6, "Supporting: repo cleanup route convergence guard", body=READY_BODY)
ISSUE_READY = issue(17, "Codex Toolkit: cross-project devloop/autopilot control plane v1", body=READY_BODY)
ISSUE_UNKNOWN = issue(14, "命令行工具的启用问题", body="unstructured log")


def item(payload: dict, status: str) -> dict:
    return {
        "id": f"ITEM_{payload['number']}",
        "title": payload["title"],
        "status": status,
        "content": payload,
    }


ITEMS = [
    item(ISSUE_HUMAN, "In Progress"),
    item(ISSUE_BACKLOG, "Todo"),
    item(ISSUE_PARKED, "Todo"),
    item(ISSUE_SUPPORTING, "Todo"),
    item(ISSUE_READY, "In Progress"),
    item(ISSUE_UNKNOWN, "Todo"),
]


class FakeGh(codex_project_autopilot.github_project_task.GhClient):
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


class FakeRunner(codex_project_autopilot.CommandRunner):
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: list[str]):
        self.calls.append(tuple(args))
        return codex_project_autopilot.CommandResult(
            args=args,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr="" if self.returncode == 0 else "boom",
        )


def write_contract(tmp_path: Path, *, repo: str = "pen364692088/EGO") -> Path:
    path = tmp_path / "project_contract.yaml"
    path.write_text(
        f"""
version: 1
project:
  name: Test Project
  repo: {repo}
  default_branch: main
github_project:
  owner: pen364692088
  number: 1
  status_field: Status
verify_profiles:
  target:
    commands:
      - label: unit
        command: [python3, -m, pytest]
protected_paths:
  - protected/
allowed_mutation_paths:
  - scripts/
  - docs/codex/tasks/current/
commit_policy:
  mode: direct-main
  push: true
task_classification:
  ready_project_statuses: [In Progress, Todo]
  ready_title_prefixes:
    - "Codex Toolkit:"
    - "EgoOperator:"
  ready_body_markers:
    - "Acceptance gate"
    - "Claim ceiling"
    - "Rollback"
  supporting_title_prefixes:
    - "Supporting:"
    - "Supporting Done:"
  parked_title_prefixes:
    - "Parked:"
  aggregate_title_contains:
    - "backlog"
    - "trial observation review"
  human_required_title_contains:
    - "human operator trial"
    - "human trial"
  high_impact_title_contains:
    - "program state"
    - "evidence ledger"
observation_classes:
  deterministic_local:
    closeout_allowed: true
""",
        encoding="utf-8",
    )
    return path


def base_responses(*, items: list[dict] | None = None) -> dict[tuple[str, ...], list[str] | str]:
    return {
        ("--version",): "gh version 2.92.0\n",
        ("auth", "status"): (
            "github.com\n"
            "  ✓ Logged in to github.com account pen364692088\n"
            "  - Token scopes: 'gist', 'project', 'repo'\n"
        ),
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
        ): j({"items": items if items is not None else ITEMS}),
    }


def run_cli(
    argv: list[str],
    *,
    fake: FakeGh | None = None,
    runner: FakeRunner | None = None,
) -> tuple[int, dict]:
    out = io.StringIO()
    code = codex_project_autopilot.main(argv, client=fake or FakeGh(base_responses()), runner=runner or FakeRunner(), stdout=out)
    return code, json.loads(out.getvalue())


def test_contract_load_success_and_missing_field(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    contract = codex_project_autopilot.load_contract(path)

    assert contract.repo == "pen364692088/EGO"
    assert contract.owner == "pen364692088"
    assert "protected/" in contract.protected_paths

    bad = tmp_path / "bad.yaml"
    bad.write_text("project: {}\n", encoding="utf-8")

    code, payload = run_cli(["--contract", str(bad), "report"], fake=FakeGh({}))

    assert code == 2
    assert payload["error"] in {"missing_github_project_section", "missing_project_contract_fields"}


def test_missing_contract_returns_structured_error(tmp_path: Path) -> None:
    code, payload = run_cli(["--contract", str(tmp_path / "missing.yaml"), "report"], fake=FakeGh({}))

    assert code == 2
    assert payload["error"] == "missing_project_contract"


def test_doctor_reports_contract_and_github_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(codex_project_autopilot.github_project_task.shutil, "which", lambda name: "/usr/bin/gh")
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "doctor"], fake=FakeGh(base_responses()))

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["contract"]["repo"] == "pen364692088/EGO"
    assert payload["github"]["status_field"]["options"] == ["Todo", "In Progress", "Done"]


def test_report_classifies_ready_human_aggregate_parked_supporting_and_unknown(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "report"], fake=FakeGh(base_responses()))

    assert code == 0
    classes = {entry["number"]: entry["classification"]["class"] for entry in payload["issues"]}
    assert classes[17] == "ready"
    assert classes[3] == "human_required"
    assert classes[5] == "aggregate"
    assert classes[10] == "parked"
    assert classes[6] == "supporting"
    assert classes[14] == "unknown"


def test_plan_next_skips_human_aggregate_and_parked(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "plan-next"], fake=FakeGh(base_responses()))

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["next_issue"]["number"] == 17


def test_classify_issue_reads_issue_body_and_project_item(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = base_responses()
    responses[(
        "issue",
        "view",
        "17",
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url,body",
    )] = j(ISSUE_READY)
    fake = FakeGh(responses)

    code, payload = run_cli(["--contract", str(path), "classify-issue", "--issue", "17"], fake=fake)

    assert code == 0
    assert payload["classification"]["class"] == "ready"
    assert payload["project_item"]["status"] == "In Progress"


def test_run_loop_dry_run_stops_on_dirty_unsafe_worktree(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    runner = FakeRunner(stdout=" M legacy/noise.py\n M scripts/codex_project_autopilot.py\n")

    code, payload = run_cli(
        ["--contract", str(path), "run-loop", "--dry-run", "--max-issues", "3", "--max-minutes", "10"],
        fake=FakeGh(base_responses()),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "stopped"
    assert payload["stop_reason"] == "dirty_worktree_unsafe"
    assert payload["dirty"]["unsafe_dirty"] == 1


def test_run_loop_dry_run_plans_ready_issues_without_mutating_github(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    fake = FakeGh(base_responses())

    code, payload = run_cli(
        ["--contract", str(path), "run-loop", "--dry-run", "--max-issues", "1", "--max-minutes", "10"],
        fake=fake,
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["planned"][0]["issue"]["number"] == 17
    mutating = [call for call in fake.calls if "item-edit" in call or "issue" in call and "close" in call]
    assert mutating == []


def test_run_loop_without_dry_run_is_rejected(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "run-loop"], fake=FakeGh(base_responses()))

    assert code == 2
    assert payload["error"] == "mutation_not_implemented"


def test_non_ego_contract_does_not_require_egooperator_paths(tmp_path: Path) -> None:
    path = write_contract(tmp_path, repo="someone/other")

    contract = codex_project_autopilot.load_contract(path)
    encoded = json.dumps(codex_project_autopilot.contract_summary(contract))

    assert contract.repo == "someone/other"
    assert "EgoOperator" not in encoded
