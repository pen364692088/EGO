#!/usr/bin/env python3
"""
Static verifier for MVP19 current-runtime selfhood integration wiring.

Purpose:
- verify the current authority source has moved to openemotion/selfhood_integration
- verify the current runtime mainline reads bounded selfhood integration context
- verify upstream authority surfaces stay read-only and legacy integration materials
  stay technical-reference or reference-only
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
        "Tasks/active/mvp19_cross_axis_self_integration/LEGACY_REFERENCE_REGISTER.md"
    )

    integration_modules = [
        "OpenEmotion/openemotion/selfhood_integration/__init__.py",
        "OpenEmotion/openemotion/selfhood_integration/schemas.py",
        "OpenEmotion/openemotion/selfhood_integration/state.py",
        "OpenEmotion/openemotion/selfhood_integration/store.py",
        "OpenEmotion/openemotion/selfhood_integration/updater.py",
        "OpenEmotion/openemotion/selfhood_integration/governance.py",
    ]
    upstream_authority_surfaces = [
        "OpenEmotion/openemotion/self_model/*",
        "OpenEmotion/openemotion/endogenous_drives/*",
        "OpenEmotion/openemotion/reflective_self/*",
        "OpenEmotion/openemotion/developmental_self/*",
        "OpenEmotion/openemotion/social_self/*",
        "OpenEmotion/openemotion/embodied_self/*",
    ]
    legacy_reference_surfaces = [
        "Tasks/MVP13_task_plan.md",
        "Tasks/MVP14_task_plan.md",
        "Tasks/MVP15_task_plan.md",
        "Tasks/MVP16_task_plan.md",
        "Tasks/MVP17_task_plan.md",
        "Tasks/MVP18_task_plan.md",
        "OpenEmotion/roadmap/VersionRoadmap.md",
        "Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md",
        "Tasks/active/SELF_AWARE_STEP_08_admission_review.md",
        "Tasks/active/SELF_AWARE_STEP_08A_real_developmental_evidence_closure.md",
        "Tasks/active/SELF_AWARE_STEP_08B_admission_retry_review.md",
        "OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md",
        "OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md",
    ]

    selfhood_integration_package_present = all(_exists(path) for path in integration_modules)
    legacy_surfaces_present = {path: _exists(path) for path in legacy_reference_surfaces}

    proto_self_kernel_reads_selfhood_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.selfhood_integration_context import",
            "derive_selfhood_integration_outputs(",
            "summarize_runtime_selfhood_integration_context(",
            "extract_runtime_selfhood_integration_context(",
        ],
    )
    runtime_v2_injects_selfhood_context = _has_any(
        runtime_text,
        [
            "def _inject_selfhood_integration_context(",
            "\"selfhood_integration_context\"",
            "selfhood_integration_store=",
        ],
    )
    runtime_v2_records_selfhood_hooks = _has_any(
        runtime_text,
        [
            "\"self_integration_delta\"",
            "\"cross_axis_priority_snapshot\"",
            "\"proposal_conflict_snapshot\"",
            "\"integrated_policy_hints\"",
            "\"integrated_tendency_proposal\"",
            "\"axis_arbitration_hints\"",
            "\"self_integration_writeback_candidate\"",
            "\"selfhood_integration_writeback\"",
        ],
    )

    upstream_read_only_registered = all(
        needle in register_text
        for needle in [
            *upstream_authority_surfaces,
            "upstream_authority_read_only",
            "frozen read surface",
            "WP14 formal owner state",
            "WP14 fallback owner",
        ]
    )
    legacy_reference_registered = all(
        needle in register_text
        for needle in [
            *legacy_reference_surfaces,
            "technical reference",
            "reference-only",
            "input-only",
        ]
    )

    bounded_consumer_present = all(
        [
            selfhood_integration_package_present,
            proto_self_kernel_reads_selfhood_context,
            runtime_v2_injects_selfhood_context,
            runtime_v2_records_selfhood_hooks,
        ]
    )
    surfaces_present = all(legacy_surfaces_present.values())

    if bounded_consumer_present and upstream_read_only_registered and legacy_reference_registered and surfaces_present:
        status = "current_runtime_selfhood_consumer_present_legacy_reference_only"
    elif bounded_consumer_present and upstream_read_only_registered and legacy_reference_registered:
        status = "current_runtime_selfhood_consumer_present_legacy_surface_missing"
    elif bounded_consumer_present and upstream_read_only_registered:
        status = "current_runtime_selfhood_consumer_present_register_incomplete"
    elif bounded_consumer_present:
        status = "current_runtime_selfhood_consumer_present_read_only_map_incomplete"
    elif selfhood_integration_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "selfhood_integration_owner_not_detected"

    return {
        "schema_version": "mvp19.mainline_wiring_check.v1",
        "root": str(ROOT),
        "formal_owner": {
            "selfhood_integration_package_present": selfhood_integration_package_present,
            "required_modules": integration_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_selfhood_context": proto_self_kernel_reads_selfhood_context,
            "runtime_v2_injects_selfhood_context": runtime_v2_injects_selfhood_context,
            "runtime_v2_records_selfhood_hooks": runtime_v2_records_selfhood_hooks,
            "bounded_consumer_present": bounded_consumer_present,
        },
        "upstream_read_only_map": {
            "registered": upstream_read_only_registered,
            "required_surfaces": upstream_authority_surfaces,
        },
        "legacy_reference": {
            "registered_reference_only": legacy_reference_registered,
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
        help="Exit non-zero unless the current runtime selfhood consumer is detected.",
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
        print(f"upstream_read_only_map.registered: {report['upstream_read_only_map']['registered']}")
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
