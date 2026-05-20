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
ISSUE_L2 = issue(18, "Codex Toolkit: dirty-baseline scoped L2 single-issue executor", body=READY_BODY)
ISSUE_EPIC = issue(25, "Epic 0: Experience baseline and eval contract", body=READY_BODY)
ISSUE_RESEARCH = issue(26, "Research: external agent project scan", body=READY_BODY)
ISSUE_HUMAN_OBS = issue(
    27,
    "EgoRoadmap: human perception smoke",
    body=f"{READY_BODY}\n\nObservation class: human_required\n",
)
ISSUE_LLM = issue(
    23,
    "Codex Toolkit: scripted LLM judge closeout case",
    body=READY_BODY + "\nObservation class: scripted_with_llm_judge\n",
)
ISSUE_HIGH = issue(
    24,
    "Codex Toolkit: program state mutation",
    body=READY_BODY,
)


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
    item(ISSUE_L2, "In Progress"),
    item(ISSUE_EPIC, "Todo"),
    item(ISSUE_RESEARCH, "Todo"),
    item(ISSUE_HUMAN_OBS, "Todo"),
    item(ISSUE_LLM, "In Progress"),
    item(ISSUE_HIGH, "In Progress"),
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
    def __init__(
        self,
        stdout: str = "",
        returncode: int = 0,
        responses: dict[tuple[str, ...], tuple[int, str, str]] | None = None,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: list[str], *, env: dict[str, str] | None = None):
        key = tuple(args)
        self.calls.append(key)
        if key in self.responses:
            returncode, stdout, stderr = self.responses[key]
            return codex_project_autopilot.CommandResult(
                args=args,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )
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
    - "EgoRoadmap:"
  epic_title_prefixes:
    - "Epic "
  research_title_prefixes:
    - "Research:"
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
  scripted_real_entry:
    closeout_allowed: true
  scripted_with_llm_judge:
    closeout_allowed: false
  human_required:
    closeout_allowed: false
auto_closeout:
  default_observation_class: deterministic_local
  done_status: Done
  observation_verify_profiles:
    deterministic_local: target
    scripted_real_entry: target
    scripted_with_llm_judge: target
  llm_review_observation_classes:
    - scripted_with_llm_judge
  hard_stop_classes:
    - human_required
    - aggregate
    - parked
    - supporting
    - unknown
    - high_impact
    - blocked
  hard_stop_title_contains:
    - "program state"
    - "evidence ledger"
    - "stage card"
  hard_stop_body_markers:
    - "requires stage card"
    - "modifies docs/PROGRAM_STATE_UNIFIED.yaml"
  claim_ceiling: Test closeout claim
auto_execute:
  require_project_status: In Progress
  allowed_observation_classes:
    - deterministic_local
    - scripted_real_entry
  blocked_observation_classes:
    - scripted_with_llm_judge
    - human_required
    - aggregate
    - parked
    - supporting
    - unknown
    - high_impact
  observation_verify_profiles:
    deterministic_local: target
    scripted_real_entry: target
  hard_stop_classes:
    - human_required
    - aggregate
    - parked
    - supporting
    - unknown
    - high_impact
    - blocked
  hard_stop_title_contains:
    - "program state"
    - "evidence ledger"
    - "stage card"
  hard_stop_body_markers:
    - "requires stage card"
    - "modifies docs/PROGRAM_STATE_UNIFIED.yaml"
  claim_ceiling: Test executor claim
auto_pause:
  enabled: false
  recent_report_limit: 8
  repeated_failure_threshold: 3
  repeated_issue_threshold: 3
  pausing_stop_reasons:
    - dirty_worktree_unsafe
    - dirty_scope_unsafe
    - closeout_not_eligible
    - issue_not_ready
    - no_ready_issue
    - l5_execute_not_implemented
goal_control:
  planning_backend: codex_exec
  native_goal_enabled: false
  candidate_issue_limit: 3
  recent_report_limit: 8
  hard_stop_markers:
    - "program state"
    - "evidence ledger"
    - "stage card"
    - "docs/PROGRAM_STATE_UNIFIED.yaml"
  claim_ceiling: Test goal-control claim
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
    assert classes[18] == "ready"
    assert classes[25] == "epic"
    assert classes[26] == "research"
    assert classes[27] == "human_required"
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


