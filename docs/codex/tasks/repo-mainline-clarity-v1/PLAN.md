# Repo Mainline Clarity v1 Plan

## Phase 1: Mainline View

- Add `docs/MAINLINE_QUICKSTART.md` as the first human onboarding page.
- Generate `docs/REPO_SURFACE_MAP.md` from route-convergence code.
- Register this task as a supporting active lane, not active default.
- Add `verify_mainline_clarity.py` to check README links, quickstart content, surface map drift, and staged operational exhaust.
- Wire the verifier into `verify_repo.py --mode fast`.

## Phase 2: Controlled Physical Archive

Phase 2A only reconciles the already half-applied archive migration:

- Accept the moved docs under `docs/archive/`.
- Accept historical cleanup bundles `P0` through `P7` under `artifacts/archive/repo_cleanup_history/`.
- Add `scripts/codex/verify_archive_reconciliation.py` as the path/index/current-reference gate.
- Wire the verifier into `verify_repo.py --mode fast`.
- Do not authorize any new archive class or broader physical move in this slice.

Phase 2B does not move files. It adds dirty-worktree triage:

- Add `scripts/codex/audit_worktree_noise.py` as a read-only classifier for `git status --porcelain`.
- Record the remaining dirty surface in `WORKTREE_TRIAGE.md`.
- Treat EgoCore/OpenEmotion runtime changes, formal state, formal evidence, logs, JSONL, cache, and unknown untracked paths as outside cleanup scope.
- Add a return gate: either admit a later small cleanup class explicitly, or stop cleanup and return to `subject_system_v1_governed_proactivity` fresh live recheck.

Final Return Gate Review closes the cleanup-oriented loop:

- Add `RETURN_GATE_REVIEW.md` as the handoff page for what remains dirty and who owns each class.
- Extend `audit_worktree_noise.py` with per-category `recommended_next_owner` and top-20 representative paths.
- Tighten `verify_mainline_clarity.py` so repo-mainline-clarity cleanup staging cannot mix runtime, authority, evidence, generated output, logs, JSONL, temp, or unknown paths.

## Phase 3: Split / Restructure

Deferred. Only consider if Phase 1-2 still fail onboarding, CI isolation, or authority-boundary clarity.

## Validation

```bash
python3 -m py_compile scripts/codex/route_convergence_common.py scripts/codex/generate_route_convergence_views.py scripts/codex/verify_route_convergence.py scripts/codex/verify_mainline_clarity.py scripts/codex/verify_repo.py
python3 scripts/codex/generate_route_convergence_views.py
python3 scripts/codex/verify_route_convergence.py
python3 scripts/codex/verify_mainline_clarity.py
python3 scripts/codex/verify_archive_reconciliation.py
python3 scripts/codex/audit_worktree_noise.py --json
python3 scripts/codex/check_program_state_integrity.py --skip-diff-check
python3 scripts/codex/verify_repo.py --mode fast
git diff --check -- docs scripts .gitignore README.md
```
