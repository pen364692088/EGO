# Repo Mainline Clarity v1 Phase 2B Worktree Triage

## Purpose

Phase 2B is a readability and return-gate slice. It does not move files, delete files, change runtime behavior, update `PROGRAM_STATE_UNIFIED.yaml`, or update the formal evidence ledger.

No runtime behavior changes are claimed by this triage.

## Audit Command

```bash
python3 scripts/codex/audit_worktree_noise.py --json
```

The helper is read-only. It reads `git status --porcelain=v1 -z`, classifies dirty paths, and writes JSON to stdout only.

## Current Dirty Surface

Latest local audit during the return-gate review classified `7320` dirty paths. The live count can drift as this review file changes; use the audit command above for the current snapshot.

| Category | Count | Cleanup scope | Representative paths |
| --- | ---: | --- | --- |
| `authority_dirty` | 3 | No | `docs/PROGRAM_STATE_UNIFIED.yaml`, `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`, `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` |
| `formal_evidence_dirty` | 1463 | No | `artifacts/evidence_ledger/index.yaml`, `artifacts/reports/program_state_summary.md`, `artifacts/telegram_real_mainline_v1/dashboard_v1/*` |
| `formal_runtime_dirty` | 110 | No | `EgoCore/app/*`, `EgoCore/tools/*`, `OpenEmotion/openemotion/*`, `OpenEmotion/tests/*` |
| `generated_or_mirror` | 5243 | No | `OpenEmotion/artifacts/*`, `EgoCore/docs/generated/*`, `artifacts/proto_self_mirror/*` |
| `operational_exhaust` | 226 | No | `logs/*`, `EgoCore/logs/*`, `*.jsonl`, caches, session/runtime outputs |
| `untracked_unknown` | 269 | No | untracked paths outside admitted cleanup scope |
| `cleanup_candidate` | 6 | Yes | `scripts/codex/audit_worktree_noise.py`, `scripts/codex/verify_mainline_clarity.py`, this task's Phase 2B / return-gate docs |

## Do Not Stage In Cleanup

These paths are explicitly blocked from cleanup commits:

- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `artifacts/evidence_ledger/index.yaml`
- `EgoCore/` runtime code and tests
- `OpenEmotion/` runtime code and tests
- `temp/`
- `logs/`
- runtime/session `*.jsonl`
- cache and `__pycache__/`
- API keys or host-local config
- untracked unknown paths

## Classification Notes

- `authority_dirty` means the path may affect repo authority or derived authority mirrors. It requires a separate authority-state task, not a cleanup commit.
- `formal_evidence_dirty` means the path may be part of accepted or candidate evidence. It requires evidence admission, not cleanup staging.
- `formal_runtime_dirty` means the path belongs to EgoCore/OpenEmotion or another runtime surface. It must be reviewed as mainline runtime work.
- `operational_exhaust` means logs, session stores, runtime JSONL, or cache-like outputs. This triage does not delete or de-track them.
- `generated_or_mirror` means generated status, mirror output, or observation surfaces. This triage records drift but does not reconcile it.
- `untracked_unknown` means the path is outside any admitted cleanup class. It must stay out of selective cleanup commits.
- `cleanup_candidate` is limited to the Phase 2B audit helper, verifier update, and task docs.

## Return gate

Default next action after Phase 2B: stop cleanup and return to `subject_system_v1_governed_proactivity` fresh live recheck.

Continue cleanup only if a later explicit slice admits exactly one low-risk path class and adds a verifier for it. Runtime changes, authority state changes, formal evidence changes, and operational exhaust cleanup must not be bundled with repo-mainline clarity.

See `RETURN_GATE_REVIEW.md` for the final owner mapping and staging rule.

## Claim Ceiling

This proves repo readability and route discipline only. It does not prove runtime efficacy, live autonomy, consciousness, alive status, real semantic intelligence, or user benefit.