def test_plan_next_can_select_research_when_no_ready_issue(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "plan-next"],
        fake=FakeGh(base_responses(items=[item(ISSUE_EPIC, "Todo"), item(ISSUE_RESEARCH, "Todo")])),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["next_issue"]["number"] == 26
    assert payload["next_issue"]["classification"]["class"] == "research"


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
    baseline = tmp_path / "missing_baseline.json"
    runner = FakeRunner(stdout=" M legacy/noise.py\n M scripts/codex_project_autopilot.py\n")

    code, payload = run_cli(
        [
            "--contract",
            str(path),
            "--baseline-path",
            str(baseline),
            "run-loop",
            "--dry-run",
            "--max-issues",
            "3",
            "--max-minutes",
            "10",
        ],
        fake=FakeGh(base_responses()),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "stopped"
    assert payload["stop_reason"] == "dirty_worktree_unsafe"
    assert payload["dirty_gate"]["summary"]["unsafe_dirty"] == 1


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


def test_run_loop_defaults_to_dry_run(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "run-loop"], fake=FakeGh(base_responses()))

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True


def test_non_ego_contract_does_not_require_egooperator_paths(tmp_path: Path) -> None:
    path = write_contract(tmp_path, repo="someone/other")

    contract = codex_project_autopilot.load_contract(path)
    encoded = json.dumps(codex_project_autopilot.contract_summary(contract))

    assert contract.repo == "someone/other"
    assert "EgoOperator" not in encoded


def test_baseline_records_dirty_state(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    runner = FakeRunner(stdout=" M legacy/noise.py\n M scripts/codex_project_autopilot.py\n")

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "baseline"],
        fake=FakeGh({}),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["entry_count"] == 2
    assert runner.calls == [("git", "status", "--short", "--untracked-files=all")]
    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["entry_count"] == 2


def test_baseline_records_untracked_files(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    runner = FakeRunner(stdout="?? scripts/new_helper.py\n")

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "baseline"],
        fake=FakeGh({}),
        runner=runner,
    )

    assert code == 0
    assert payload["entry_count"] == 1
    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["entries"][0]["status"] == "??"
    assert recorded["entries"][0]["path"] == "scripts/new_helper.py"


def test_diff_scope_allows_unchanged_preexisting_dirty_outside_allowed_paths(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    runner = FakeRunner(stdout=" M legacy/noise.py\n")

    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=runner)
    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "diff-scope"],
        fake=FakeGh({}),
        runner=runner,
    )

    assert code == 0
    assert payload["unsafe"]["count"] == 0
    assert payload["counts"]["unchanged_preexisting"] == 1


def test_diff_scope_separates_new_scoped_and_new_unsafe_changes(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    runner = FakeRunner(stdout="")
    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=runner)

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "diff-scope"],
        fake=FakeGh({}),
        runner=FakeRunner(stdout=" M scripts/codex_project_autopilot.py\n M legacy/new_noise.py\n"),
    )

    assert code == 0
    assert payload["scoped"]["count"] == 1
    assert payload["unsafe"]["count"] == 1
    assert payload["counts"]["new_scoped"] == 1
    assert payload["counts"]["new_unsafe"] == 1


def test_diff_scope_marks_changed_preexisting_outside_allowed_as_unsafe(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "version": 1,
                "entry_count": 1,
                "entries": [{"status": " M", "path": "legacy/noise.py", "line": " M legacy/noise.py", "signature": "old"}],
            }
        ),
        encoding="utf-8",
    )

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "diff-scope"],
        fake=FakeGh({}),
        runner=FakeRunner(stdout=" M legacy/noise.py\n"),
    )

    assert code == 0
    assert payload["unsafe"]["count"] == 1
    assert payload["counts"]["changed_preexisting_unsafe"] == 1


def test_pause_gate_detects_repeated_failure_stop_reason() -> None:
    reports = [{"stop_reason": "dirty_scope_unsafe", "planned": []} for _ in range(3)]

    gate = codex_project_autopilot.pause_gate_from_reports(
        reports,
        repeated_failure_threshold=3,
        repeated_issue_threshold=3,
        pausing_stop_reasons=["dirty_scope_unsafe"],
    )

    assert gate["status"] == "paused"
    assert gate["pause_required"] is True
    assert gate["reasons"][0]["reason"] == "repeated_failure_stop_reason"
    assert gate["next_action"] == "reframe_or_create_operator_cut"


def test_pause_gate_detects_repeated_same_issue_zeno_trap() -> None:
    reports = [
        {"stop_reason": "max_issues_reached", "planned": [{"issue": {"number": 56}}]},
        {"stop_reason": "max_issues_reached", "planned": [{"issue": {"number": 56}}]},
        {"stop_reason": "max_issues_reached", "planned": [{"issue": {"number": 56}}]},
    ]

    gate = codex_project_autopilot.pause_gate_from_reports(
        reports,
        repeated_failure_threshold=3,
        repeated_issue_threshold=3,
        pausing_stop_reasons=["dirty_scope_unsafe"],
    )

    assert gate["status"] == "paused"
    assert any(reason["reason"] == "zeno_trap_repeated_issue" for reason in gate["reasons"])


