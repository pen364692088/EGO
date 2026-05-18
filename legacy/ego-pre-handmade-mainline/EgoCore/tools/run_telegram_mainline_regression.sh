#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=".:modules:..:../OpenEmotion${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -s \
  tests/test_telegram_failure_case_replay.py \
  tests/test_telegram_artifact_confirmation_flow.py \
  tests/test_runtime_v2_telegram_bridge.py \
  tests/test_telegram_bot_native_switch.py \
  tests/test_runtime_v2_ws2_target_binding.py \
  tests/test_runtime_v2_ws3_intent_guess.py \
  tests/test_runtime_v2_parse_and_challenge.py \
  tests/test_telegram_session_commands.py \
  tests/test_telegram_context_command.py \
  -q
