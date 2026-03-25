# CONTEXT_HYGIENE.md - Context Management Guide

Keep execution context clean, current, and compact to reduce mistakes and token waste.

## 1) When to Checkpoint

Create a checkpoint when:
- A milestone is reached (plan complete, implementation complete, verification complete)
- A risky change is about to start
- You are switching tasks or repos
- You are blocked and waiting on user input
- Session context is getting long/noisy

### Checkpoint Contents
- Current goal and phase
- Completed DoD items
- Next action (single executable step)
- Evidence paths (logs/tests/screenshots)
- Open blockers/questions

## 2) How to Handle Compaction

When context is truncated/compacted:
1. Re-read `TASK.md` first
2. Re-open latest evidence artifacts from `logs/` (or listed paths)
3. Reconstruct state in 3-5 bullets
4. Confirm next action is still valid
5. Update `TASK.md` with refreshed timestamp and state

If critical info is missing, explicitly mark:
`BLOCKED: need <specific missing info> from user`

## 3) Token-Saving Strategies

- Keep chat updates short (summary only); store long output in `logs/`
- Prefer bullet points over long prose
- Reference paths instead of pasting full logs
- Avoid re-reading unchanged large files
- Reuse stable templates (`TASK.md`, `DECISIONS.md`) instead of rewriting context
- Keep one clear next action at all times

## Quick Routine (per loop)
1. Read `TASK.md`
2. Execute next action
3. Save long output to `logs/`
4. Update evidence + status in `TASK.md`
5. Repeat until DoD is complete
