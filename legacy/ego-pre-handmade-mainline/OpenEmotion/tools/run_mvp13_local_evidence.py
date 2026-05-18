from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class SuiteResult:
    name: str
    command: List[str]
    returncode: int
    passed: bool
    log_file: str


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run_suite(*, repo_root: Path, artifacts_dir: Path, name: str, pythonpath: str, args: List[str]) -> SuiteResult:
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath
    command = [sys.executable, "-m", "pytest", *args]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = artifacts_dir / f"{name}.log"
    log_path.write_text(
        completed.stdout + ("\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    return SuiteResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        passed=completed.returncode == 0,
        log_file=str(log_path),
    )


def _git_commit_short(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _render_markdown(report: dict) -> str:
    lines = [
        "# MVP13 Local Evidence Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- git_commit_short: `{report['git_commit_short']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- verification_level: `{report['verification_level']}`",
        f"- evidence_level: `{report['evidence_level']}`",
        "",
        "## Suites",
    ]
    for suite in report["suites"]:
        lines.extend(
            [
                f"- `{suite['name']}`: `{'passed' if suite['passed'] else 'failed'}`",
                f"  - log: `{suite['log_file']}`",
                f"  - returncode: `{suite['returncode']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Acceptance",
            f"- E3 local proof pack exists: `{report['acceptance']['e3_local_proof_pack']}`",
            f"- E4 mainline-trigger path defined: `{report['acceptance']['e4_path_defined']}`",
            f"- E5 stability gate defined: `{report['acceptance']['e5_gate_defined']}`",
            "",
            "## E4 Path",
            report["e4_mainline_path"],
            "",
            "## E5 Gate",
            report["e5_stability_gate"],
            "",
            "## Current Boundary",
            report["current_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    artifacts_root = repo_root / "OpenEmotion" / "artifacts" / "mvp13"
    stamp = _utc_stamp()
    artifacts_dir = artifacts_root / f"formal_owner_evidence_{stamp}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    suites = [
        _run_suite(
            repo_root=repo_root,
            artifacts_dir=artifacts_dir,
            name="owner_contract_and_governance",
            pythonpath="OpenEmotion",
            args=[
                "-q",
                "-s",
                "--noconftest",
                "OpenEmotion/tests/mvp13/test_self_model_owner_contract.py",
                "OpenEmotion/tests/mvp13/test_self_model_infra.py",
                "OpenEmotion/tests/mvp13/test_self_model_persistence.py",
                "OpenEmotion/tests/mvp13/test_self_model_replay.py",
                "OpenEmotion/tests/mvp13/test_self_model_governance.py",
            ],
        ),
        _run_suite(
            repo_root=repo_root,
            artifacts_dir=artifacts_dir,
            name="proto_self_read_integration",
            pythonpath="OpenEmotion",
            args=[
                "-q",
                "-s",
                "OpenEmotion/openemotion/proto_self_v2/tests/test_self_model_read_integration.py",
                "OpenEmotion/openemotion/proto_self_v2/tests/test_kernel_contract.py",
            ],
        ),
        _run_suite(
            repo_root=repo_root,
            artifacts_dir=artifacts_dir,
            name="egocore_bridge",
            pythonpath="EgoCore:OpenEmotion",
            args=[
                "-q",
                "-s",
                "EgoCore/tests/test_runtime_v2_proto_self_runtime.py",
                "EgoCore/tests/test_proto_self_v2_contracts.py",
            ],
        ),
    ]

    overall_status = "pass" if all(item.passed for item in suites) else "fail"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(repo_root),
        "overall_status": overall_status,
        "verification_level": "V3" if overall_status == "pass" else "V2",
        "evidence_level": "E3" if overall_status == "pass" else "E2",
        "suites": [asdict(item) for item in suites],
        "acceptance": {
            "e3_local_proof_pack": overall_status == "pass",
            "e4_path_defined": True,
            "e5_gate_defined": True,
        },
        "e4_mainline_path": (
            "runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2 -> "
            "self_model_update_gate -> formal owner store revision log"
        ),
        "e5_stability_gate": (
            "Require repeated mainline-triggered writeback samples, zero hard invariant violations, "
            "no unstable drift spikes, and replay-consistent owner revisions across a real observation window."
        ),
        "current_boundary": (
            "This report is local E3 proof only. It does not claim E4 mainline-trigger evidence or E5 stability."
        ),
    }

    report_json = artifacts_dir / "mvp13_local_evidence_report.json"
    report_md = artifacts_dir / "mvp13_local_evidence_report.md"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(report), encoding="utf-8")

    shutil.copy2(report_json, artifacts_root / "mvp13_local_evidence_current.json")
    shutil.copy2(report_md, artifacts_root / "mvp13_local_evidence_current.md")

    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
