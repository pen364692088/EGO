from __future__ import annotations

from pathlib import Path

from app.dashboard.stage1_evidence import (
    build_dashboard_artifact_manifest,
    build_stage1_entrypoint_comparative_audit,
)


def test_build_stage1_entrypoint_comparative_audit_keeps_preflight_out_of_live_counts() -> None:
    report = build_stage1_entrypoint_comparative_audit(
        preflight_report={
            "claim_ceiling": "bounded_local_proof",
            "entrypoint_contract": {"entrypoint": "dashboard_chat"},
            "summary": {
                "total_samples": 3,
                "mainline_candidate_total": 2,
                "host_only_total": 1,
                "verdict": "mainline_candidate_reply_sample_present",
            },
        },
        preflight_artifact="artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_INGRESS_REPLY_SAMPLE_PREFLIGHT_CURRENT.json",
        live_window_reports=[
            {
                "artifact_path": "artifacts/telegram_real_mainline_v1/dashboard_v1/DASHBOARD_LIVE_SESSION_EXPORT_CURRENT.json",
                "report": {
                    "claim_ceiling": "single_entry_live_window_observation",
                    "entrypoint_contract": {"entrypoint": "dashboard_chat"},
                    "summary": {
                        "ordinary_chat_turn_count": 5,
                        "execute_task_turn_count": 2,
                        "subject_gate_ok_count": 7,
                        "oe_available_count": 7,
                        "mainline_candidate_count": 5,
                        "host_only_count": 0,
                        "degraded_count": 0,
                        "source_counts": {
                            "repo_authored_control": 2,
                            "generated": 2,
                            "chatlog_curated": 1,
                        },
                        "verdict": "ordinary_chat_mainline_observed",
                    },
                },
            }
        ],
        subject_mainline_audit={
            "entrypoint_contract": {"accepted_stage1_entrypoints": ["telegram", "dashboard_chat"]},
            "stage1_activation_lens": {"mainline_candidate_unexpected_miss_total": 9},
        },
        subject_mainline_artifact="artifacts/telegram_real_mainline_v1/dashboard_v1/SUBJECT_MAINLINE_AUDIT_CURRENT.json",
    )

    comparative = report["evidence_ladder"]["comparative_audit"]
    row = comparative["rows"][0]

    assert report["claim_ceiling"] == "comparative_audit_partial"
    assert report["evidence_ladder"]["bounded_preflight"]["claim_ceiling"] == "bounded_local_proof"
    assert comparative["preflight_excluded_from_live_counts"] is True
    assert comparative["verdict"] == "single_entry_live_window_present__cross_entry_pending"
    assert row["entrypoint"] == "dashboard_chat"
    assert row["ordinary_chat_turn_count"] == 5
    assert row["source_counts"]["chatlog_curated"] == 1
    assert comparative["live_window_aggregate"]["ordinary_chat_turn_count"] == 5
    assert comparative["live_window_aggregate"]["host_only_count"] == 0
    assert comparative["live_window_source_counts"]["repo_authored_control"] == 2
    assert report["supporting_context"]["subject_mainline_audit_reference"]["telegram_mainline_candidate_unexpected_miss_total"] == 9


