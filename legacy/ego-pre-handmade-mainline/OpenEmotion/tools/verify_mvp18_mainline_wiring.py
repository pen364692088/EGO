#!/usr/bin/env python3
"""
Static verifier for MVP18 current-runtime embodied wiring.

Purpose:
- verify the current authority source has moved to openemotion/embodied_self
- verify the current runtime mainline reads bounded embodied/environment context
- verify historical consequence/intervention surfaces remain reference-only or input-only
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
    register_text = _read(
        "Tasks/active/mvp18_embodied_loop_environment_coupling/LEGACY_REFERENCE_REGISTER.md"
    )

    embodied_modules = [
        "OpenEmotion/openemotion/embodied_self/__init__.py",
        "OpenEmotion/openemotion/embodied_self/schemas.py",
        "OpenEmotion/openemotion/embodied_self/state.py",
        "OpenEmotion/openemotion/embodied_self/store.py",
        "OpenEmotion/openemotion/embodied_self/updater.py",
        "OpenEmotion/openemotion/embodied_self/governance.py",
    ]
    legacy_surfaces = [
        "OpenEmotion/roadmap/VersionRoadmap.md",
        "OpenEmotion/emotiond/consequence.py",
        "OpenEmotion/emotiond/science/interventions.py",
        "OpenEmotion/emotiond/science/science_mode.py",
    ]

    embodied_self_package_present = all(_exists(path) for path in embodied_modules)
    legacy_surfaces_present = {path: _exists(path) for path in legacy_surfaces}

    proto_self_kernel_reads_embodied_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.embodied_self_context import",
            "derive_embodied_outputs(",
            "summarize_runtime_embodied_self_context(",
            "extract_runtime_embodied_self_context(",
            "extract_runtime_environment_context(",
        ],
    )
    runtime_v2_injects_embodied_context = _has_any(
        runtime_text,
        [
            "def _inject_embodied_self_context(",
            "def _inject_environment_context(",
            "\"embodied_self_context\"",
            "\"environment_context\"",
            "embodied_self_store=",
        ],
    )
    runtime_v2_records_embodied_hooks = _has_any(
        runtime_text,
        [
            "\"embodied_self_delta\"",
            "\"consequence_update_candidates\"",
            "\"resource_boundary_snapshot\"",
            "\"repair_or_stabilize_proposal_candidates\"",
            "\"embodied_writeback_candidate\"",
            "\"embodied_writeback\"",
        ],
    )

    register_mentions_reference_only = all(
        needle in register_text
        for needle in [
            "OpenEmotion/roadmap/VersionRoadmap.md",
            "OpenEmotion/emotiond/consequence.py",
            "OpenEmotion/emotiond/science/interventions.py",
            "OpenEmotion/emotiond/science/science_mode.py",
            "technical reference",
            "reference-only",
            "input-only",
        ]
    )

    bounded_consumer_present = all(
        [
            embodied_self_package_present,
            proto_self_kernel_reads_embodied_context,
            runtime_v2_injects_embodied_context,
            runtime_v2_records_embodied_hooks,
        ]
    )
    surfaces_present = all(legacy_surfaces_present.values())

    if bounded_consumer_present and register_mentions_reference_only and surfaces_present:
        status = "current_runtime_embodied_consumer_present_legacy_reference_only"
    elif bounded_consumer_present and register_mentions_reference_only:
        status = "current_runtime_embodied_consumer_present_legacy_surface_missing"
    elif bounded_consumer_present:
        status = "current_runtime_embodied_consumer_present_register_incomplete"
    elif embodied_self_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "embodied_owner_not_detected"

    return {
        "schema_version": "mvp18.mainline_wiring_check.v1",
        "root": str(ROOT),
        "formal_owner": {
            "embodied_self_package_present": embodied_self_package_present,
            "required_modules": embodied_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_embodied_context": proto_self_kernel_reads_embodied_context,
            "runtime_v2_injects_embodied_context": runtime_v2_injects_embodied_context,
            "runtime_v2_records_embodied_hooks": runtime_v2_records_embodied_hooks,
            "bounded_consumer_present": bounded_consumer_present,
        },
        "legacy_reference": {
            "registered_reference_only": register_mentions_reference_only,
            "surfaces_present": legacy_surfaces_present,
            "surfaces_complete": surfaces_present,
        },
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--require-current-runtime-consumer",
        action="store_true",
        help="Exit non-zero unless the current runtime embodied consumer is detected.",
    )
    args = parser.parse_args()

    report = inspect_wiring()

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"status: {report['status']}")
        print(
            "current_runtime_mainline.bounded_consumer_present: "
            f"{report['current_runtime_mainline']['bounded_consumer_present']}"
        )
        print(
            "legacy_reference.registered_reference_only: "
            f"{report['legacy_reference']['registered_reference_only']}"
        )
        print(
            "legacy_reference.surfaces_complete: "
            f"{report['legacy_reference']['surfaces_complete']}"
        )

    if args.require_current_runtime_consumer and not report["current_runtime_mainline"]["bounded_consumer_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
