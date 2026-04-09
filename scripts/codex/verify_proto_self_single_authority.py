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
PROGRAM_STATE = ROOT / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
TEST_FILE = ROOT / "OpenEmotion" / "tests" / "test_self_model_single_authority.py"
IDENTITY_TEST_FILE = ROOT / "OpenEmotion" / "tests" / "test_identity_single_authority.py"
DRIVES_WIRING_TEST = ROOT / "OpenEmotion" / "tests" / "mvp14" / "test_mainline_wiring.py"
DEVELOPMENTAL_REFERENCE_DEMOTION_TEST = ROOT / "OpenEmotion" / "tests" / "mvp16" / "test_mainline_reference_demotion.py"
DEVELOPMENTAL_OWNER_INFRA_TEST = ROOT / "OpenEmotion" / "tests" / "mvp16" / "test_developmental_owner_infra.py"
DEVELOPMENTAL_PROTO_SELF_INTEGRATION_TEST = ROOT / "OpenEmotion" / "tests" / "mvp16" / "test_developmental_proto_self_integration.py"
DEVELOPMENTAL_CAUSAL_PROOF_TEST = ROOT / "OpenEmotion" / "tests" / "mvp16" / "test_developmental_causal_formal_proof.py"
DEVELOPMENTAL_WIRING_TOOL = ROOT / "OpenEmotion" / "tools" / "verify_mvp16_mainline_wiring.py"
DELETED_PATHS = (
    ROOT / "OpenEmotion" / "emotiond" / "self_model_adapter.py",
    ROOT / "OpenEmotion" / "emotiond" / "self_model_mirror.py",
    ROOT / "EgoCore" / "app" / "openemotion_adapter" / "proto_self_restore.py",
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
        "`developmental continuity`",
        "当前 formal mainline 固定为：",
        "legacy adapter/mirror 已物理删除",
        "`OpenEmotion/emotiond/developmental_core/*`",
        "`OpenEmotion/emotiond/developmental/*`",
        "`OpenEmotion/tests/mvp16/*`",
    ],
    ROOT_README: [
        "docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
    ],
    EGOCORE_README: [
        "../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
    ],
    OPENEMOTION_README: [
        "../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
        "`self-model / drives / reflection` 的 formal owner 已接入；drives 的 compat/projection helper 与 thin re-export surfaces 已收口，v1 substrate 仍是 thin compute/proposal layer",
        "`identity invariants` 当前仍由 v1 substrate 承担 runtime authority",
        "`self-model / drives / reflection` 的 formal owner 已接入；drives 的 compat/projection helper 与 thin re-export surfaces 已收口，v1 substrate 仍是 thin compute/proposal layer",
        "`self-model / drives / reflection / developmental` 的 formal owner 已接入；drives 的 compat/projection helper 与 thin re-export surfaces 已收口，v1 substrate 仍是 thin compute/proposal layer",
        "`developmental` 的 implementation library 是 `OpenEmotion/emotiond/developmental_core/*`；live caller path 仍是 `runtime_v2/proto_self_runtime.py::_apply_developmental_self_writeback` + `proto_self_v2/developmental_self_context.py` + `proto_self_v2/developmental.py`；`emotiond/developmental/*` 仅保留为 wrapper/reference surface，`MVP16` 工具与测试只作为 proof/e2e harness",
        "legacy adapter/mirror 已删除",
        "已从 repo 删除，不再是 formal mainline",
    ],
    LOGIC_FLOW: [
        "docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
        "### 4.4 当前四类能力的单一权威收口",
        "`identity invariants` | `openemotion.proto_self.state.IdentityInvariants`",
        "formal owner 是唯一 authority；`drive_adapter.py` 只是 compat/projection helper；`emotiond/drives/*` 只是 thin compat re-export surfaces；substrate 仅保留为 thin compute/proposal layer",
        "v1 `reflection_note` 只保留 transient trigger 语义",
        "`developmental continuity` | `openemotion.developmental_self/*` | `OpenEmotion/emotiond/developmental_core/*`",
        "`OpenEmotion/emotiond/developmental/*` 只是 legacy wrapper/reference surface；`OpenEmotion/tests/mvp16/*` 与 `OpenEmotion/tools/verify_mvp16_mainline_wiring.py` 只是 proof/e2e harness",
        "已从 repo 删除",
    ],
    DEVELOPMENTAL_WIRING_TOOL: [
        "current_runtime_developmental_consumer_present_legacy_reference_only",
        "OpenEmotion/openemotion/developmental_self/*",
        "OpenEmotion/emotiond/developmental_core/*",
        "OpenEmotion/emotiond/developmental/*",
        "OpenEmotion/tests/mvp16/*",
        "OpenEmotion/tools/verify_mvp16_mainline_wiring.py",
    ],
    PATH_REGISTER: [
        "| `OpenEmotion/emotiond/drive_adapter.py` | `compatibility_only` |",
        "| `OpenEmotion/emotiond/drives/*` | `compatibility_only` |",
        "| `OpenEmotion/openemotion/identity/identity_invariants.py` | `reference_only` |",
        "| `OpenEmotion/openemotion/identity/long_term_self_summary.py` | `reference_only` |",
        "| `OpenEmotion/emotiond/reflection_adapter.py` | `reference_only` |",
        "active substrate` 也不等于 authority；单一权威收口以 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 为准",
        "- `OpenEmotion/emotiond/self_model_adapter.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger",
        "- `OpenEmotion/emotiond/self_model_mirror.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger",
        "- `EgoCore/app/openemotion_adapter/proto_self_restore.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger",
    ],
    PROGRAM_STATE: [
        "program:",
        "highest_evidence_level: \"E5\"",
        "controlled_subject_capabilities",
        "authority_source: \"docs/PROGRAM_STATE_UNIFIED.yaml\"",
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
    DEVELOPMENTAL_REFERENCE_DEMOTION_TEST: [
        'assert report["formal_owner"]["developmental_self_package_present"] is True',
        'assert report["current_runtime_mainline"]["proto_self_kernel_reads_developmental_context"] is True',
        'assert report["current_runtime_mainline"]["runtime_v2_injects_developmental_context"] is True',
        'assert report["current_runtime_mainline"]["runtime_v2_records_developmental_hooks"] is True',
        'assert report["status"] == "current_runtime_developmental_consumer_present_legacy_reference_only"',
    ],
    DEVELOPMENTAL_OWNER_INFRA_TEST: [
        'assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS',
        'assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.developmental_self"',
        'assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS',
        'assert not verdict.accepted',
        'assert "invalid_behavioral_authority:proposal_1:reply" in verdict.violations',
    ],
    DEVELOPMENTAL_PROTO_SELF_INTEGRATION_TEST: [
        'assert output.developmental_writeback_candidate is not None',
        'assert output.developmental_writeback_candidate["required_gate"] == "developmental_writeback_gate"',
        'assert output.developmental_proposal_candidates[0]["promotion_level"] == "controlled_axis"',
        'assert output.developmental_self_delta["proposal_candidate_count"] == 1',
        'assert output.trace_payload["developmental_context"]["host_hint_field"] == "runtime_summary.developmental_context"',
    ],
    DEVELOPMENTAL_CAUSAL_PROOF_TEST: [
        'assert intervention.developmental_proposal_candidates',
        'assert intervention.policy_hint["developmental_growth_bias"] == "elevated"',
        'assert intervention.developmental_writeback_candidate["behavioral_authority"] == "none"',
        'assert intervention.developmental_priority_hints["identity_preservation_guard"] == "strict"',
        'assert control.developmental_proposal_candidates == []',
    ],
    ROOT / "OpenEmotion" / "openemotion" / "self_model" / "model.py": [
        'AUTHORITY_STATUS = "formal_owner"',
        'FORMAL_MAINLINE_ENABLED = True',
        'LIVE_RUNTIME_AUTHORITY = "openemotion.self_model"',
        'ACTIVE_RUNTIME_SUBSTRATE = "openemotion.proto_self.self_model"',
    ],
    ROOT / "OpenEmotion" / "openemotion" / "developmental_self" / "__init__.py": [
        "get_developmental_self_owner",
        "reset_developmental_self_owner",
        "DevelopmentalSelfOwner",
        "REQUIRED_WRITEBACK_GATE",
        "RUNTIME_LOCAL_PROJECTION_FIELD",
    ],
    ROOT / "OpenEmotion" / "openemotion" / "proto_self_v2" / "developmental.py": [
        "from emotiond.developmental_core import",
        "def run_developmental_cycle",
        "DevelopmentalShadowState",
    ],
    ROOT / "OpenEmotion" / "openemotion" / "proto_self_v2" / "developmental_self_context.py": [
        "REQUIRED_WRITEBACK_GATE",
        "developmental_self_delta",
        "developmental_writeback_candidate",
        "runtime_summary.developmental_self_context",
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
        "OpenEmotion/openemotion/proto_self_v2/developmental_self_context.py",
        "OpenEmotion/openemotion/proto_self_v2/developmental.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        for module_prefix in ("emotiond.self_model_adapter", "emotiond.self_model_mirror"):
            if _imports_module(rel_path, module_prefix):
                errors.append(f"{rel_path} must not import legacy self-model surface {module_prefix}")

    if not DEVELOPMENTAL_REFERENCE_DEMOTION_TEST.exists():
        errors.append(
            f"missing required developmental reference demotion test: {DEVELOPMENTAL_REFERENCE_DEMOTION_TEST.relative_to(ROOT)}"
        )
    else:
        developmental_reference_text = DEVELOPMENTAL_REFERENCE_DEMOTION_TEST.read_text(encoding="utf-8")
        for snippet in CODE_REQUIRED_SNIPPETS[DEVELOPMENTAL_REFERENCE_DEMOTION_TEST]:
            if snippet not in developmental_reference_text:
                errors.append(
                    f"{DEVELOPMENTAL_REFERENCE_DEMOTION_TEST.relative_to(ROOT)} missing required developmental proof assertion: {snippet}"
                )

    for developmental_test in (
        DEVELOPMENTAL_OWNER_INFRA_TEST,
        DEVELOPMENTAL_PROTO_SELF_INTEGRATION_TEST,
        DEVELOPMENTAL_CAUSAL_PROOF_TEST,
    ):
        if not developmental_test.exists():
            errors.append(f"missing required developmental test: {developmental_test.relative_to(ROOT)}")
            continue
        developmental_text = developmental_test.read_text(encoding="utf-8")
        for snippet in CODE_REQUIRED_SNIPPETS[developmental_test]:
            if snippet not in developmental_text:
                errors.append(
                    f"{developmental_test.relative_to(ROOT)} missing required developmental authority assertion: {snippet}"
                )

    for rel_path in (
        "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
    ):
        if not _imports_module(rel_path, "openemotion.self_model"):
            errors.append(f"{rel_path} must import openemotion.self_model on the formal mainline")

    for rel_path in (
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "OpenEmotion/openemotion/proto_self_v2/developmental_self_context.py",
    ):
        if not _imports_module(rel_path, "openemotion.developmental_self"):
            errors.append(f"{rel_path} must import openemotion.developmental_self on the formal developmental mainline")

    if not _imports_module("OpenEmotion/openemotion/proto_self_v2/developmental.py", "emotiond.developmental_core"):
        errors.append(
            "OpenEmotion/openemotion/proto_self_v2/developmental.py must import emotiond.developmental_core as the live implementation library"
        )

    if _imports_module("OpenEmotion/emotiond/developmental/__init__.py", "openemotion.developmental_self"):
        errors.append(
            "OpenEmotion/emotiond/developmental/__init__.py must not import openemotion.developmental_self as a live authority surface"
        )

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
