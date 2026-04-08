from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_self_model_legacy_adapter_and_mirror_are_deleted_and_only_ledgered():
    adapter = ROOT / "OpenEmotion" / "emotiond" / "self_model_adapter.py"
    mirror = ROOT / "OpenEmotion" / "emotiond" / "self_model_mirror.py"

    assert not adapter.exists()
    assert not mirror.exists()

    decision = _read("docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md")
    readme = _read("OpenEmotion/README.md")
    logic_flow = _read("docs/CURRENT_PROJECT_LOGIC_FLOW.md")
    program_state = _read("EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml")
    path_register = _read("EgoCore/docs/05_DEPRECATED_AND_SHIMS.md")
    authority = _read("docs/codex/tasks/repo-authority-cleanup/AUTHORITY_MATRIX.md")
    caller = _read("docs/codex/tasks/repo-authority-cleanup/CALLER_MATRIX.md")
    fate = _read("docs/codex/tasks/repo-authority-cleanup/FILE_FATE_LEDGER.md")
    conflict = _read("docs/codex/tasks/repo-authority-cleanup/CONFLICT_REGISTER.md")
    import_map = _read("EgoCore/docs/generated/import_or_reference_map.csv")
    file_inventory = _read("EgoCore/docs/generated/file_inventory.csv")

    assert "## Final Fate" in decision
    assert "legacy adapter/mirror 已物理删除" in decision
    assert "legacy adapter/mirror 已删除" in readme
    assert "已从 repo 删除，不再是 formal mainline" in readme
    assert "已从 repo 删除" in logic_flow
    assert "OpenEmotion/emotiond/self_model_adapter.py" not in program_state
    assert "OpenEmotion/emotiond/self_model_mirror.py" not in program_state
    assert "| `OpenEmotion/emotiond/self_model_adapter.py` |" not in path_register
    assert "| `OpenEmotion/emotiond/self_model_mirror.py` |" not in path_register
    assert "OpenEmotion/emotiond/self_model_adapter.py" in authority
    assert "OpenEmotion/emotiond/self_model_mirror.py" in authority
    assert "deleted" in authority
    assert "OpenEmotion/tests/test_self_model_single_authority.py" in caller
    assert "OpenEmotion/tests/test_self_model_single_authority.py" in fate
    assert "OpenEmotion/emotiond/self_model_adapter.py" in caller
    assert "OpenEmotion/emotiond/self_model_mirror.py" in caller
    assert "deleted" in caller
    assert "OpenEmotion/emotiond/self_model_adapter.py" in fate
    assert "OpenEmotion/emotiond/self_model_mirror.py" in fate
    assert "deleted" in fate
    assert "resolved delete admission" in conflict
    assert ",emotiond/self_model_adapter.py," not in import_map
    assert ",emotiond/self_model_mirror.py," not in import_map
    assert "OpenEmotion/emotiond/self_model_adapter.py" not in file_inventory
    assert "OpenEmotion/emotiond/self_model_mirror.py" not in file_inventory
