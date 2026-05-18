#!/usr/bin/env python3
"""
Historical snapshot verifier for MVP15 reflective wiring.

Purpose:
- capture the reflective wiring state as an archive/reference-only snapshot
- verify the current runtime mainline reads bounded reflective context
- verify legacy emotiond reflection surfaces remain reference-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _exists(rel_path: str) -> bool:
    return (ROOT / rel_path).exists()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def inspect_wiring() -> dict:
    kernel_text = _read("OpenEmotion/openemotion/proto_self_v2/kernel.py")
    runtime_text = _read("EgoCore/app/runtime_v2/proto_self_runtime.py")
    register_text = _read("Tasks/active/mvp15_reflective_self_counterfactual/LEGACY_REFERENCE_REGISTER.md")

    reflective_modules = [
        "OpenEmotion/openemotion/reflective_self/__init__.py",
        "OpenEmotion/openemotion/reflective_self/schemas.py",
        "OpenEmotion/openemotion/reflective_self/state.py",
        "OpenEmotion/openemotion/reflective_self/store.py",
        "OpenEmotion/openemotion/reflective_self/updater.py",
    ]
    legacy_modules = [
        "OpenEmotion/emotiond/reflection_engine/engine.py",
        "OpenEmotion/emotiond/reflection_adapter.py",
        "OpenEmotion/emotiond/reflection_shadow.py",
        "OpenEmotion/emotiond/self_counterfactual.py",
    ]

    reflective_self_package_present = all(_exists(path) for path in reflective_modules)
    legacy_surfaces_present = {path: _exists(path) for path in legacy_modules}

    proto_self_kernel_reads_reflective_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.reflective_self_context import",
            "derive_reflective_self_outputs(",
            "summarize_runtime_reflective_self_context(",
            "extract_runtime_reflective_self_context(",
        ],
    )
    runtime_v2_injects_reflective_context = _has_any(
        runtime_text,
        [
            "def _inject_reflective_self_context(",
            "\"reflective_self_context\"",
            "reflective_self_store=",
        ],
    )
    runtime_v2_records_reflection_hooks = _has_any(
        runtime_text,
        [
            "\"reflective_self_delta\"",
            "\"revision_proposal_candidates\"",
            "\"reflection_writeback_candidate\"",
        ],
    )

    register_mentions_reference_only = all(
        needle in register_text
        for needle in [
            "OpenEmotion/emotiond/reflection_engine/*",
            "OpenEmotion/emotiond/reflection_adapter.py",
            "OpenEmotion/emotiond/reflection_shadow.py",
            "OpenEmotion/emotiond/self_counterfactual.py",
            "reference-only",
        ]
    )

    bounded_consumer_present = all(
        [
            reflective_self_package_present,
            proto_self_kernel_reads_reflective_context,
            runtime_v2_injects_reflective_context,
            runtime_v2_records_reflection_hooks,
        ]
    )

    if bounded_consumer_present and register_mentions_reference_only:
        status = "current_runtime_reflective_consumer_present_legacy_reference_only"
    elif bounded_consumer_present:
        status = "current_runtime_reflective_consumer_present_register_incomplete"
    elif reflective_self_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "reflective_owner_not_detected"

    return {
        "schema_version": "mvp15.mainline_wiring_check.v3",
        "root": str(ROOT),
        "formal_owner": {
            "reflective_self_package_present": reflective_self_package_present,
            "required_modules": reflective_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_reflective_context": proto_self_kernel_reads_reflective_context,
            "runtime_v2_injects_reflective_context": runtime_v2_injects_reflective_context,
            "runtime_v2_records_reflection_hooks": runtime_v2_records_reflection_hooks,
            "bounded_consumer_present": bounded_consumer_present,
        },
        "legacy_reference": {
            "registered_reference_only": register_mentions_reference_only,
            "surfaces_present": legacy_surfaces_present,
        },
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--require-current-runtime-consumer",
        action="store_true",
        help="Exit non-zero unless the current runtime reflective consumer is detected.",
    )
    args = parser.parse_args()

    report = inspect_wiring()

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"status: {report['status']}")
        print("surface_role: archive/reference-only historical snapshot")
        print(
            "current_runtime_mainline.bounded_consumer_present: "
            f"{report['current_runtime_mainline']['bounded_consumer_present']}"
        )
        print(
            "legacy_reference.registered_reference_only: "
            f"{report['legacy_reference']['registered_reference_only']}"
        )

    if args.require_current_runtime_consumer and not report["current_runtime_mainline"]["bounded_consumer_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
