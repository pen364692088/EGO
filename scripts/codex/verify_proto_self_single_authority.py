#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_DOC = ROOT / "docs" / "PROTO_SELF_SINGLE_AUTHORITY_DECISION.md"
ROOT_README = ROOT / "README.md"
EGOCORE_README = ROOT / "EgoCore" / "README.md"
OPENEMOTION_README = ROOT / "OpenEmotion" / "README.md"
LOGIC_FLOW = ROOT / "docs" / "CURRENT_PROJECT_LOGIC_FLOW.md"
PATH_REGISTER = ROOT / "EgoCore" / "docs" / "05_DEPRECATED_AND_SHIMS.md"
CAPABILITY_REGISTRY = ROOT / "docs" / "CAPABILITY_REGISTRY.md"
PROGRAM_STATE = ROOT / "EgoCore" / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
TEST_FILE = ROOT / "OpenEmotion" / "tests" / "test_self_model_single_authority.py"
IDENTITY_TEST_FILE = ROOT / "OpenEmotion" / "tests" / "test_identity_single_authority.py"
DRIVES_WIRING_TEST = ROOT / "OpenEmotion" / "tests" / "mvp14" / "test_mainline_wiring.py"
DELETED_PATHS = (
    ROOT / "OpenEmotion" / "emotiond" / "self_model_adapter.py",
    ROOT / "OpenEmotion" / "emotiond" / "self_model_mirror.py",
)

REQUIRED_DOC_SNIPPETS = {
    DECISION_DOC: [
        "## A. Unique Authority Table",
        "## B. Keep / Downgrade / Reference-only / Delete-candidate Table",
        "## C. Minimum Change Plan",
        "## Final Fate",
        "`identity invariants`",
        "`self-model`",
        "`drives / appraisal`",
        "`reflection / structured revision`",
        "当前 formal mainline 固定为：",
        "legacy adapter/mirror 已物理删除",
    ],
    ROOT_README: [
        "docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
    ],
    EGOCORE_README: [
        "../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
    ],
    OPENEMOTION_README: [
        "../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
        "`identity invariants` 当前仍由 v1 substrate 承担 runtime authority",
        "`self-model / drives / reflection` 的 formal owner 已接入；drives 的 compat/projection helper 与 thin re-export surfaces 已收口，v1 substrate 仍是 thin compute/proposal layer",
        "legacy adapter/mirror 已删除",
        "已从 repo 删除，不再是 formal mainline",
    ],
    LOGIC_FLOW: [
        "docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
        "### 4.4 当前四类能力的单一权威收口",
        "`identity invariants` | `openemotion.proto_self.state.IdentityInvariants`",
        "formal owner 是唯一 authority；`drive_adapter.py` 只是 compat/projection helper；`emotiond/drives/*` 只是 thin compat re-export surfaces；substrate 仅保留为 thin compute/proposal layer",
        "v1 `reflection_note` 只保留 transient trigger 语义",
        "已从 repo 删除",
    ],
    PATH_REGISTER: [
        "| `EgoCore/app/openemotion_adapter/proto_self_restore.py` | `compatibility_only` |",
        "| `OpenEmotion/emotiond/drive_adapter.py` | `compatibility_only` |",
        "| `OpenEmotion/emotiond/drives/*` | `compatibility_only` |",
        "| `OpenEmotion/openemotion/identity/identity_invariants.py` | `reference_only` |",
        "| `OpenEmotion/openemotion/identity/long_term_self_summary.py` | `reference_only` |",
        "| `OpenEmotion/emotiond/reflection_adapter.py` | `reference_only` |",
        "active substrate` 也不等于 authority；单一权威收口以 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 为准",
        "- `OpenEmotion/emotiond/self_model_adapter.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger",
        "- `OpenEmotion/emotiond/self_model_mirror.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger",
    ],
    PROGRAM_STATE: [
        "formal owner is openemotion/endogenous_drives/*",
        "`emotiond/drives/*` remains thin compat re-export surface",
        "thin rather than authoritative",
    ],
    CAPABILITY_REGISTRY: [
        "| identity invariants authority surface |",
        "| self-model authority surface |",
        "| drives / appraisal authority surface |",
        "| reflection / structured revision authority surface |",
    ],
}

