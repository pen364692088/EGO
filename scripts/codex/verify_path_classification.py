#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "EgoCore" / "docs" / "05_DEPRECATED_AND_SHIMS.md"

PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "EgoCore" / "README.md",
    ROOT / "OpenEmotion" / "README.md",
    ROOT / "docs" / "CURRENT_PROJECT_LOGIC_FLOW.md",
]

REQUIRED_REGISTER_ROWS = {
    "`EgoCore/app/runtime_v2/*`": "`formal`",
    "`EgoCore/app/telegram_bot.py` 中 `_handle_with_new_runtime`": "`compatibility_only`",
    "`EgoCore/app/telegram_bot.py` 中 `_handle_with_legacy_router`": "`deprecated_candidate`",
    "`OpenEmotion/openemotion/*`": "`formal`",
    "`OpenEmotion/emotiond/*`": "`reference_only`",
}

REQUIRED_PUBLIC_REFERENCES = {
    ROOT / "README.md": [
        "边界冻结下的收口期",
        "EgoCore/docs/05_DEPRECATED_AND_SHIMS.md",
    ],
    ROOT / "EgoCore" / "README.md": [
        "边界冻结下的收口期",
        "docs/05_DEPRECATED_AND_SHIMS.md",
    ],
    ROOT / "OpenEmotion" / "README.md": [
        "边界冻结下的收口期",
        "EgoCore/docs/05_DEPRECATED_AND_SHIMS.md",
    ],
    ROOT / "docs" / "CURRENT_PROJECT_LOGIC_FLOW.md": [
        "EgoCore/docs/05_DEPRECATED_AND_SHIMS.md",
        "compatibility_only",
    ],
}


def main() -> int:
    errors: list[str] = []

    if not REGISTER.exists():
        errors.append("missing EgoCore/docs/05_DEPRECATED_AND_SHIMS.md")
    else:
        text = REGISTER.read_text(encoding="utf-8")
        for row_label, classification in REQUIRED_REGISTER_ROWS.items():
            pattern = re.escape(row_label) + r".*" + re.escape(classification)
            if not re.search(pattern, text):
                errors.append(
                    f"path classification register missing required row/classification: {row_label} -> {classification}"
                )
        for classification in ("`formal`", "`compatibility_only`", "`reference_only`", "`deprecated_candidate`"):
            if classification not in text:
                errors.append(f"path classification register missing classification legend entry: {classification}")

    for path in PUBLIC_DOCS:
        if not path.exists():
            errors.append(f"missing public doc: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for required in REQUIRED_PUBLIC_REFERENCES.get(path, []):
            if required not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required path/compat reference: {required}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("path classification register gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
