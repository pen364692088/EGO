#!/usr/bin/env python3
"""
Run the Step08A real developmental closure check.

This script:
1. Syncs developmental projection from authoritative real Telegram samples.
2. Recomputes the current admission-grade closure status.
3. Prints a compact JSON report suitable for tomorrow's close-out run.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.developmental import (  # noqa: E402
    DEFAULT_OBSERVATION_DIR,
    DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR,
    DEFAULT_STATE_PATH,
    get_developmental_manager,
    reset_developmental_manager,
)
from tools.mvp16_daily_check import (  # noqa: E402
    STATUS_ALERT,
    STATUS_BLOCKED,
    STATUS_PASS,
    check_admission_inputs,
    check_continuity,
    check_invariants,
    check_metrics,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step08A developmental closure check.")
    parser.add_argument(
        "--sample-artifacts-dir",
        default=str(DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR),
        help="Directory containing authoritative real Telegram sample_* artifacts.",
    )
    parser.add_argument(
        "--state-path",
        default=str(DEFAULT_STATE_PATH),
        help="Path to persisted developmental_state.json.",
    )
    parser.add_argument(
        "--observation-dir",
        default=str(DEFAULT_OBSERVATION_DIR),
        help="Directory for trajectory index and replay audit artifacts.",
    )
    return parser.parse_args()


def determine_gaps(summary: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    if not summary.get("has_real_data", False):
        gaps.append("no_real_mainline_episode")
    if summary.get("real_session_count", 0) < 2:
        gaps.append("insufficient_real_sessions")
    if summary.get("real_day_count", 0) < 2:
        gaps.append("insufficient_real_days")
    if summary.get("session_reset_transition_count", 0) < 1:
        gaps.append("session_reset_transition_missing")
    if summary.get("calendar_rollover_transition_count", 0) < 1:
        gaps.append("calendar_rollover_transition_missing")
    if not summary.get("trajectory_refs_present", False):
        gaps.append("trajectory_refs_missing")
    if not summary.get("replay_refs_present", False):
        gaps.append("replay_refs_missing")
    return gaps


def determine_status(summary: Dict[str, Any]) -> str:
    if not summary.get("has_real_data", False):
        return STATUS_BLOCKED
    if summary.get("admission_inputs_present", False):
        return STATUS_PASS
    return STATUS_ALERT


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_path)
    sample_artifacts_dir = Path(args.sample_artifacts_dir)
    observation_dir = Path(args.observation_dir)

    reset_developmental_manager(state_path=state_path)
    manager = get_developmental_manager(state_path=state_path)
    sync_summary = manager.sync_real_projection_from_sample_artifacts(
        sample_artifacts_dir=sample_artifacts_dir,
        observation_dir=observation_dir,
    )

    continuity = check_continuity()
    metrics = check_metrics()
    invariants = check_invariants()
    admission_inputs = check_admission_inputs()

    closure_summary = {
        "real_episode_count": sync_summary.get("real_episode_count", 0),
        "real_session_count": sync_summary.get("real_session_count", 0),
        "real_day_count": sync_summary.get("real_day_count", 0),
        "session_reset_transition_count": sync_summary.get("session_reset_transition_count", 0),
        "calendar_rollover_transition_count": sync_summary.get("calendar_rollover_transition_count", 0),
        "trajectory_refs_present": sync_summary.get("trajectory_refs_present", False),
        "replay_refs_present": sync_summary.get("replay_refs_present", False),
        "admission_inputs_present": sync_summary.get("admission_inputs_present", False),
    }

    gaps = determine_gaps(sync_summary)
    status = determine_status(sync_summary)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "next_action": (
            "collect_next_real_calendar_day_sample_then_rerun"
            if status != STATUS_PASS
            else "ready_for_admission_retry"
        ),
        "current_gaps": gaps,
        "sample_artifacts_dir": str(sample_artifacts_dir),
        "state_path": str(state_path),
        "observation_dir": str(observation_dir),
        "sync_summary": sync_summary,
        "closure_summary": closure_summary,
        "daily_check": {
            "continuity": continuity,
            "metrics": metrics,
            "invariants": invariants,
            "admission_inputs": admission_inputs,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if status == STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