BANNED_SNIPPETS = {
    OPENEMOTION_README: [
        "| SelfModelAdapter (主链 wiring) | verified_e2e | emotiond/self_model_adapter.py, docs/E2E_SELF_MODEL_ADAPTER_REPORT.md |",
        "## 当前运行时主线：Proto-Self Kernel v1",
        "`self_model_adapter.py` 与 `self_model_mirror.py` 已从 repo 删除",
    ],
    LOGIC_FLOW: [
        "openemotion.identity.identity_invariants 已 live",
        "legacy adapter/mirror 已从 repo 删除",
    ],
    PROGRAM_STATE: [
        "formal owner remains emotiond/drives/*",
    ],
}

CODE_REQUIRED_SNIPPETS = {
    TEST_FILE: [
        'assert not adapter.exists()',
        'assert not mirror.exists()',
        'assert "legacy adapter/mirror 已物理删除" in decision',
        'assert "resolved delete admission" in conflict',
        'assert "legacy adapter/mirror 已删除" in readme',
    ],
    IDENTITY_TEST_FILE: [
        'assert PACKAGE_AUTHORITY_STATUS == "reference_only"',
        'assert PACKAGE_FORMAL_MAINLINE_ENABLED is False',
        'assert PACKAGE_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"',
        'assert IDENTITY_INVARIANTS_AUTHORITY_STATUS == "reference_only"',
        'assert IDENTITY_INVARIANTS_FORMAL_MAINLINE_ENABLED is False',
        'assert IDENTITY_INVARIANTS_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"',
        'assert LONG_TERM_SELF_SUMMARY_AUTHORITY_STATUS == "reference_only"',
        'assert LONG_TERM_SELF_SUMMARY_FORMAL_MAINLINE_ENABLED is False',
        'assert LONG_TERM_SELF_SUMMARY_LIVE_RUNTIME_AUTHORITY == "openemotion.proto_self.state.IdentityInvariants"',
        'assert _imports_module(',
        'OpenEmotion/openemotion/proto_self_v2/kernel.py',
        'OpenEmotion/openemotion/proto_self_v2/state.py',
        'EgoCore/app/openemotion_hooks/native_hooks.py',
        'EgoCore/app/openemotion_adapter/proto_self_adapter.py',
        'EgoCore/app/runtime_v2/proto_self_runtime.py',
        '"openemotion.identity"',
    ],
    DRIVES_WIRING_TEST: [
        'assert LegacyDriveManager is FormalDriveManager',
        'assert LegacyManagerModuleDriveManager is FormalDriveManager',
        'assert "_FORMAL_OWNER_ACTION_WEIGHTS" not in core_text',
        'assert "ACTION_DRIVE_WEIGHTS =" not in adapter_text',
        'assert "compute_action_bias_from_priority_snapshot" in core_text',
        'assert "compute_action_bias_from_priority_snapshot" in adapter_text',
        'assert "ACTION_DRIVE_WEIGHTS" in helper_text',
    ],
    ROOT / "OpenEmotion" / "openemotion" / "self_model" / "model.py": [
        'AUTHORITY_STATUS = "formal_owner"',
        'FORMAL_MAINLINE_ENABLED = True',
        'LIVE_RUNTIME_AUTHORITY = "openemotion.self_model"',
        'ACTIVE_RUNTIME_SUBSTRATE = "openemotion.proto_self.self_model"',
    ],
    ROOT / "OpenEmotion" / "openemotion" / "endogenous_drives" / "action_bias.py": [
        "ACTION_DRIVE_WEIGHTS",
        "compute_action_bias_from_priority_snapshot",
    ],
    ROOT / "OpenEmotion" / "emotiond" / "drive_adapter.py": [
        "from openemotion.endogenous_drives.action_bias import compute_action_bias_from_priority_snapshot",
        "from emotiond.drives import get_drive_manager",
    ],
    ROOT / "OpenEmotion" / "emotiond" / "drives" / "__init__.py": [
        "The formal authority lives in ``openemotion.endogenous_drives``.",
        "thin re-exports",
    ],
    ROOT / "OpenEmotion" / "emotiond" / "drives" / "manager.py": [
        "DriveManager = _FormalDriveManager",
        "from openemotion.endogenous_drives import DriveManager as _FormalDriveManager",
    ],
    ROOT / "OpenEmotion" / "emotiond" / "drives" / "schema.py": [
        "thin re-export of the formal owner package",
    ],
    ROOT / "OpenEmotion" / "emotiond" / "drives" / "integration.py": [
        "The formal owner lives in ``openemotion.endogenous_drives``.",
        "historical integration API alive while avoiding a second drive authority",
    ],
}

