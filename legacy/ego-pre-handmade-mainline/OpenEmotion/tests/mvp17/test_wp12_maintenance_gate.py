from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = ROOT / "scripts" / "codex"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_wp12_maintenance_verification import build_report_payload, render_markdown  # noqa: E402
from verify_wp12_maintenance_gate import verify_gate  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_valid_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    baseline = tmp_path / "WP12_QA_BASELINE.md"
    report_md = tmp_path / "MAINTENANCE_VERIFICATION_CURRENT.md"
    report_json = tmp_path / "MAINTENANCE_VERIFICATION_CURRENT.json"
    ledger = tmp_path / "MAINTENANCE_LEDGER.md"
    status = tmp_path / "STATUS.md"
    readme = tmp_path / "README.md"

    _write(
        baseline,
        "\n".join(
            [
                "# baseline",
                "## 1. 文档定位",
                "## 2. 当前正式口径",
                "## 3. 已证实功能边界",
                "## 4. 五层测试矩阵",
                "## 5. 十项 Checklist",
                "## 6. 失败分级与 Reopen 规则",
                "## 7. 维护态允许与禁止",
                "## 8. 标准汇报模板",
                "## 9. Canonical Maintenance Commands",
                "run_wp12_maintenance_verification.py",
                "verify_wp12_maintenance_gate.py --json",
                "## 10. Publish Gate",
            ]
        )
        + "\n",
    )
    payload = build_report_payload(
        commands_run=[
            {"label": "x", "command": "pytest x", "returncode": 0, "status": "pass", "summary": "1 passed"}
        ],
        causal_payload={"status": "pass", "verification_level": "V3", "evidence_level": "E3", "pair_count": 4, "passed_count": 4},
        single_payload={
            "status": "pass",
            "verification_level": "V4",
            "evidence_level": "E4",
            "social_writeback_gate": "allow_writeback",
            "proposal_only_discipline_consistent": True,
            "behavioral_authority_none": True,
            "replay_valid": True,
        },
        batch_payload={
            "status": "pass",
            "verification_level": "V5",
            "evidence_level": "E5",
            "report_count": 3,
            "accepted_count": 3,
            "proposal_only_discipline_count": 3,
            "behavioral_authority_none_count": 3,
            "bounded_influence_present_count": 3,
        },
        generated_at="2026-04-04T12:00:00+00:00",
        git_commit_short="abc1234",
    )
    payload["baseline"] = str(baseline)
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(render_markdown(payload), encoding="utf-8")
    ledger.write_text(
        "\n".join(
            [
                "# ledger",
                "### 2026-04-04 — First institutionalized maintenance verification",
                "- generated_at:",
                "  - `2026-04-04T12:00:00+00:00`",
                "- report:",
                "  - `MAINTENANCE_VERIFICATION_CURRENT.md`",
                "  - `MAINTENANCE_VERIFICATION_CURRENT.json`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    status.write_text("status: maintenance_mode\nrun_wp12_maintenance_verification.py\n", encoding="utf-8")
    readme.write_text("verify_wp12_maintenance_gate.py --json\n", encoding="utf-8")
    return baseline, report_md, report_json, ledger, status, readme


def test_verify_gate_accepts_valid_fixture(tmp_path):
    baseline, report_md, report_json, ledger, status, readme = _build_valid_fixture(tmp_path)

    payload = verify_gate(
        baseline_path=baseline,
        report_md_path=report_md,
        report_json_path=report_json,
        ledger_path=ledger,
        status_path=status,
        readme_path=readme,
    )

    assert payload["status"] == "pass"
    assert payload["publish_gate_ready"] is True


def test_verify_gate_rejects_overclaim_fixture(tmp_path):
    baseline, report_md, report_json, ledger, status, readme = _build_valid_fixture(tmp_path)
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    payload["current_claim"]["allowed"].append("live autonomy")
    payload["does_not_prove"] = ["OpenEmotion direct reply authority", "broader transport claims"]
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = verify_gate(
        baseline_path=baseline,
        report_md_path=report_md,
        report_json_path=report_json,
        ledger_path=ledger,
        status_path=status,
        readme_path=readme,
    )

    assert gate["status"] == "fail"
    assert gate["publish_gate_ready"] is False
    assert any("live autonomy" in entry for entry in gate["errors"])


def test_runner_report_payload_contains_required_fields():
    payload = build_report_payload(
        commands_run=[
            {"label": "x", "command": "pytest x", "returncode": 0, "status": "pass", "summary": "1 passed"}
        ],
        causal_payload={"status": "pass", "verification_level": "V3", "evidence_level": "E3", "pair_count": 4, "passed_count": 4},
        single_payload={
            "status": "pass",
            "verification_level": "V4",
            "evidence_level": "E4",
            "social_writeback_gate": "allow_writeback",
            "proposal_only_discipline_consistent": True,
            "behavioral_authority_none": True,
            "replay_valid": True,
        },
        batch_payload={
            "status": "pass",
            "verification_level": "V5",
            "evidence_level": "E5",
            "report_count": 3,
            "accepted_count": 3,
            "proposal_only_discipline_count": 3,
            "behavioral_authority_none_count": 3,
            "bounded_influence_present_count": 3,
        },
        generated_at="2026-04-04T12:00:00+00:00",
        git_commit_short="abc1234",
    )

    assert payload["checklist_pass_count"] == 10
    assert payload["reopen"]["decision"] == "no"
    assert "maintenance_mode" in json.dumps(payload["current_claim"], ensure_ascii=False)
    assert payload["does_not_prove"] == [
        "live autonomy",
        "OpenEmotion direct reply authority",
        "broader transport claims",
    ]
