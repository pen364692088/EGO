# Mainline Quickstart

## Current Mainline

The current active default lane is `ego_handmade_first_transition`.

Default operator runtime: `Ego_handmade/agent_base.py`.

Source of truth: `docs/PROGRAM_STATE_UNIFIED.yaml`.

Derived route view: `docs/codex/tasks/TASK_LANE_INDEX.md`.

## Runtime Ownership

- `Ego_handmade` owns the current operator-first runtime candidate: natural language understanding, runtime modes, transaction approval, local operator memory, trace, and human-trial reports.
- `legacy/ego-pre-handmade-mainline/EgoCore` is a legacy runtime reference and fallback source for gates, transport, replay, and audit ideas.
- `legacy/ego-pre-handmade-mainline/OpenEmotion` is a legacy subject-semantics reference and algorithm source.
- `legacy/ego-pre-handmade-mainline/ego_desktop_lab` is a legacy deterministic lab/reference harness. It is not a product runtime and must not become a second active runtime.
- New work should preserve the `user text -> LLM understanding -> proposal/plan -> gate -> trace` path. Do not reintroduce keyword-first semantic routing as the default entry.

## First 5 Files To Read

1. `docs/PROGRAM_STATE_UNIFIED.yaml`
2. `docs/MAINLINE_QUICKSTART.md`
3. `docs/codex/tasks/TASK_LANE_INDEX.md`
4. `docs/REPO_HYGIENE_POLICY.md`
5. `docs/codex/tasks/ego-mainline-demotion-v1/STATUS.md`

## Do Not Reopen By Default

- `active_inference_mainline_activation` is closed evidence, not the active implementation lane.
- MVS-aligned compact work is closed evidence, not the active implementation lane.
- `subject_system_v1_governed_proactivity` is now legacy/pre-handmade evidence, not the active default implementation lane.
- `repo_authority_cleanup` is closeout-complete; only explicit housekeeping slices should reopen cleanup.
- `thought_probe / weak-generic rebind / bare-continue repair / proactive timing / self-DM live gate` are regression evidence unless the active lane explicitly admits a new task.
- `legacy/ego-pre-handmade-mainline/ego_desktop_lab` should not become a Telegram path, GUI path, desktop executor, or third core.

## Claim Ceiling

The current transition can prove only `Ego_handmade-first repo transition / legacy demotion recorded` plus local operator-candidate behavior. It does not prove consciousness, alive status, live autonomy, runtime efficacy, stable long-term memory, or real user benefit.

## Minimal Verification

```bash
python3 scripts/codex/verify_route_convergence.py
python3 scripts/codex/verify_mainline_clarity.py
python3 -m py_compile Ego_handmade/agent_base.py Ego_handmade/memory_system.py Ego_handmade/real_use_gate.py Ego_handmade/human_operator_trial.py
TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests
```