def test_pause_gate_allows_mixed_progress_reports() -> None:
    reports = [
        {"stop_reason": "max_issues_reached", "planned": [{"issue": {"number": 56}}]},
        {"stop_reason": "ready_queue_exhausted", "planned": [{"issue": {"number": 55}}]},
    ]

    gate = codex_project_autopilot.pause_gate_from_reports(
        reports,
        repeated_failure_threshold=3,
        repeated_issue_threshold=3,
        pausing_stop_reasons=["dirty_scope_unsafe"],
    )

    assert gate["status"] == "ok"
    assert gate["pause_required"] is False


def test_load_run_reports_skips_unit_test_claim_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "20260101-000000-autopilot-run.json").write_text(
        json.dumps({"planned": [{"closeout_check": {"claim_ceiling": "Test closeout claim"}}]}),
        encoding="utf-8",
    )

    reports = codex_project_autopilot.load_run_reports(report_dir, limit=8)

    assert reports == []


def test_operator_digest_summarizes_planned_issue_and_next_user_action() -> None:
    payload = {
        "status": "ok",
        "mode": "plan",
        "stop_reason": "max_issues_reached",
        "planned": [{"issue": {"number": 57, "title": "Digest task"}, "dry_run_action": "would_run_once"}],
    }

    digest = codex_project_autopilot.build_operator_digest(payload)

    assert "#57:would_run_once" in digest["summary"]
    assert digest["issue_count"] == 1
    assert digest["needs_user"] == ["No immediate user action required for this dry-run report."]


def test_operator_digest_explains_pause_and_dirty_stop() -> None:
    pause_digest = codex_project_autopilot.build_operator_digest(
        {"status": "stopped", "stop_reason": "autopilot_pause_required", "planned": []}
    )
    dirty_digest = codex_project_autopilot.build_operator_digest(
        {"status": "stopped", "stop_reason": "dirty_scope_unsafe", "planned": []}
    )

    assert "Reframe" in pause_digest["needs_user"][0]
    assert "dirty worktree" in dirty_digest["needs_user"][0]


def test_run_loop_with_baseline_does_not_block_on_unchanged_preexisting_dirty(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    runner = FakeRunner(stdout=" M legacy/noise.py\n")
    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=runner)

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "run-loop", "--dry-run", "--max-issues", "1"],
        fake=FakeGh(base_responses()),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["planned"][0]["issue"]["number"] == 17
    assert payload["operator_digest"]["issue_count"] == 1


def test_run_loop_with_baseline_blocks_new_out_of_scope_dirty(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=FakeRunner(stdout=""))

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "run-loop", "--dry-run"],
        fake=FakeGh(base_responses()),
        runner=FakeRunner(stdout=" M legacy/noise.py\n"),
    )

    assert code == 0
    assert payload["status"] == "stopped"
    assert payload["stop_reason"] == "dirty_scope_unsafe"


