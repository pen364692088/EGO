#!/usr/bin/env python3
"""
Static verifier for MVP15 reflection/counterfactual mainline wiring.

Purpose:
- avoid manual grep when checking whether MVP15 is still shadow-only
- distinguish artifact generation from real mainline writeback / consumer paths
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def inspect_wiring() -> dict:
    core_text = _read("OpenEmotion/emotiond/core.py")
    api_text = _read("OpenEmotion/emotiond/api.py")
    workspace_text = _read("OpenEmotion/emotiond/workspace.py")

    reflection_engine_present = (ROOT / "OpenEmotion/emotiond/reflection_engine/engine.py").exists()
    counterfactual_module_present = (ROOT / "OpenEmotion/emotiond/self_counterfactual.py").exists()

    core_uses_reflection_shadow = "from emotiond.reflection_shadow import get_reflection_shadow" in core_text
    core_uses_reflection_adapter = _has_any(
        core_text,
        [
            "from emotiond.reflection_adapter import get_reflection_adapter",
            "_mvp15_reflection_adapter = get_reflection_adapter(",
            "_build_reflection_guidance(",
            "\"reflection_guidance\"",
        ],
    )
    core_uses_reflection_engine_directly = _has_any(
        core_text,
        [
            "from emotiond.reflection_engine import",
            "get_reflection_engine(",
            "create_reflection_job(",
            "execute_reflection(",
            "approve_proposal(",
        ],
    )
    core_uses_counterfactual_consumer = _has_any(
        core_text,
        [
            "from emotiond.self_counterfactual import",
            "get_counterfactual_model(",
            "apply_counterfactual_to_candidates(",
            "match_and_apply_counterfactual(",
        ],
    )

    api_uses_reflection_engine_directly = _has_any(
        api_text,
        [
            "from emotiond.reflection_engine import",
            "get_reflection_engine(",
            "approve_proposal(",
        ],
    )
    api_uses_counterfactual_consumer = _has_any(
        api_text,
        [
            "from emotiond.self_counterfactual import",
            "get_counterfactual_model(",
            "apply_counterfactual_to_candidates(",
            "match_and_apply_counterfactual(",
        ],
    )
    api_uses_reflection_guidance_surface = "\"reflection_guidance\"" in api_text or "'reflection_guidance'" in api_text

    workspace_uses_reflection_engine_directly = _has_any(
        workspace_text,
        [
            "from emotiond.reflection_engine import",
            "get_reflection_engine(",
            "approve_proposal(",
        ],
    )
    workspace_uses_counterfactual_consumer = _has_any(
        workspace_text,
        [
            "from emotiond.self_counterfactual import",
            "get_counterfactual_model(",
            "apply_counterfactual_to_candidates(",
            "match_and_apply_counterfactual(",
        ],
    )

    bounded_mainline_consumer_present = any(
        [
            core_uses_reflection_adapter,
            core_uses_reflection_engine_directly,
            core_uses_counterfactual_consumer,
            api_uses_reflection_guidance_surface,
            api_uses_reflection_engine_directly,
            api_uses_counterfactual_consumer,
            workspace_uses_reflection_engine_directly,
            workspace_uses_counterfactual_consumer,
        ]
    )

    if core_uses_reflection_shadow and core_uses_reflection_adapter and not (
        workspace_uses_reflection_engine_directly or workspace_uses_counterfactual_consumer
    ):
        status = "bounded_mainline_consumer_present_workspace_still_legacy"
    elif core_uses_reflection_shadow and not bounded_mainline_consumer_present:
        status = "shadow_only_mainline_writeback_missing"
    elif bounded_mainline_consumer_present:
        status = "bounded_mainline_consumer_present"
    else:
        status = "reflection_mainline_not_detected"

    return {
        "schema_version": "mvp15.mainline_wiring_check.v2",
        "root": str(ROOT),
        "formal_owner": {
            "reflection_engine_present": reflection_engine_present,
            "counterfactual_module_present": counterfactual_module_present,
        },
        "core": {
            "uses_reflection_shadow": core_uses_reflection_shadow,
            "uses_reflection_adapter": core_uses_reflection_adapter,
            "uses_reflection_engine_directly": core_uses_reflection_engine_directly,
            "uses_counterfactual_consumer": core_uses_counterfactual_consumer,
        },
        "api": {
            "uses_reflection_guidance_surface": api_uses_reflection_guidance_surface,
            "uses_reflection_engine_directly": api_uses_reflection_engine_directly,
            "uses_counterfactual_consumer": api_uses_counterfactual_consumer,
        },
        "workspace": {
            "uses_reflection_engine_directly": workspace_uses_reflection_engine_directly,
            "uses_counterfactual_consumer": workspace_uses_counterfactual_consumer,
        },
        "mainline": {
            "bounded_consumer_present": bounded_mainline_consumer_present,
        },
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--require-writeback-consumer",
        action="store_true",
        help="Exit non-zero unless a reflection/counterfactual writeback consumer is detected on the current mainline.",
    )
    args = parser.parse_args()

    report = inspect_wiring()

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"status: {report['status']}")
        print(f"core.uses_reflection_shadow: {report['core']['uses_reflection_shadow']}")
        print(f"mainline.bounded_consumer_present: {report['mainline']['bounded_consumer_present']}")

    if args.require_writeback_consumer and not report["mainline"]["bounded_consumer_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
