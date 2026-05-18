# Legacy Pre-Handmade Mainline

This directory preserves the pre-`Ego_handmade` projects after the 2026-05-18 operator-first transition.

Contents:

- `EgoCore/`: legacy host/runtime implementation and fallback source.
- `OpenEmotion/`: legacy subject/proto-self implementation and algorithm source.
- `ego_desktop_lab/`: legacy deterministic lab/reference harness.

Rules:

- Do not use these directories as the default new-development entry.
- Do not restore keyword-first semantic routing or template fallback into `Ego_handmade`.
- Use this tree for reference, rollback, audits, or explicit legacy maintenance only.
- Current authority remains `docs/PROGRAM_STATE_UNIFIED.yaml`.
