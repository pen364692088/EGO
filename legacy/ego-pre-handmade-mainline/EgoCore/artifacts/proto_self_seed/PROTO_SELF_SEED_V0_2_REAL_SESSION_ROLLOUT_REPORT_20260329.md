# Proto-Self Seed v0.2 Real Session Rollout Report

- date: `2026-03-29`
- scope: `single-sample real-session rollout`
- boundary: `one real Telegram session only; not a stability or E5 claim`

## Authority Source

- `Tasks/Proto-Self_Seed/Proto-Self_Seed_v0.2_正式设计稿.md`
- `Tasks/Proto-Self_Seed/README.md`
- current formal mainline seam:
  - `telegram_bot -> native_loop -> native_hooks -> runtime_v2/proto_self_runtime -> openemotion_adapter -> openemotion.proto_self_v2`

## Live Process Binding

- live process version:
  - [LIVE_TELEGRAM_PROCESS_VERSION.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json)
- current observed live runtime:
  - `git_commit_short = 142c9bd`
  - `process_kind = telegram`
  - `pid = 49424`

## Controlled Real Session

- chat sequence:
  - `/new`
  - `/proto seed on`
  - `看看这个文件 "D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"`
- repo-tracked sample:
  - [sample_20260329_175737_7ca3cfb6](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/real_telegram/sample_20260329_175737_7ca3cfb6)
- primary ledger:
  - [ledger.json](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/real_telegram/sample_20260329_175737_7ca3cfb6/ledger.json)

## Facts Proven

- explicit profile is active on the real Telegram path:
  - `openemotion.result.subject_profile == "seed_v0_2"`
- the finalized sample preserves ingress-stage candidate evidence:
  - `openemotion_events[0].payload.candidate_actions == ["inspect_file", "continue_pending_commitment"]`
- host decision remains separate from subject candidate generation:
  - `trace_payload.executed_action.action_type == "file"`
- feedback writeback occurred:
  - `trace_payload.exec_result.status == "success"`
  - `trace_payload.exec_result.action_type == "file"`
- next-state update occurred:
  - `trace_payload.seed_state_snapshot.focus_goal.current_focus == "inspect_target"`
  - `trace_payload.seed_state_snapshot.revision_counter == 11`

## What This Closes

- real Telegram ingress reached `seed_v0_2`
- candidate generation is visible in the finalized real sample
- final host action is visible and remains host-owned
- `exec_result` writeback is visible
- next-state update is visible

This is sufficient to call:

- `real-session rollout V4 achieved`

## What This Does Not Prove

- it does not prove stability
- it does not prove multi-sample continuity
- it does not prove live E5
- it does not replace the default `proto_self.v2` path

## Validation Commands

```bash
python3 -m py_compile \
  EgoCore/app/runtime_v2/loop.py \
  EgoCore/app/runtime_v2/action_protocol.py \
  EgoCore/tests/test_runtime_v2_minimal.py
```

```bash
PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q \
  EgoCore/tests/test_runtime_v2_minimal.py \
  EgoCore/tests/test_runtime_v2_telegram_bridge.py \
  EgoCore/tests/test_runtime_v2_ws4_progress_events.py
```

```bash
python3 scripts/codex/verify_repo.py --mode fast
```

## Conclusion

- completion strength: `real-session V4 achieved`
- not claimed here:
  - `stable`
  - `E5`
  - `default path replacement`