def test_build_stage1_entrypoint_comparative_audit_marks_multi_window_single_entry_history() -> None:
    report = build_stage1_entrypoint_comparative_audit(
        preflight_report=None,
        preflight_artifact=None,
        live_window_reports=[
            {
                "artifact_path": "artifacts/telegram_real_mainline_v1/dashboard_v1/historical/reference/live_session_exports/DASHBOARD_LIVE_SESSION_EXPORT_20260413T003336Z.json",
                "report": {
                    "claim_ceiling": "single_entry_live_window_observation",
                    "entrypoint_contract": {"entrypoint": "dashboard_chat"},
                    "summary": {
                        "ordinary_chat_turn_count": 5,
                        "execute_task_turn_count": 0,
                        "subject_gate_ok_count": 5,
                        "oe_available_count": 5,
                        "mainline_candidate_count": 5,
                        "host_only_count": 0,
                        "degraded_count": 0,
                        "source_counts": {
                            "repo_authored_control": 2,
                            "generated": 2,
                            "chatlog_curated": 1,
                        },
                        "verdict": "ordinary_chat_mainline_observed",
                    },
                },
            },
            {
                "artifact_path": "artifacts/telegram_real_mainline_v1/dashboard_v1/DASHBOARD_LIVE_SESSION_EXPORT_CURRENT.json",
                "report": {
                    "claim_ceiling": "single_entry_live_window_observation",
                    "entrypoint_contract": {"entrypoint": "dashboard_chat"},
                    "summary": {
                        "ordinary_chat_turn_count": 4,
                        "execute_task_turn_count": 1,
                        "subject_gate_ok_count": 5,
                        "oe_available_count": 5,
                        "mainline_candidate_count": 4,
                        "host_only_count": 0,
                        "degraded_count": 0,
                        "source_counts": {
                            "repo_authored_control": 2,
                            "generated": 3,
                        },
                        "verdict": "ordinary_chat_mainline_observed",
                    },
                },
            },
        ],
        subject_mainline_audit=None,
        subject_mainline_artifact=None,
    )

    comparative = report["evidence_ladder"]["comparative_audit"]

    assert comparative["verdict"] == "single_entry_multi_window_present__cross_entry_pending"
    assert comparative["entrypoint_count"] == 1
    assert comparative["live_window_aggregate"]["ordinary_chat_turn_count"] == 9
    assert comparative["live_window_aggregate"]["execute_task_turn_count"] == 1
    assert comparative["live_window_aggregate"]["host_only_count"] == 0
    assert comparative["live_window_source_counts"]["generated"] == 5
    assert comparative["source_mix_summary"]["mixed_source_window_count"] == 2


def test_build_stage1_entrypoint_comparative_audit_relabels_zero_gate_window() -> None:
    report = build_stage1_entrypoint_comparative_audit(
        preflight_report=None,
        preflight_artifact=None,
        live_window_reports=[
            {
                "artifact_path": "artifacts/telegram_real_mainline_v1/dashboard_v1/historical/reference/live_session_exports/DASHBOARD_LIVE_SESSION_EXPORT_20260413T030103Z.json",
                "report": {
                    "claim_ceiling": "single_entry_live_window_observation",
                    "entrypoint_contract": {"entrypoint": "dashboard_chat"},
                    "summary": {
                        "ordinary_chat_turn_count": 5,
                        "execute_task_turn_count": 0,
                        "subject_gate_ok_count": 0,
                        "oe_available_count": 0,
                        "mainline_candidate_count": 0,
                        "host_only_count": 0,
                        "degraded_count": 0,
                        "source_counts": {
                            "repo_authored_control": 2,
                            "generated": 2,
                            "chatlog_curated": 1,
                        },
                        "verdict": "ordinary_chat_mainline_observed",
                    },
                },
            }
        ],
        subject_mainline_audit=None,
        subject_mainline_artifact=None,
    )

    row = report["evidence_ladder"]["comparative_audit"]["rows"][0]

    assert row["ordinary_chat_turn_count"] == 5
    assert row["mainline_candidate_count"] == 0
    assert row["verdict"] == "ordinary_chat_window_present__mainline_not_observed"


def test_build_dashboard_artifact_manifest_classifies_legacy_inventory(tmp_path: Path) -> None:
    for name in [
        "README.md",
        "runs.jsonl",
        "UNIFIED_INGRESS_REPLY_SAMPLE_PREFLIGHT_CURRENT.json",
        "DASHBOARD_LIVE_SESSION_EXPORT_CURRENT.json",
        "PLASTICITY_REFLECTION_EVIDENCE.md",
    ]:
        (tmp_path / name).write_text("{}\n", encoding="utf-8")

    manifest = build_dashboard_artifact_manifest(tmp_path)

    assert manifest["inventory_scope"] == "legacy_top_level_inventory"
    assert manifest["category_counts"]["baseline_indexes"] == 1
    assert manifest["category_counts"]["bounded_preflight"] == 1
    assert manifest["category_counts"]["single_entry_live_windows"] == 1
    assert manifest["category_counts"]["acceptance_reports"] == 1
    assert manifest["category_counts"]["historical/reference"] == 1
    assert manifest["unclassified_files"] == []
