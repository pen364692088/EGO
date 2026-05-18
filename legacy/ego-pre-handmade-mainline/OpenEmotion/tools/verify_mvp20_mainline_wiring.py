#!/usr/bin/env python3
"""
Static verifier for MVP20 current-runtime initiative wiring.

Purpose:
- verify the current authority source has moved to openemotion/initiative_self
- verify the current runtime mainline reads bounded initiative context
- verify historical proactive substrate and roadmap materials remain
  host-substrate-only or reference-only
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
        "Tasks/active/mvp20_host_governed_initiative_continuity/LEGACY_REFERENCE_REGISTER.md"
    )

    initiative_modules = [
        "OpenEmotion/openemotion/initiative_self/__init__.py",
        "OpenEmotion/openemotion/initiative_self/schemas.py",
        "OpenEmotion/openemotion/initiative_self/state.py",
        "OpenEmotion/openemotion/initiative_self/store.py",
        "OpenEmotion/openemotion/initiative_self/updater.py",
        "OpenEmotion/openemotion/initiative_self/governance.py",
    ]
    host_substrate_surfaces = [
        "EgoCore/app/runtime_v2/initiative_arbiter.py",
        "EgoCore/app/runtime_v2/initiative_scheduler.py",
        "EgoCore/app/runtime_v2/proactive_delivery.py",
        "EgoCore/app/runtime_v2/proactive_outbox.py",
        "EgoCore/app/runtime_v2/proactive_outbox_drain.py",
        "EgoCore/app/runtime_v2/proactive_telegram_policy.py",
        "EgoCore/app/runtime_v2/proactive_telegram_cycle.py",
        "EgoCore/tools/run_mvp12_proactive_followup.py",
        "EgoCore/tools/run_mvp12_idle_scheduler.py",
        "EgoCore/tools/run_mvp12_controlled_delivery.py",
        "EgoCore/tools/run_mvp12_proactive_outbox.py",
        "EgoCore/tools/run_mvp12_proactive_outbox_drain.py",
        "EgoCore/tools/run_mvp12_telegram_proactive_transport.py",
        "EgoCore/tools/run_mvp12_host_governed_proactive_telegram_cycle.py",
        "EgoCore/tools/run_mvp12_shadow_observation.py",
    ]
    roadmap_reference_surfaces = [
        "OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md",
        "OpenEmotion/roadmap/VersionRoadmap.md",
    ]

    initiative_self_package_present = all(_exists(path) for path in initiative_modules)
    host_substrate_surfaces_present = {path: _exists(path) for path in host_substrate_surfaces}
    roadmap_reference_surfaces_present = {
        path: _exists(path) for path in roadmap_reference_surfaces
    }

    proto_self_kernel_reads_initiative_context = _has_any(
        kernel_text,
        [
            "from openemotion.proto_self_v2.initiative_self_context import",
            "derive_initiative_outputs(",
            "summarize_runtime_initiative_context(",
            "extract_runtime_initiative_context(",
        ],
    )
    runtime_v2_injects_initiative_context = _has_any(
        runtime_text,
        [
            "def _inject_initiative_self_context(",
            "def _inject_initiative_context(",
            "\"initiative_self_context\"",
            "\"initiative_context\"",
            "initiative_self_store=",
        ],
    )
    runtime_v2_records_initiative_hooks = _has_any(
        runtime_text,
        [
            "\"initiative_self_delta\"",
            "\"initiative_proposal_candidates\"",
            "\"commitment_execution_snapshot\"",
            "\"initiative_policy_hints\"",
            "\"host_proactive_candidate\"",
            "\"initiative_writeback_candidate\"",
            "\"initiative_writeback\"",
        ],
    )

    host_substrate_registered = all(
        needle in register_text
        for needle in [
            *host_substrate_surfaces,
            "host_execution_substrate_reference_only",
            "host_substrate_only",
            "fallback semantic owner",
            "initiative semantics",
            "proactive transport or outbox evidence is not `WP15` causal proof",
        ]
    )
    roadmap_reference_registered = all(
        needle in register_text
        for needle in [
            *roadmap_reference_surfaces,
            "technical reference",
            "reference-only",
            "current-runtime authority",
        ]
    )

    bounded_consumer_present = all(
        [
            initiative_self_package_present,
            proto_self_kernel_reads_initiative_context,
            runtime_v2_injects_initiative_context,
            runtime_v2_records_initiative_hooks,
        ]
    )
    host_substrate_surfaces_complete = all(host_substrate_surfaces_present.values())
    roadmap_reference_surfaces_complete = all(roadmap_reference_surfaces_present.values())

    if (
        bounded_consumer_present
        and host_substrate_registered
        and roadmap_reference_registered
        and host_substrate_surfaces_complete
        and roadmap_reference_surfaces_complete
    ):
        status = "current_runtime_initiative_consumer_present_legacy_reference_only"
    elif bounded_consumer_present and host_substrate_registered and roadmap_reference_registered:
        status = "current_runtime_initiative_consumer_present_legacy_surface_missing"
    elif bounded_consumer_present:
        status = "current_runtime_initiative_consumer_present_register_incomplete"
    elif initiative_self_package_present:
        status = "formal_owner_present_runtime_consumer_missing"
    else:
        status = "initiative_owner_not_detected"

    return {
        "schema_version": "mvp20.mainline_wiring_check.v1",
        "root": str(ROOT),
        "formal_owner": {
            "initiative_self_package_present": initiative_self_package_present,
            "required_modules": initiative_modules,
        },
        "current_runtime_mainline": {
            "proto_self_kernel_reads_initiative_context": (
                proto_self_kernel_reads_initiative_context
            ),
            "runtime_v2_injects_initiative_context": runtime_v2_injects_initiative_context,
            "runtime_v2_records_initiative_hooks": runtime_v2_records_initiative_hooks,
            "bounded_consumer_present": bounded_consumer_present,
        },
        "host_substrate_reference": {
            "registered_host_substrate_only": host_substrate_registered,
            "surfaces_present": host_substrate_surfaces_present,
            "surfaces_complete": host_substrate_surfaces_complete,
        },
        "roadmap_reference": {
            "registered_reference_only": roadmap_reference_registered,
            "surfaces_present": roadmap_reference_surfaces_present,
            "surfaces_complete": roadmap_reference_surfaces_complete,
        },
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--require-current-runtime-consumer",
        action="store_true",
        help="Exit non-zero unless the current runtime initiative consumer is detected.",
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
            "host_substrate_reference.registered_host_substrate_only: "
            f"{report['host_substrate_reference']['registered_host_substrate_only']}"
        )
        print(
            "roadmap_reference.registered_reference_only: "
            f"{report['roadmap_reference']['registered_reference_only']}"
        )

    if args.require_current_runtime_consumer and not report["current_runtime_mainline"][
        "bounded_consumer_present"
    ]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
