# Repo Mainline Clarity v1 Status

## Current Milestone

`final_return_gate_review`

## Status

`verify_passed`

## Current Slice

This slice closes the cleanup-oriented loop by mapping remaining dirty categories to next owners and by guarding repo-mainline-clarity cleanup staging against runtime/evidence/state/exhaust mixing.

## Does Not Change

- No runtime behavior.
- No new archive move or archive class.
- No split-repo migration.
- No `PROGRAM_STATE_UNIFIED.yaml` update.
- No formal evidence ledger update.

## Completion Criteria

- `README.md` points new agents to `docs/MAINLINE_QUICKSTART.md`. Passed.
- `docs/REPO_SURFACE_MAP.md` is generated and verified. Passed.
- `verify_mainline_clarity.py` passes. Passed.
- `verify_route_convergence.py` still proves exactly one active default lane. Passed.
- `verify_repo.py --mode fast` includes the mainline clarity gate. Passed.
- Archived docs and `P0` through `P7` cleanup bundles remain findable through `docs/archive/ARCHIVE_INDEX.yaml`.
- `verify_archive_reconciliation.py` passes and is included in `verify_repo.py --mode fast`.
- Current authority paths and the active default lane remain unchanged.
- `scripts/codex/audit_worktree_noise.py --json` classifies the remaining dirty surface.
- `WORKTREE_TRIAGE.md` records `authority_dirty`, `formal_runtime_dirty`, `operational_exhaust`, and the cleanup return gate.
- `RETURN_GATE_REVIEW.md` records the final owner mapping and default return to fresh live recheck.
- `audit_worktree_noise.py` emits per-category `recommended_next_owner` and `top_20_paths`.

## Verification

- `python3 scripts/codex/generate_route_convergence_views.py` passed.
- `python3 scripts/codex/verify_route_convergence.py` passed with exactly one active default lane.
- `python3 scripts/codex/verify_mainline_clarity.py` passed.
- `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check` passed.
- `python3 -m py_compile ego_desktop_lab/*.py` passed.
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q` passed with `189 passed`.
- `python3 scripts/codex/verify_repo.py --mode fast` passed; OpenEmotion live health smoke was skipped because the local health endpoint was unavailable.
- Scoped whitespace check for this change surface passed.

## Phase 2A Verification Target

- `python3 -m py_compile scripts/codex/verify_archive_reconciliation.py scripts/codex/verify_repo.py` passed.
- `python3 scripts/codex/verify_archive_reconciliation.py` passed with `2` moved docs and `8` moved artifact dirs.
- `python3 scripts/codex/generate_program_state_views.py` passed.
- `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check` passed.
- `python3 scripts/codex/verify_route_convergence.py` passed with exactly one active default lane.
- `python3 scripts/codex/verify_mainline_clarity.py` passed.
- `python3 scripts/codex/verify_repo.py --mode fast` passed with the archive reconciliation gate included.
- Scoped whitespace check for the archive reconciliation surface passed.

## Phase 2B Verification Target

- `python3 -m py_compile scripts/codex/audit_worktree_noise.py scripts/codex/verify_mainline_clarity.py` passed.
- `python3 scripts/codex/audit_worktree_noise.py --json` passed and classified `7319` dirty paths.
- `python3 scripts/codex/verify_mainline_clarity.py` passed with the worktree audit gate.
- `python3 scripts/codex/verify_route_convergence.py` passed with exactly one active default lane.
- `python3 scripts/codex/verify_archive_reconciliation.py` passed.
- `python3 scripts/codex/verify_repo.py --mode fast` passed; OpenEmotion live health smoke remained skipped because the local health endpoint was unavailable.
- `git diff --check -- docs/codex/tasks/repo-mainline-clarity-v1 scripts/codex` passed.

## Phase 2B Return Gate

After Phase 2B, default next action is to stop cleanup and return to `subject_system_v1_governed_proactivity` fresh live recheck unless a later explicit small cleanup slice admits one path class with its own verifier.

## Final Return Gate Verification Target

- `python3 -m py_compile scripts/codex/audit_worktree_noise.py scripts/codex/verify_mainline_clarity.py` passed.
- `python3 scripts/codex/audit_worktree_noise.py --json` passed and classified `7320` dirty paths, with per-category `recommended_next_owner` and `top_20_paths`.
- `python3 scripts/codex/verify_route_convergence.py` passed with exactly one active default lane.
- `python3 scripts/codex/verify_mainline_clarity.py` passed with the return-gate review and cleanup staging guard.
- `python3 scripts/codex/verify_archive_reconciliation.py` passed.
- `python3 scripts/codex/verify_repo.py --mode fast` passed; OpenEmotion live health smoke remained skipped because the local health endpoint was unavailable.
- `git diff --cached --name-only` showed no staged files during pre-stage verification.
- `git diff --cached --check` passed.
- `git diff --check -- docs/codex/tasks/repo-mainline-clarity-v1 scripts/codex` passed.

## Known Limitation

The broad cleanup command `git diff --check -- docs EgoCore OpenEmotion ego_desktop_lab artifacts scripts` is still blocked by pre-existing unrelated runtime artifacts and logs with whitespace issues. This task does not clean or stage those files.

## Claim Ceiling

Repo readability and route discipline only. This does not prove runtime efficacy, live autonomy, consciousness, alive status, or user benefit.
