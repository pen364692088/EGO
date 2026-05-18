#!/usr/bin/env python3
"""
Static verifier for MVP17 current-runtime social wiring.

Purpose:
- verify the current authority source has moved to openemotion/social_self
- verify the current runtime mainline reads bounded social context
- verify legacy social / relationship / repair surfaces remain reference-only or input-only
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
    register_text = _read("Tasks/active/mvp17_social_self_other_modeling/LEGACY_REFERENCE_REGISTER.md")

    social_modules = [
        "OpenEmotion/openemotion/social_self/__init__.py",
        "OpenEmotion/openemotion/social_self/schemas.py",
        "OpenEmotion/openemotion/social_self/state.py",
        "OpenEmotion/openemotion/social_self/store.py",
        "OpenEmotion/openemotion/social_self/updater.py",
        "OpenEmotion/openemotion/social_self/governance.py",
    ]
    legacy_surfaces = [
        "EgoCore/app/response/relationship_context.py",
        "EgoCore/app/handlers/social_chat_handler.py",
        "EgoCore/app/runtime/repair_context_manager.py",
        "EgoCore/app/bridges/openemotion_bridge.py",
        "OpenEmotion/emotiond/api.py",
        "OpenEmotion/emotiond/db.py",
        "OpenEmotion/emotiond/state.py",
        "OpenEmotion/emotiond/models.py",
        "OpenEmotion/emotiond/other_minds.py",
        "OpenEmotion/emotiond/persistence.py",
        "OpenEmotion/emotiond/offline_rollouts.py",
        "OpenEmotion/emotiond/memory_legacy.py",
    ]
    social_self_package_present = all(_exists(path) for path in social_modules)
    legacy_surfaces_present = {path: _exists(path) for path in legacy_surfaces}

    proto_self_kernel_reads_social_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.social_self_context import",
            "derive_social_outputs(",
            "summarize_runtime_social_self_context(",
            "extract_runtime_social_self_context(",
            "extract_runtime_social_context(",
        ],
    )
    runtime_v2_injects_social_context = _has_any(
        runtime_text,
        [
            "def _inject_social_self_context(",
            "def _inject_social_context(",
            "\"social_self_context\"",
            "\"social_context\"",
            "social_self_store=",
        ],
    )
    runtime_v2_records_social_hooks = _has_any(
        runtime_text,
        [
            "\"social_self_delta\"",
            "\"relation_update_candidates\"",
            "\"repair_proposal_candidates\"",
            "\"social_writeback_candidate\"",
            "\"social_writeback\"",
        ],
    )

    register_mentions_reference_only = all(
        needle in register_text
        for needle in [
            "EgoCore/app/response/relationship_context.py",
            "EgoCore/app/handlers/social_chat_handler.py",
            "EgoCore/app/runtime/repair_context_manager.py",
            "EgoCore/app/bridges/openemotion_bridge.py",
            "OpenEmotion/emotiond/api.py",
            "OpenEmotion/emotiond/db.py",
            "OpenEmotion/emotiond/state.py",
            "OpenEmotion/emotiond/models.py",
            "OpenEmotion/emotiond/other_minds.py",
            "OpenEmotion/emotiond/persistence.py",
            "OpenEmotion/emotiond/offline_rollouts.py",
            "OpenEmotion/emotiond/memory_legacy.py",
            "reference-only",
            "input-only",
        ]
    )

    bounded_consumer_present = all(
        [
            social_self_package_present,
            proto_self_kernel_reads_social_context,
            runtime_v2_injects_social_context,
            runtime_v2_records_social_hooks,
        ]
    )
    surfaces_present = all(legacy_surfaces_present.values())

    if bounded_consumer_present and register_mentions_reference_only and surfaces_present:
        status = "current_runtime_social_consumer_present_legacy_reference_only"
    elif bounded_consumer_present and register_mentions_reference_only:
        status = "current_runtime_social_consumer_present_legacy_surface_missing"
    elif bounded_consumer_present:
        status = "current_runtime_social_consumer_present_register_incomplete"
    elif social_self_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "social_owner_not_detected"

    return {
        "schema_version": "mvp17.mainline_wiring_check.v1",
        "root": str(ROOT),
        "formal_owner": {
            "social_self_package_present": social_self_package_present,
            "required_modules": social_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_social_context": proto_self_kernel_reads_social_context,
            "runtime_v2_injects_social_context": runtime_v2_injects_social_context,
            "runtime_v2_records_social_hooks": runtime_v2_records_social_hooks,
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
        help="Exit non-zero unless the current runtime social consumer is detected.",
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
