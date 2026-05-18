# MVP13 Controlled Observation Report

- generated_at: `2026-04-03T06:58:39.021418+00:00`
- git_commit_short: `cfbbe0c`
- session_id: `session:mvp13:batch:002:open_license_ultrachat_tracking`
- observation_count: `3`
- verification_level: `V4`
- evidence_level: `E4`
- status: `pass`

## Scenario

- scenario_id: `open_license_ultrachat_tracking`
- source_class: `open_license`
- source_ref: `https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k#prompt_id=9fb649a870769f4881c647d20d178656f67fc881b2dc0b65d4860237c2c8da6c`
- dialogue_frame_target: `mechanism_gap`

## Developmental

- cycle_id: `dev-1ac5ff2fd43d51f8`
- gate_status: `allow`
- self_model_delta_fields: `['confidence_by_domain', 'known_unknowns']`

## Writeback

- gate_verdict: `allow_writeback`
- accepted: `True`
- changed_fields: `['confidence_by_domain', 'known_unknowns']`
- revision_id: `rev_000002`
- trace_reference: `developmental:dev-1ac5ff2fd43d51f8:b3d256a52d9a92ea`

## Replay

- replay_valid: `True`
- revision_count: `2`

## Boundary

This report proves a controlled mainline-triggered formal owner writeback path. It does not claim E5 stability or live autonomous authority.
