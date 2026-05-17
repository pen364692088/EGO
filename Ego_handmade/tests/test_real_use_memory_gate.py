from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import real_use_gate


def _prepare_tmp_gate_root(tmp_path, monkeypatch):
    monkeypatch.setattr(real_use_gate.agent, "EGO_HANDMADE_ROOT", tmp_path)
    monkeypatch.setattr(real_use_gate.agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    (tmp_path / ".gitignore").write_text("artifacts/real_use_gate/\nmemory/*.jsonl\n", encoding="utf-8")
    return tmp_path / "real_use"


def test_real_use_gate_runs_practical_scenarios(tmp_path, monkeypatch):
    out_dir = _prepare_tmp_gate_root(tmp_path, monkeypatch)

    report = real_use_gate.run_real_use_gate(out_dir)

    assert report.schema_version == "ego_handmade.real_use_memory_gate.v1"
    assert report.status == "local_candidate_pass"
    assert report.claim_ceiling == "Ego_handmade real-use memory gate local candidate pass"
    assert report.scenario_count >= 10
    assert all(obs.score == 5 for obs in report.observations)
    assert not any(obs.memory_misuse for obs in report.observations)
    assert not any(obs.operator_correction_required for obs in report.observations)


def test_real_use_gate_covers_memory_hits_and_tool_gates(tmp_path, monkeypatch):
    out_dir = _prepare_tmp_gate_root(tmp_path, monkeypatch)

    report = real_use_gate.run_real_use_gate(out_dir)
    by_id = {obs.scenario_id: obs for obs in report.observations}

    assert by_id["auto_candidate_memory"].candidate_memory_created is True
    assert by_id["hot_memory_recall"].memory_hit_ids
    assert "remember_note" in by_id["explicit_core_memory"].tool_names
    assert "read_file" in by_id["read_file"].tool_names
    assert "write_file" in by_id["write_file_blocked"].blocked_tools
    assert "web_fetch" in by_id["web_fetch_blocked"].blocked_tools
    assert "update_todos" in by_id["long_task_breakdown"].tool_names
    assert by_id["archived_memory_no_misuse"].memory_misuse is False


def test_real_use_gate_writes_json_and_markdown_reports(tmp_path, monkeypatch):
    out_dir = _prepare_tmp_gate_root(tmp_path, monkeypatch)

    report = real_use_gate.run_real_use_gate(out_dir)
    json_path, markdown_path = real_use_gate.write_real_use_report(report, out_dir)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == report.schema_version
    assert payload["status"] == "local_candidate_pass"
    assert "Ego_handmade Real Use Memory Gate v1" in markdown
    assert "memory_misuse" in markdown
    assert "ä½" not in markdown
