from __future__ import annotations

import ast
from pathlib import Path

from openemotion.identity import (
    IDENTITY_INVARIANTS_AUTHORITY_STATUS,
    IDENTITY_INVARIANTS_FORMAL_MAINLINE_ENABLED,
    IDENTITY_INVARIANTS_LIVE_RUNTIME_AUTHORITY,
    LONG_TERM_SELF_SUMMARY_AUTHORITY_STATUS,
    LONG_TERM_SELF_SUMMARY_FORMAL_MAINLINE_ENABLED,
    LONG_TERM_SELF_SUMMARY_LIVE_RUNTIME_AUTHORITY,
    PACKAGE_AUTHORITY_STATUS,
    PACKAGE_FORMAL_MAINLINE_ENABLED,
    PACKAGE_LIVE_RUNTIME_AUTHORITY,
)
from openemotion.proto_self.state import IdentityInvariants as RuntimeIdentityInvariants
from openemotion.proto_self_v2.state import ProtoSelfStateV2


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


def test_identity_reference_surfaces_are_explicitly_non_mainline():
    assert PACKAGE_AUTHORITY_STATUS == "reference_only"
    assert PACKAGE_FORMAL_MAINLINE_ENABLED is False
    assert PACKAGE_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"

    assert IDENTITY_INVARIANTS_AUTHORITY_STATUS == "reference_only"
    assert IDENTITY_INVARIANTS_FORMAL_MAINLINE_ENABLED is False
    assert IDENTITY_INVARIANTS_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"

    assert LONG_TERM_SELF_SUMMARY_AUTHORITY_STATUS == "reference_only"
    assert LONG_TERM_SELF_SUMMARY_FORMAL_MAINLINE_ENABLED is False
    assert LONG_TERM_SELF_SUMMARY_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"


def test_proto_self_v2_identity_projection_still_uses_runtime_identity_authority():
    identity_field = ProtoSelfStateV2.__dataclass_fields__["identity"]

    assert identity_field.default_factory is RuntimeIdentityInvariants


def test_formal_mainline_does_not_import_reference_only_identity_owner():
    assert _imports_module(
        "OpenEmotion/openemotion/proto_self_v2/kernel.py",
        "openemotion.identity",
    ) is False
    assert _imports_module(
        "OpenEmotion/openemotion/proto_self_v2/state.py",
        "openemotion.identity",
    ) is False


def test_egocore_does_not_take_identity_runtime_ownership():
    assert _imports_module(
        "EgoCore/app/openemotion_hooks/native_hooks.py",
        "openemotion.identity",
    ) is False
    assert _imports_module(
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
        "openemotion.identity",
    ) is False
    assert _imports_module(
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "openemotion.identity",
    ) is False
