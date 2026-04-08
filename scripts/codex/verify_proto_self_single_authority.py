#!/usr/bin/env python3
from __future__ import annotations

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

REQUIRED_DOC_SNIPPETS = {
    DECISION_DOC: [
        "## A. Unique Authority Table",
        "## B. Keep / Downgrade / Reference-only / Delete-candidate Table",
        "## C. Minimum Change Plan",
        "`identity invariants`",
        "`self-model`",
        "`drives / appraisal`",
        "`reflection / structured revision`",
        "当前 formal mainline 固定为：",
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
        "`self-model / drives / reflection` 的 formal owner 已接入，但 v1 substrate 仍是活跃计算层",
        "`emotiond/self_model_adapter.py` 与 `emotiond/self_model_mirror.py` 不是 formal mainline",
    ],
    LOGIC_FLOW: [
        "docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md",
        "### 4.4 当前四类能力的单一权威收口",
        "`identity invariants` | `openemotion.proto_self.state.IdentityInvariants`",
        "formal owner 是唯一 authority；substrate 仍是 active compute/proposal layer",
        "v1 `reflection_note` 只保留 transient trigger 语义",
    ],
    PATH_REGISTER: [
        "| `EgoCore/app/openemotion_adapter/proto_self_restore.py` | `compatibility_only` |",
        "| `OpenEmotion/emotiond/self_model_adapter.py` | `compatibility_only` |",
        "| `OpenEmotion/emotiond/self_model_mirror.py` | `reference_only` |",
        "| `OpenEmotion/openemotion/identity/identity_invariants.py` | `reference_only` |",
        "| `OpenEmotion/openemotion/identity/long_term_self_summary.py` | `reference_only` |",
        "| `OpenEmotion/emotiond/reflection_adapter.py` | `reference_only` |",
        "active substrate` 也不等于 authority；单一权威收口以 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 为准",
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
        "| identity invariants | verified_contract | openemotion/identity/ |",
        "| SelfModelAdapter (主链 wiring) | verified_e2e | emotiond/self_model_adapter.py, docs/E2E_SELF_MODEL_ADAPTER_REPORT.md |",
        "## 当前运行时主线：Proto-Self Kernel v1",
    ],
    LOGIC_FLOW: [
        "openemotion.identity.identity_invariants 已 live",
    ],
}


def main() -> int:
    errors: list[str] = []

    for path, snippets in REQUIRED_DOC_SNIPPETS.items():
        if not path.exists():
            errors.append(f"missing required document: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required authority snippet: {snippet}")

    for path, snippets in BANNED_SNIPPETS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                errors.append(f"{path.relative_to(ROOT)} still contains banned legacy authority snippet: {snippet}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("proto-self single-authority gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