BANNED_DOC_SNIPPETS = {
    PROGRAM_STATE: [
        "formal owner remains emotiond/drives/*",
    ],
}


def _imports_module(rel_path: str, module_prefix: str) -> bool:
    source = (ROOT / rel_path).read_text(encoding="utf-8")
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


def main() -> int:
    errors: list[str] = []

    for path in DELETED_PATHS:
        if path.exists():
            errors.append(f"deleted path still exists on disk: {path.relative_to(ROOT)}")

    for path, snippets in REQUIRED_DOC_SNIPPETS.items():
        if not path.exists():
            errors.append(f"missing required document: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required authority snippet: {snippet}")

    for path, snippets in BANNED_DOC_SNIPPETS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                errors.append(f"{path.relative_to(ROOT)} still contains banned legacy authority snippet: {snippet}")

    for path, snippets in BANNED_SNIPPETS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                errors.append(f"{path.relative_to(ROOT)} still contains banned legacy authority snippet: {snippet}")

    for path, snippets in CODE_REQUIRED_SNIPPETS.items():
        if not path.exists():
            errors.append(f"missing required code surface: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required authority constant: {snippet}")

    if not IDENTITY_TEST_FILE.exists():
        errors.append(f"missing required admission test: {IDENTITY_TEST_FILE.relative_to(ROOT)}")
    else:
        identity_text = IDENTITY_TEST_FILE.read_text(encoding="utf-8")
        for snippet in CODE_REQUIRED_SNIPPETS[IDENTITY_TEST_FILE]:
            if snippet not in identity_text:
                errors.append(f"{IDENTITY_TEST_FILE.relative_to(ROOT)} missing required identity authority assertion: {snippet}")

    if not TEST_FILE.exists():
        errors.append(f"missing required admission test: {TEST_FILE.relative_to(ROOT)}")
    else:
        if _imports_module(str(TEST_FILE.relative_to(ROOT)), "emotiond.self_model_adapter"):
            errors.append(f"{TEST_FILE.relative_to(ROOT)} must not import legacy self-model surface emotiond.self_model_adapter")
        if _imports_module(str(TEST_FILE.relative_to(ROOT)), "emotiond.self_model_mirror"):
            errors.append(f"{TEST_FILE.relative_to(ROOT)} must not import legacy self-model surface emotiond.self_model_mirror")

    for rel_path in (
        "OpenEmotion/openemotion/proto_self_v2/kernel.py",
        "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        for module_prefix in ("emotiond.self_model_adapter", "emotiond.self_model_mirror"):
            if _imports_module(rel_path, module_prefix):
                errors.append(f"{rel_path} must not import legacy self-model surface {module_prefix}")

    for rel_path in (
        "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
    ):
        if not _imports_module(rel_path, "openemotion.self_model"):
            errors.append(f"{rel_path} must import openemotion.self_model on the formal mainline")

    for rel_path in (
        "OpenEmotion/openemotion/proto_self_v2/kernel.py",
        "OpenEmotion/openemotion/proto_self_v2/endogenous_drive_context.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        for module_prefix in ("emotiond.drive_adapter", "emotiond.drives"):
            if _imports_module(rel_path, module_prefix):
                errors.append(f"{rel_path} must not import legacy drives surface {module_prefix}")

    if not _imports_module("EgoCore/app/runtime_v2/proto_self_runtime.py", "openemotion.endogenous_drives"):
        errors.append(
            "EgoCore/app/runtime_v2/proto_self_runtime.py must import openemotion.endogenous_drives on the formal mainline"
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("proto-self single-authority gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
