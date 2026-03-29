#!/usr/bin/env python3
"""
Sync MVP16 developmental projection from authoritative real-channel sample artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.developmental import (  # noqa: E402
    DEFAULT_OBSERVATION_DIR,
    DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR,
    DEFAULT_STATE_PATH,
    get_developmental_manager,
    reset_developmental_manager,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync MVP16 developmental projection from real sample artifacts.")
    parser.add_argument(
        "--sample-artifacts-dir",
        default=str(DEFAULT_REAL_SAMPLE_ARTIFACTS_DIR),
        help="Directory containing real Telegram sample_*/sample.json and ledger.json artifacts.",
    )
    parser.add_argument(
        "--state-path",
        default=str(DEFAULT_STATE_PATH),
        help="Path to OpenEmotion developmental_state.json projection file.",
    )
    parser.add_argument(
        "--observation-dir",
        default=str(DEFAULT_OBSERVATION_DIR),
        help="Directory for real_trajectory_index.json and real_trajectory_replay_audit.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_path)
    sample_artifacts_dir = Path(args.sample_artifacts_dir)
    observation_dir = Path(args.observation_dir)

    reset_developmental_manager(state_path=state_path)
    manager = get_developmental_manager(state_path=state_path)
    summary = manager.sync_real_projection_from_sample_artifacts(
        sample_artifacts_dir=sample_artifacts_dir,
        observation_dir=observation_dir,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
