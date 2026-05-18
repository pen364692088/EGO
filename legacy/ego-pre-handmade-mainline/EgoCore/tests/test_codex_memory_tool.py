from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "codex_memory.py"
    spec = importlib.util.spec_from_file_location("codex_memory_tool", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, records: list[dict]) -> None:
    content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    path.write_text(content, encoding="utf-8")


def test_render_index_contains_truths_and_preferences(tmp_path):
    module = _load_module()
    workspace = module.CodexMemoryWorkspace(tmp_path)
    workspace.ensure_layout()

    _write_jsonl(
        workspace.project_truth_path,
        [
            {
                "record_id": "truth-1",
                "scope": "project",
                "title": "Boundary",
                "content": "EgoCore owns runtime.",
                "source_type": "repo_file",
                "source_ref": "PROJECT_MEMORY.md#系统边界",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "revalidate_when_boundary_changes",
            }
        ],
    )
    _write_jsonl(
        workspace.user_preferences_path,
        [
            {
                "record_id": "pref-1",
                "scope": "preference",
                "title": "Auto push",
                "content": "Push after verified commits.",
                "source_type": "user_confirmation",
                "source_ref": "user_confirmation:test:auto_push",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "until_user_overrides",
            }
        ],
    )

    rendered = workspace.render_index()
    assert "Boundary" in rendered
    assert "Auto push" in rendered
    assert "当前任务 handoff" in rendered


def test_validate_rejects_missing_source_ref(tmp_path):
    module = _load_module()
    workspace = module.CodexMemoryWorkspace(tmp_path)
    workspace.ensure_layout()

    _write_jsonl(
        workspace.project_truth_path,
        [
            {
                "record_id": "truth-1",
                "scope": "project",
                "title": "Boundary",
                "content": "EgoCore owns runtime.",
                "source_type": "repo_file",
                "source_ref": "",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "revalidate_when_boundary_changes",
            }
        ],
    )
    _write_jsonl(
        workspace.user_preferences_path,
        [
            {
                "record_id": "pref-1",
                "scope": "preference",
                "title": "Auto push",
                "content": "Push after verified commits.",
                "source_type": "user_confirmation",
                "source_ref": "user_confirmation:test:auto_push",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "until_user_overrides",
            }
        ],
    )

    errors = workspace.validate()
    assert any("missing `source_ref`" in error for error in errors)


def test_create_task_handoff_and_bootstrap_bundle(tmp_path):
    module = _load_module()
    workspace = module.CodexMemoryWorkspace(tmp_path)
    workspace.ensure_layout()

    _write_jsonl(
        workspace.project_truth_path,
        [
            {
                "record_id": "truth-1",
                "scope": "project",
                "title": "Boundary",
                "content": "EgoCore owns runtime.",
                "source_type": "repo_file",
                "source_ref": "PROJECT_MEMORY.md#系统边界",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "revalidate_when_boundary_changes",
            }
        ],
    )
    _write_jsonl(
        workspace.user_preferences_path,
        [
            {
                "record_id": "pref-1",
                "scope": "preference",
                "title": "Auto push",
                "content": "Push after verified commits.",
                "source_type": "user_confirmation",
                "source_ref": "user_confirmation:test:auto_push",
                "last_verified_at": "2026-03-27T00:00:00Z",
                "owner": "codex",
                "expiry_or_revalidate_rule": "until_user_overrides",
            }
        ],
    )
    workspace.write_index()

    task_path = workspace.create_task_handoff(
        task_id="L2-TEST-001",
        title="Restore continuity polish",
        source_ref="Tasks/active/L2-TEST-001.md",
    )
    closure_path = workspace.create_task_closure(
        task_id="L2-TEST-000",
        title="Previous task",
        source_ref="Tasks/archive/L2-TEST-000.md",
    )

    bundle = workspace.build_bootstrap_bundle(
        task_record=task_path,
        previous_closure=closure_path,
    )

    assert "L2-TEST-001.json" in bundle
    assert "CODEX_MEMORY.md" in bundle
    assert "L2-TEST-000-closure.json" in bundle
