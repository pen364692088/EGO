#!/usr/bin/env python3
"""
Static verifier for MVP16 current-runtime developmental wiring.

Purpose:
- verify the current authority source has moved to openemotion/developmental_self
- verify the current runtime mainline reads bounded developmental context
- verify legacy developmental surfaces remain reference-only or input-only

Reference surfaces intentionally kept in the text for drift checks:
- OpenEmotion/openemotion/developmental_self/*
- OpenEmotion/emotiond/developmental_core/*
- OpenEmotion/emotiond/developmental/*
- OpenEmotion/tests/mvp16/*
- OpenEmotion/tools/verify_mvp16_mainline_wiring.py
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
        "Tasks/active/mvp16_host_governed_developmental_continuity/LEGACY_REFERENCE_REGISTER.md"
    )

    developmental_modules = [
        "OpenEmotion/openemotion/developmental_self/__init__.py",
        "OpenEmotion/openemotion/developmental_self/schemas.py",
        "OpenEmotion/openemotion/developmental_self/state.py",
        "OpenEmotion/openemotion/developmental_self/store.py",
        "OpenEmotion/openemotion/developmental_self/updater.py",
        "OpenEmotion/openemotion/developmental_self/governance.py",
        "OpenEmotion/openemotion/developmental_self/intake.py",
    ]
    legacy_surfaces = [
        "OpenEmotion/emotiond/developmental/__init__.py",
        "OpenEmotion/emotiond/developmental/manager.py",
        "OpenEmotion/emotiond/developmental/schema.py",
        "OpenEmotion/emotiond/developmental_core/__init__.py",
        "OpenEmotion/tools/mvp16_daily_check.py",
        "OpenEmotion/tools/mvp16_real_trajectory_sync.py",
        "OpenEmotion/tools/mvp16_anomaly_handler.py",
        "OpenEmotion/tools/persistence_restart_experiments.py",
        "OpenEmotion/tools/causal_intervention_experiments.py",
    ]

    developmental_self_package_present = all(_exists(path) for path in developmental_modules)
    legacy_surfaces_present = {path: _exists(path) for path in legacy_surfaces}

    proto_self_kernel_reads_developmental_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.developmental_self_context import",
            "derive_developmental_outputs(",
            "summarize_runtime_developmental_self_context(",
            "extract_runtime_developmental_self_context(",
        ],
    )
    runtime_v2_injects_developmental_context = _has_any(
        runtime_text,
        [
            "def _inject_developmental_self_context(",
            "def _inject_developmental_context(",
            "\"developmental_self_context\"",
            "\"developmental_context\"",
            "developmental_self_store=",
        ],
    )
    runtime_v2_records_developmental_hooks = _has_any(
        runtime_text,
        [
            "\"developmental_self_delta\"",
            "\"developmental_proposal_candidates\"",
            "\"developmental_writeback_candidate\"",
            "\"developmental_writeback\"",
        ],
    )

    register_mentions_reference_only = all(
        needle in register_text
        for needle in [
            "OpenEmotion/emotiond/developmental/*",
            "OpenEmotion/emotiond/developmental_core/*",
            "OpenEmotion/tools/mvp16_daily_check.py",
            "OpenEmotion/tools/mvp16_real_trajectory_sync.py",
            "OpenEmotion/tools/mvp16_anomaly_handler.py",
            "OpenEmotion/tools/persistence_restart_experiments.py",
            "OpenEmotion/tools/causal_intervention_experiments.py",
            "reference-only",
            "input-only",
        ]
    )

    bounded_consumer_present = all(
        [
            developmental_self_package_present,
            proto_self_kernel_reads_developmental_context,
            runtime_v2_injects_developmental_context,
            runtime_v2_records_developmental_hooks,
        ]
    )

    if bounded_consumer_present and register_mentions_reference_only:
        status = "current_runtime_developmental_consumer_present_legacy_reference_only"
    elif bounded_consumer_present:
        status = "current_runtime_developmental_consumer_present_register_incomplete"
    elif developmental_self_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "developmental_owner_not_detected"

    return {
        "schema_version": "mvp16.mainline_wiring_check.v1",
        "root": str(ROOT),
        "formal_owner": {
            "developmental_self_package_present": developmental_self_package_present,
            "required_modules": developmental_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_developmental_context": proto_self_kernel_reads_developmental_context,
            "runtime_v2_injects_developmental_context": runtime_v2_injects_developmental_context,
            "runtime_v2_records_developmental_hooks": runtime_v2_records_developmental_hooks,
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
        help="Exit non-zero unless the current runtime developmental consumer is detected.",
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

    if args.require_current_runtime_consumer and not report["current_runtime_mainline"]["bounded_consumer_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
