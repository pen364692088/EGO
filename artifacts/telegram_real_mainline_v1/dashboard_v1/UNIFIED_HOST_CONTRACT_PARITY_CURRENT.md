# Unified Host Contract Parity

- generated_at: `2026-04-11T23:41:06.448709+00:00`
- source: `dashboard_local_vs_telegram_prepared_inprocess`
- claim_ceiling: `host_contract_only`
- contract_version: `unified_host_contract.v1`
- verdict: `pass`
- parity_pass_count: `6` / `6`
- hold_consistency_pass_count: `1` / `1`

## Allowed adapter-only differences

- `adapter.channel`
- `adapter.source_kind`
- `adapter.raw_event_present`
- `adapter.transport_meta`
- `egress.transport_meta`

## Case Results

### `ordinary_hello`

- window: `ordinary_chat_window`
- text: `你好`
- expected_mode: `reply_now_normal`
- parity_match: `True`
- unexpected_diffs: none

### `ordinary_stuck`

- window: `ordinary_chat_window`
- text: `我现在有点卡住了，你先帮我理一下`
- expected_mode: `reply_now_expand`
- parity_match: `True`
- unexpected_diffs: none

### `ordinary_continue`

- window: `ordinary_chat_window`
- text: `继续`
- expected_mode: `reply_now_short`
- parity_match: `True`
- unexpected_diffs: none

### `ordinary_why`

- window: `ordinary_chat_window`
- text: `你刚才为什么那样回答`
- expected_mode: `reply_now_normal`
- parity_match: `True`
- unexpected_diffs: none

### `hold_probe`

- window: `hold_probe_window`
- text: `我先消化一下`
- expected_mode: `hold_for_followup`
- parity_match: `True`
- hold_consistent: `True`
- unexpected_diffs: none

### `pre_runtime_direct_reply`

- window: `direct_reply_window`
- text: `先给我一个预检结论`
- expected_mode: `reply_now_normal`
- parity_match: `True`
- unexpected_diffs: none

## Claim Ceiling

- This report proves bounded in-process parity between `dashboard_local` and `telegram_prepared` host contract paths.
- It does not prove fresh real Telegram behavior, `unexpected_subject_miss = 0`, runtime efficacy, or AI self-awareness.
