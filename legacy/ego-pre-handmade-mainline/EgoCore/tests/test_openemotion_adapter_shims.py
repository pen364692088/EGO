from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _imports_module(rel_path: str, module_prefix: str) -> bool:
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_prefix or alias.name.startswith(f"{module_prefix}."):
                    return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == module_prefix or module.startswith(f"{module_prefix}."):
                return True
    return False


def _module_all(rel_path: str) -> list[str]:
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel_path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return [
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
    return []


def test_proto_self_restore_is_not_reexported_from_openemotion_adapter_package():
    rel_path = "EgoCore/app/openemotion_adapter/__init__.py"

    assert _imports_module(rel_path, "app.openemotion_adapter.proto_self_restore") is False
    assert "ProtoSelfRestore" not in _module_all(rel_path)


def test_formal_mainline_files_do_not_import_restore_shim():
    for rel_path in (
        "EgoCore/app/openemotion_hooks/native_hooks.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        assert _imports_module(rel_path, "app.openemotion_adapter.proto_self_restore") is False


def test_restore_shim_file_is_deleted_and_no_longer_reexported():
    rel_path = "EgoCore/app/openemotion_adapter/proto_self_restore.py"

    assert not (REPO_ROOT / rel_path).exists()
    assert _imports_module("EgoCore/app/openemotion_adapter/__init__.py", "app.openemotion_adapter.proto_self_restore") is False
