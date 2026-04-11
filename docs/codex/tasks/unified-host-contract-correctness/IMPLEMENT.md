# Unified Host Contract Correctness - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `docs/PROGRAM_STATE_UNIFIED.yaml`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 当前 tranche 只做 host contract correctness，不推进新的 self-awareness candidate 实现
- 旧任务 `mandatory-subject-ingress-all-turns` 与 `live-chat-subjective-variability` 只保留为 downstream reference，不再作为 acceptance owner

## Scope control

- 允许改：
  - canonical host contract snapshot / compare helper
  - in-process dashboard-vs-telegram parity runner
  - bounded dashboard debug surface
  - task / authority / evidence sync
- 不允许改：
  - runtime public API
  - host-consumable surface beyond `policy_hint / response_tendency / trace_payload`
  - candidate-private host API
  - live Telegram acceptance logic
  - new self-awareness winner semantics

## Validation strategy

- code / runner:
  - `python3 -m py_compile ...`
  - focused pytest on:
    - `test_unified_host_contract_parity.py`
    - `test_dashboard_chat_service.py`
    - `test_unified_telegram_contract.py`
    - proactive hold/proactive transport regressions
- repo gates:
  - `python3 scripts/codex/lint_repo.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- state sync:
  - `python3 scripts/codex/generate_program_state_views.py`
  - `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check`

## Failure handling

- 如果 parity 失败：
  - 先修 canonical host contract drift
  - 不把 adapter-only 字段移出 compare 之外的字段偷删成“假通过”
- 如果 verify fast 失败：
  - 先区分 touched-surface regression 与已知 OpenEmotion smoke blocker
  - 只有 touched-surface 全绿时，才能降级成 `conditional_complete / smoke-blocked`

## Artifact contract

- current artifact:
  - `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.json`
  - `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.md`
- artifact meaning:
  - `source = dashboard_local_vs_telegram_prepared_inprocess`
  - `claim_ceiling = host_contract_only`
- artifact must not be consumed by:
  - `real_telegram` acceptance
  - live Telegram proof scripts

## Final handoff checklist

- [ ] parity artifact 已生成
- [ ] focused pytest 已通过
- [ ] authority / task / evidence wording 已同步
- [ ] derived views 已重生成
- [ ] `verify_repo --mode fast` 结果已记录