def test_normalize_issue_dry_run_outputs_structured_body_for_command_tool_log(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = base_responses()
    responses[(
        "issue",
        "view",
        "14",
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url,body",
    )] = j(ISSUE_UNKNOWN)

    code, payload = run_cli(
        ["--contract", str(path), "normalize-issue", "--issue", "14", "--dry-run"],
        fake=FakeGh(responses),
    )

    assert code == 0
    body = payload["proposed_body"]
    assert "## Acceptance gate" in body
    assert "## Claim ceiling" in body
    assert "run command" in body.casefold() or "command-line" in body.casefold()


def test_normalize_issue_without_dry_run_is_rejected(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = base_responses()
    responses[(
        "issue",
        "view",
        "14",
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url,body",
    )] = j(ISSUE_UNKNOWN)

    code, payload = run_cli(["--contract", str(path), "normalize-issue", "--issue", "14"], fake=FakeGh(responses))

    assert code == 2
    assert payload["error"] == "mutation_not_implemented"


def test_decompose_goal_outputs_ready_issue_bodies_with_review_gate(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    goal = "- Build continuity memory repair\n- Add scripted real-entry eval"

    code, payload = run_cli(
        [
            "--contract",
            str(path),
            "decompose-goal",
            "--goal",
            goal,
            "--canonical-source",
            "docs/roadmap.md",
            "--title-prefix",
            "EgoRoadmap:",
            "--observation-class",
            "scripted_real_entry",
        ],
        fake=FakeGh({}),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["proposal_count"] == 2
    assert payload["reviewer_check"]["verdict"] == "proposal_set_ready"
    assert payload["proposals"][0]["title"].startswith("EgoRoadmap:")
    assert len(payload["proposals"][0]["title"]) <= 96
    body = payload["proposals"][0]["body"]
    assert "## Canonical source" in body
    assert "## Acceptance gate" in body
    assert "Observation class: scripted_real_entry" in body
    assert "docs/roadmap.md" in body


def test_decompose_goal_reads_goal_file_and_uses_contract_prefix(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    goal_path = tmp_path / "goal.md"
    goal_path.write_text("Improve task board automation without bypassing gates.", encoding="utf-8")

    code, payload = run_cli(
        ["--contract", str(path), "decompose-goal", "--goal-file", str(goal_path), "--max-issues", "2"],
        fake=FakeGh({}),
    )

    assert code == 0
    assert payload["proposal_count"] == 2
    assert payload["proposals"][0]["title"].startswith("Codex Toolkit:")
    assert payload["reviewer_check"]["finding_count"] == 0


def test_decomposition_reviewer_flags_missing_gate_and_overclaim() -> None:
    proposals = [
        {
            "title": "Bad task",
            "body": "## Canonical source\nx\n\n## Current meaning\nThis proves consciousness.\n",
        }
    ]

    review = codex_project_autopilot.review_decomposition_proposals(proposals)

    assert review["verdict"] == "needs_revision"
    reasons = {finding["reason"] for finding in review["findings"]}
    assert "missing_required_section" in reasons
    assert "possible_overclaim" in reasons


def test_decompose_goal_requires_single_goal_input(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    goal_path = tmp_path / "goal.md"
    goal_path.write_text("Goal", encoding="utf-8")

    code, payload = run_cli(
        ["--contract", str(path), "decompose-goal", "--goal", "Goal", "--goal-file", str(goal_path)],
        fake=FakeGh({}),
    )

    assert code == 2
    assert payload["error"] == "ambiguous_goal_input"


def responses_for_issue(full_issue: dict, *, status: str = "In Progress") -> dict[tuple[str, ...], list[str] | str]:
    responses = base_responses()
    issue_ref = str(full_issue["number"])
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
    )] = j({"items": [item(full_issue, status)]})
    responses[(
        "issue",
        "view",
        issue_ref,
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url,body",
    )] = j(full_issue)
    return responses


def test_run_once_dry_run_refuses_non_ready_issue_classes(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    cases = [
        (ISSUE_UNKNOWN, "unknown"),
        (ISSUE_HUMAN, "human_required"),
        (ISSUE_BACKLOG, "aggregate"),
        (ISSUE_PARKED, "parked"),
        (ISSUE_SUPPORTING, "supporting"),
    ]

    for payload, expected_class in cases:
        code, result = run_cli(
            ["--contract", str(path), "run-once", "--issue", str(payload["number"]), "--dry-run"],
            fake=FakeGh(responses_for_issue(payload)),
            runner=FakeRunner(stdout=""),
        )

        assert code == 0
        assert result["status"] == "stopped"
        assert result["stop_reason"] == "issue_not_ready"
        assert result["classification"]["class"] == expected_class


def test_run_once_dry_run_plans_ready_issue_with_clean_scope(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=FakeRunner(stdout=""))

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "run-once", "--issue", "18", "--dry-run"],
        fake=FakeGh(responses_for_issue(ISSUE_L2)),
        runner=FakeRunner(stdout=" M scripts/codex_project_autopilot.py\n"),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["planned"][0]["step"] == "load_issue"


def test_run_once_dry_run_plans_research_issue_with_clean_scope(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    baseline = tmp_path / "baseline.json"
    run_cli(["--contract", str(path), "--baseline-path", str(baseline), "baseline"], fake=FakeGh({}), runner=FakeRunner(stdout=""))

    code, payload = run_cli(
        ["--contract", str(path), "--baseline-path", str(baseline), "run-once", "--issue", "26", "--dry-run"],
        fake=FakeGh(responses_for_issue(ISSUE_RESEARCH, status="Todo")),
        runner=FakeRunner(stdout=" M scripts/codex_project_autopilot.py\n"),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["classification"]["class"] == "research"


def test_verify_profile_runs_contract_commands(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    runner = FakeRunner()

    code, payload = run_cli(["--contract", str(path), "verify-profile", "--profile", "target"], fake=FakeGh({}), runner=runner)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["passed"] is True
    assert payload["results"][0]["label"] == "unit"
    assert runner.calls == [("python3", "-m", "pytest")]


def closeout_runner(
    *,
    verify_stdout: str = "unit ok",
    changed_files: str = "scripts/codex_project_autopilot.py\nscripts/tests/test_codex_project_autopilot.py\n",
) -> FakeRunner:
    return FakeRunner(
        responses={
            ("git", "status", "--short", "--untracked-files=all"): (0, "", ""),
            ("python3", "-m", "pytest"): (0, verify_stdout, ""),
            ("git", "rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n", ""),
            ("git", "rev-parse", "HEAD"): (0, "abcdef1234567890\n", ""),
            ("git", "status", "-sb"): (0, "## main...origin/main\n", ""),
            ("git", "show", "--name-only", "--format=", "--diff-filter=ACMR", "HEAD"): (0, changed_files, ""),
        }
    )


def test_closeout_check_deterministic_local_is_eligible_after_verify_pass(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "eligible"
    assert payload["eligible"] is True
    assert payload["verify"]["passed"] is True
    assert payload["evidence_packet"]["implementation_refs"]["changed_files"]
    comment = payload["closeout_comment"]
    assert "What changed:" in comment
    assert "Acceptance evidence:" in comment
    assert "Verification:" in comment
    assert "Implementation refs:" in comment
    assert "Residuals:" in comment
    assert "Claim ceiling:" in comment
    assert "Not claimed:" in comment


def test_closeout_check_deterministic_local_without_issue_specific_evidence_blocks(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=closeout_runner(changed_files=""),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] == "closeout_evidence_missing_issue_specific_item" for reason in payload["blocked_reasons"])


def test_closeout_check_scripted_real_entry_requires_report_evidence(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    scripted = issue(
        70,
        "Codex Toolkit: scripted real entry closeout",
        body=READY_BODY + "\nObservation class: scripted_real_entry\n",
    )

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "70"],
        fake=FakeGh(responses_for_issue(scripted)),
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(
        reason["reason"] == "closeout_evidence_missing_scripted_real_entry_item"
        for reason in payload["blocked_reasons"]
    )


def test_closeout_check_scripted_real_entry_with_report_evidence_is_eligible(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    scripted = issue(
        71,
        "Codex Toolkit: scripted real entry closeout",
        body=(
            READY_BODY
            + "\nObservation class: scripted_real_entry\n\n"
            + "## Closeout evidence\n"
            + "- scripted real-entry report: `.codex/autopilot/runs/demo.json` shows the user-facing entrypoint passed.\n"
        ),
    )

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "71"],
        fake=FakeGh(responses_for_issue(scripted)),
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "eligible"
    assert any(item["type"] == "issue_evidence" for item in payload["evidence_packet"]["evidence_items"])


def test_closeout_comment_summarizes_long_verify_output(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    long_output = "A" * 900 + "TAIL"

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=closeout_runner(verify_stdout=long_output),
    )

    assert code == 0
    assert payload["status"] == "eligible"
    comment = payload["closeout_comment"]
    assert "omitted=" in comment
    assert long_output not in comment


def test_closeout_comment_current_meaning_excludes_observation_class_line(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    with_meaning = issue(
        72,
        "Codex Toolkit: closeout evidence packet v2",
        body=(
            "## Current meaning\n"
            "Upgrade closeout comments into compact evidence packets.\n\n"
            "Observation class: deterministic_local\n\n"
            "## Acceptance gate\n"
            "- Evidence-first comment is generated.\n\n"
            "## Claim ceiling\n"
            "Local only.\n\n"
            "## Rollback\n"
            "Revert script changes.\n"
        ),
    )

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "72"],
        fake=FakeGh(responses_for_issue(with_meaning)),
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "eligible"
    comment = payload["closeout_comment"]
    assert "Upgrade closeout comments into compact evidence packets." in comment
    assert "Addressed target: Upgrade closeout comments into compact evidence packets. Observation class" not in comment


def test_closeout_check_verify_failure_blocks(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    runner = FakeRunner(
        responses={
            ("git", "status", "--short", "--untracked-files=all"): (0, "", ""),
            ("python3", "-m", "pytest"): (1, "", "failed"),
        }
    )

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] == "verify_profile_failed" for reason in payload["blocked_reasons"])


def test_closeout_check_todo_issue_is_not_eligible(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY, status="Todo")),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(
        reason["reason"] == "project_status_not_in_progress_for_closeout"
        for reason in payload["blocked_reasons"]
    )


def test_executor_check_deterministic_local_in_progress_is_eligible(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "executor-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "eligible"
    assert payload["eligible"] is True
    assert payload["verify_profile"] == "target"
    assert payload["claim_ceiling"] == "Test executor claim"
    assert payload["execution_plan"][0]["step"] == "claim_issue_in_progress"


def test_executor_check_todo_issue_is_blocked_until_claimed(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "executor-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY, status="Todo")),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(
        reason["reason"] == "project_status_not_in_progress_for_l5_execute"
        for reason in payload["blocked_reasons"]
    )


def test_executor_check_blocks_llm_judge_and_human_required_classes(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    for payload in (ISSUE_LLM, ISSUE_HUMAN_OBS):
        code, result = run_cli(
            ["--contract", str(path), "executor-check", "--issue", str(payload["number"])],
            fake=FakeGh(responses_for_issue(payload)),
            runner=FakeRunner(stdout=""),
        )

        assert code == 0
        assert result["status"] == "blocked"
        assert any(
            reason["reason"] in {"observation_class_not_auto_executable", "issue_class_not_auto_executable"}
            for reason in result["blocked_reasons"]
        )


def test_executor_check_blocks_hard_stop_marker_even_if_ready(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "executor-check", "--issue", "24"],
        fake=FakeGh(responses_for_issue(ISSUE_HIGH)),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] == "issue_class_not_auto_executable" for reason in payload["blocked_reasons"])


def test_executor_check_blocks_dirty_unsafe_scope(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "executor-check", "--issue", "17"],
        fake=FakeGh(responses_for_issue(ISSUE_READY)),
        runner=FakeRunner(stdout=" M legacy/noise.py\n"),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(
        reason["reason"] in {"dirty_worktree_unsafe", "dirty_scope_unsafe"}
        for reason in payload["blocked_reasons"]
    )


def test_closeout_check_hard_stop_blocks_before_reviewer(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "24"],
        fake=FakeGh(responses_for_issue(ISSUE_HIGH)),
        runner=FakeRunner(stdout='{"verdict":"closeout_allowed"}'),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] == "issue_class_not_auto_closeable" for reason in payload["blocked_reasons"])
    assert "llm_reviewer" not in payload


def test_scripted_with_llm_judge_requires_positive_reviewer(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    reviewer = json.dumps(
        {
            "verdict": "closeout_allowed",
            "reasons": ["local evidence is sufficient"],
            "missing_evidence": [],
            "claim_ceiling": "local only",
            "suggested_comment": "ok",
        }
    )
    runner = FakeRunner(
        stdout="",
        responses={
            ("python3", "-m", "pytest"): (0, "", ""),
            (
                "codex",
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(codex_project_autopilot.DEFAULT_REVIEW_SCHEMA_PATH),
                # Prompt argument is long and generated at runtime; matched below by custom fallback.
            ): (0, reviewer, ""),
        },
    )

    original_run = runner.run
    prompts: list[str] = []

    def run_with_reviewer_prefix(args, *, env=None):
        if tuple(args[:6]) == ("codex", "exec", "--ephemeral", "--sandbox", "read-only", "--output-schema"):
            prompts.append(args[-1])
            return codex_project_autopilot.CommandResult(args=args, returncode=0, stdout=reviewer, stderr="")
        return original_run(args, env=env)

    runner.run = run_with_reviewer_prefix  # type: ignore[method-assign]
    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "23"],
        fake=FakeGh(responses_for_issue(ISSUE_LLM)),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "eligible"
    assert payload["llm_reviewer"]["verdict"] == "closeout_allowed"
    assert prompts
    assert '"status": "pending_llm_review"' in prompts[0]
    assert "Do not block solely" in prompts[0]


def test_scripted_with_llm_judge_unavailable_blocks(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    runner = FakeRunner(stdout="")
    original_run = runner.run

    def run_with_reviewer_failure(args, *, env=None):
        if tuple(args[:6]) == ("codex", "exec", "--ephemeral", "--sandbox", "read-only", "--output-schema"):
            return codex_project_autopilot.CommandResult(args=args, returncode=127, stdout="", stderr="codex not found")
        return original_run(args, env=env)

    runner.run = run_with_reviewer_failure  # type: ignore[method-assign]

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "23"],
        fake=FakeGh(responses_for_issue(ISSUE_LLM)),
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] == "llm_reviewer_unavailable" for reason in payload["blocked_reasons"])


def test_closeout_once_dry_run_does_not_mutate_github(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    fake = FakeGh(responses_for_issue(ISSUE_READY))

    code, payload = run_cli(
        ["--contract", str(path), "closeout-once", "--issue", "17", "--dry-run"],
        fake=fake,
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert not any(call[:2] == ("issue", "close") for call in fake.calls)
    assert payload["planned"][0]["gh"][:2] == ["issue", "comment"]


def test_closeout_once_execute_closes_only_when_eligible(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = responses_for_issue(ISSUE_READY)
    responses[(
        "issue",
        "view",
        "17",
        "--repo",
        "pen364692088/EGO",
        "--json",
        "number,title,state,url",
    )] = [
        j({k: ISSUE_READY[k] for k in ("number", "title", "state", "url")}),
        j({k: ISSUE_READY[k] for k in ("number", "title", "state", "url")}),
        j({"number": 17, "title": ISSUE_READY["title"], "state": "CLOSED", "url": ISSUE_READY["url"]}),
        j({"number": 17, "title": ISSUE_READY["title"], "state": "CLOSED", "url": ISSUE_READY["url"]}),
    ]
    responses[("project", "view", "1", "--owner", "pen364692088", "--format", "json")] = j(PROJECT)
    responses[("project", "field-list", "1", "--owner", "pen364692088", "--format", "json")] = [j(FIELDS), j(FIELDS)]
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
    )] = [
        j({"items": [item(ISSUE_READY, "In Progress")]}),
        j({"items": [item(ISSUE_READY, "In Progress")]}),
        j({"items": [item(ISSUE_READY, "Done")]}),
        j({"items": [item(ISSUE_READY, "Done")]}),
    ]
    responses[(
        "project",
        "item-edit",
        "--id",
        "ITEM_17",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_done",
    )] = ""
    responses[("issue", "close", "17", "--repo", "pen364692088/EGO")] = ""
    fake = FakeGh(responses)

    # The comment body is generated dynamically, so accept any issue comment call.
    original_run = fake.run

    def run_accept_dynamic_comment(args):
        if tuple(args[:5]) == ("issue", "comment", "17", "--repo", "pen364692088/EGO"):
            fake.calls.append(tuple(args))
            return ""
        return original_run(args)

    fake.run = run_accept_dynamic_comment  # type: ignore[method-assign]
    code, payload = run_cli(
        ["--contract", str(path), "closeout-once", "--issue", "17", "--execute"],
        fake=fake,
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["closeout"]["closed"] is True


def test_run_loop_l3_closeout_dry_run_writes_report_without_mutating(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = responses_for_issue(ISSUE_READY)
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
    )] = [
        j({"items": [item(ISSUE_READY, "In Progress")]}),
        j({"items": [item(ISSUE_READY, "In Progress")]}),
    ]
    fake = FakeGh(responses)
    report_dir = tmp_path / "reports"

    code, payload = run_cli(
        [
            "--contract",
            str(path),
            "--report-dir",
            str(report_dir),
            "run-loop",
            "--mode",
            "l3-closeout",
            "--dry-run",
            "--max-issues",
            "1",
            "--write-report",
        ],
        fake=fake,
        runner=closeout_runner(),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["planned"][0]["closeout_check"]["eligible"] is True
    assert payload["operator_digest"]["summary"].startswith("Autopilot l3-closeout run ok")
    assert payload["report_path"].endswith("-autopilot-run.json")
    assert str(report_dir) in payload["report_path"]
    assert not any(call[:2] == ("issue", "close") for call in fake.calls)


def test_run_loop_l5_executor_dry_run_emits_executor_packet_without_mutating(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    responses = responses_for_issue(ISSUE_READY)
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
    )] = [
        j({"items": [item(ISSUE_READY, "In Progress")]}),
        j({"items": [item(ISSUE_READY, "In Progress")]}),
    ]
    fake = FakeGh(responses)

    code, payload = run_cli(
        ["--contract", str(path), "run-loop", "--mode", "l5-executor", "--dry-run", "--max-issues", "1"],
        fake=fake,
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["mode"] == "l5-executor"
    assert payload["planned"][0]["executor_check"]["eligible"] is True
    assert payload["planned"][0]["dry_run_action"] == "would_enter_bounded_rollout"
    assert not any(call[:2] == ("issue", "close") for call in fake.calls)


def test_run_loop_l5_executor_execute_is_not_implemented(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "run-loop", "--mode", "l5-executor", "--execute", "--max-issues", "1"],
        fake=FakeGh(base_responses()),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "stopped"
    assert payload["stop_reason"] == "l5_execute_not_implemented"


def planner_response(*, title: str = "Codex Toolkit: generated ready task", marker: str = "") -> str:
    return j(
        {
            "status": "ok",
            "goal_summary": "Improve Autopilot goal-aware control.",
            "current_blocker": "No ready issue is available.",
            "recommended_next_action": "Create a bounded ready issue.",
            "candidate_issues": [
                {
                    "title": title,
                    "current_meaning": f"Generate a bounded task proposal. {marker}".strip(),
                    "observation_class": "deterministic_local",
                    "acceptance_gate": "The generated issue has acceptance, rollback, claim ceiling, and observation class.",
                    "rollback": "Close the candidate as superseded if the framing is wrong.",
                    "claim_ceiling": "Planner proposal only; not implementation evidence.",
                }
            ],
            "stop_conditions": [],
            "claim_ceiling": "Planner proposal only.",
            "requires_human": False,
        }
    )


def planner_runner(stdout: str, *, returncode: int = 0) -> FakeRunner:
    runner = FakeRunner(stdout="")
    original_run = runner.run

    def run_with_planner(args, *, env=None):
        if tuple(args[:6]) == ("codex", "exec", "--ephemeral", "--sandbox", "read-only", "--output-schema"):
            return codex_project_autopilot.CommandResult(args=args, returncode=returncode, stdout=stdout, stderr="planner failed" if returncode else "")
        return original_run(args, env=env)

    runner.run = run_with_planner  # type: ignore[method-assign]
    return runner


def test_goal_status_reports_board_distribution(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "goal-status"], fake=FakeGh(base_responses()))

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["control_plane"] == "goal-aware"
    assert payload["counts"]["ready"] == 3
    assert payload["counts"]["human_required"] == 2
    assert payload["next_issue"]["number"] == 17
    assert payload["outcome_scoreboard"]["ready_issue_throughput"]["ready_count"] >= 2


def test_goal_refresh_outputs_planner_packet(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(["--contract", str(path), "goal-refresh"], fake=FakeGh(base_responses()))

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["goal_control"]["planning_backend"] == "codex_exec"
    assert "board_counts" in payload
    assert "outcome_scoreboard" in payload


def test_plan_proposal_uses_codex_exec_planner_and_keeps_dry_run(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    fake = FakeGh(base_responses(items=[item(ISSUE_EPIC, "Todo")]))
    runner = planner_runner(planner_response())

    code, payload = run_cli(
        ["--contract", str(path), "plan-proposal", "--board", "--dry-run"],
        fake=fake,
        runner=runner,
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["planner"]["backend"] == "codex_exec"
    assert payload["candidate_issues"][0]["acceptance_gate"]
    assert not any(call[:2] == ("issue", "create") for call in fake.calls)


def test_plan_proposal_backend_unavailable_returns_structured_status(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "plan-proposal", "--board", "--dry-run"],
        fake=FakeGh(base_responses(items=[item(ISSUE_EPIC, "Todo")])),
        runner=planner_runner("", returncode=127),
    )

    assert code == 0
    assert payload["status"] == "planning_backend_unavailable"
    assert payload["planner"]["backend"] == "codex_exec"
    assert payload["fallback_candidate_issues"]


def test_plan_proposal_blocks_high_impact_or_protected_planner_output(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "plan-proposal", "--board", "--dry-run"],
        fake=FakeGh(base_responses(items=[item(ISSUE_EPIC, "Todo")])),
        runner=planner_runner(planner_response(marker="Touch docs/PROGRAM_STATE_UNIFIED.yaml")),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    assert any(reason["reason"] in {"planner_hard_stop_marker", "planner_protected_path_marker"} for reason in payload["blocked_reasons"])


def test_propose_ready_issues_dry_run_generates_required_fields(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "propose-ready-issues", "--dry-run", "--max-issues", "2"],
        fake=FakeGh(base_responses(items=[item(ISSUE_UNKNOWN, "Todo"), item(ISSUE_EPIC, "Todo")])),
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["proposal_count"] == 2
    first = payload["proposals"][0]
    assert first["acceptance_gate"]
    assert first["rollback"]
    assert first["claim_ceiling"]
    assert first["observation_class"]
    assert "## Acceptance gate" in first["body"]


def test_run_loop_no_ready_outputs_candidate_issue_drafts(tmp_path: Path) -> None:
    path = write_contract(tmp_path)

    code, payload = run_cli(
        ["--contract", str(path), "run-loop", "--dry-run", "--max-issues", "2"],
        fake=FakeGh(base_responses(items=[item(ISSUE_EPIC, "Todo")])),
        runner=FakeRunner(stdout=""),
    )

    assert code == 0
    assert payload["status"] == "stopped"
    assert payload["stop_reason"] == "no_ready_issue"
    assert payload["plan_stage"]["status"] == "candidate_issues_proposed"
    assert payload["plan_stage"]["candidate_issues"][0]["body"].count("## Acceptance gate") == 1


def test_closeout_evidence_does_not_treat_planner_proposal_as_implementation(tmp_path: Path) -> None:
    path = write_contract(tmp_path)
    proposal_only_issue = issue(
        90,
        "Codex Toolkit: planner-only closeout should block",
        body=READY_BODY + "\n## Closeout evidence\n- planner proposal: create a candidate issue from the board.\n",
    )

    code, payload = run_cli(
        ["--contract", str(path), "closeout-check", "--issue", "90"],
        fake=FakeGh(responses_for_issue(proposal_only_issue)),
        runner=closeout_runner(changed_files=""),
    )

    assert code == 0
    assert payload["status"] == "blocked"
    evidence_types = {item["type"] for item in payload["evidence_packet"]["evidence_items"]}
    assert "planner_proposal" in evidence_types
    assert any(reason["reason"] == "closeout_evidence_missing_issue_specific_item" for reason in payload["blocked_reasons"])
