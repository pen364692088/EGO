# Ego Handmade Operator Runtime Contract v1 - SPEC

## Goal

Make `Ego_handmade` usable as an operator-first local runtime by replacing
env-only file write failure with an explicit runtime mode and transaction
approval contract.

## Authority Snapshot

- formal EGO mainline remains `subject_system_v1_governed_proactivity`
- `Ego_handmade` remains candidate-local replacement work only
- no `EgoCore`, `OpenEmotion`, `ego_desktop_lab`, program-state, or
  evidence-ledger change is authorized

## Contract

- runtime modes are `chat`, `plan`, `approve`, and `trusted-workspace`
- default mode is `approve`
- file writes are proposed through `propose_file_write`, not executed directly
- operator approval creates a one-shot lease; execution must match path and
  content hash
- subagents cannot directly write files, run commands, or fetch the web
- `trusted-workspace` may auto-consume a lease for low-risk workspace writes,
  while preserving containment, allowlist, overwrite, path, and hash checks
- `run_command` and `web_fetch` remain conservative in this v1 and are not
  widened by the file-write transaction slice

## Claim Ceiling

`Ego_handmade operator runtime contract local candidate pass`.

This task cannot claim EGO mainline replacement, formal long-term memory
efficacy, live autonomy, runtime efficacy, stable user benefit, or consciousness.
