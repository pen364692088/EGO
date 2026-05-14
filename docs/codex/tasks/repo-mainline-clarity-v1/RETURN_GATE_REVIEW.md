# Repo Mainline Clarity Return Gate Review

## Verdict

The repo has one clear mainline, but the worktree is not clean enough to treat cleanup as the next default action.

- Current mainline: `subject_system_v1_governed_proactivity`.
- Authority source: `docs/PROGRAM_STATE_UNIFIED.yaml`.
- Derived route check: `docs/codex/tasks/TASK_LANE_INDEX.md`.
- No runtime behavior changes are authorized by this review.

## Dirty Surface Owners

Use `python3 scripts/codex/audit_worktree_noise.py --json` for the current snapshot. Each category now reports `recommended_next_owner` and `top_20_paths`.

| Category | Recommended next owner | Cleanup action |
| --- | --- | --- |
| `authority_dirty` | `mainline_runtime_review` | Do not stage in cleanup. Requires authority-state review. |
| `formal_runtime_dirty` | `mainline_runtime_review` | Do not stage in cleanup. Review as EgoCore/OpenEmotion mainline runtime work. |
| `formal_evidence_dirty` | `evidence_admission` | Do not stage in cleanup. Admit or reject through evidence process. |
| `generated_or_mirror` | `evidence_admission` | Do not reconcile in cleanup. Treat as generated/mirror drift until admitted. |
| `operational_exhaust` | `operational_exhaust_policy` | Do not stage in cleanup. Later decide ignore/de-track/retention policy. |
| `untracked_unknown` | `unknown_manual_triage` | Do not stage in cleanup. Needs manual owner assignment first. |
| `cleanup_candidate` | `no_action` | Only repo-mainline-clarity helper/docs are admissible in this slice. |

## Return Gate

Default next action: stop repo cleanup and return to `subject_system_v1_governed_proactivity` fresh live recheck.

Continue cleanup only if a later task admits one narrow path class and adds a verifier for that class. Do not bundle cleanup with runtime code, formal evidence, formal authority state, generated mirrors, logs, JSONL, temp files, or unknown untracked paths.

## Staging Rule

When a repo-mainline-clarity cleanup file is staged, `verify_mainline_clarity.py` must fail if the same staged set includes:

- `EgoCore/` or `OpenEmotion/` runtime paths.
- `docs/PROGRAM_STATE_UNIFIED.yaml` or mirror authority state paths.
- `artifacts/evidence_ledger/`, formal reports, or Telegram live evidence paths.
- `temp/`, logs, runtime/session `*.jsonl`, cache, or unknown paths.

This is a cleanup guard only. It does not prevent a separate mainline-runtime or evidence-admission task from staging its own scoped files with the right acceptance proof.

## Claim Ceiling

This review proves repo readability and route discipline only. It does not prove runtime efficacy, live autonomy, consciousness, alive status, real semantic intelligence, or user benefit.
