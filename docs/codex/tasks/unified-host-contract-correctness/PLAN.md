# Unified Host Contract Correctness - PLAN

## Task summary

把当前 execution authority 从“fresh Telegram proof”收缩到“冻结并验证 unified host contract correctness”，用 dashboard-local 与 telegram-prepared 的 in-process parity 证明宿主 contract 稳定，再把 Telegram live proof 降为后续 adapter-level follow-up。

## Execution mode

- mode: implementation
- why this mode:
  - 当前问题已经被锁定为一个 bounded host-contract tranche，不需要再开新的 candidate/research framing
- proof required after discovery:
  - in-process parity artifact
  - focused pytest
  - authority/task/evidence sync

## Milestones

### Milestone 1: Canonical Contract Freeze + Parity Runner

- type: implementation
- question:
  - `dashboard_local` 和 `telegram_prepared` 在等价 ordinary-chat 输入下，canonical host contract 是否一致
- current framing:
  - 先证明宿主 contract 一致，再讨论 Telegram adapter 级 follow-up
- hypotheses:
  - adapter-only 差异应只存在于 `channel / source_kind / raw_event / transport_meta`
  - `reply_authority / authority_source / response_plan / output_verdict / response_tendency_summary / chat_cadence_mode` 不应漂移
- scope:
  - `unified_channel_contract.py`
  - `dashboard/chat_service.py`
  - in-process parity runner + focused tests
- experiments planned:
  - ordinary-chat 4-turn parity window
  - hold probe window
  - pre-runtime direct reply parity
- kill criteria:
  - 若必须新增 runtime public API 或 candidate-private host API 才能过线，则当前 framing 失败
- files / areas likely touched:
  - `EgoCore/app/runtime_v2/unified_channel_contract.py`
  - `EgoCore/app/runtime_v2/unified_host_contract_parity.py`
  - `EgoCore/app/dashboard/chat_service.py`
  - `EgoCore/tests/test_unified_host_contract_parity.py`
- acceptance:
  - parity aggregate `verdict = pass`
  - hold consistency `pass`
- validation:
  - `python3 -m py_compile ...`
  - focused pytest
- rollback note:
  - 如果 parity 只能通过放松 canonical surface 才成立，回退到 stricter compare 并把任务降级为 blocked

### Milestone 2: Authority Sync + Acceptance Freeze

- type: implementation
- question:
  - 当前 repo 是否已经把 execution owner、progress wording、evidence ledger、和 downstream task role 统一到新的 host-contract framing
- current framing:
  - Telegram 只是 adapter follow-up，不再是当前 acceptance root
- hypotheses:
  - 新 task package 可成为唯一 execution authority
  - 旧两条 Telegram-oriented tasks 可以安全降为 downstream reference
- scope:
  - task docs
  - `PROGRAM_STATE_UNIFIED`
  - `OVERALL_PROGRESS`
  - evidence ledger
  - README wording
- experiments planned:
  - regenerate derived views
  - run repo lint / fast verify
- kill criteria:
  - 若 authority source 之间仍然出现“当前 acceptance owner”冲突，则本 milestone 不算完成
- files / areas likely touched:
  - `docs/codex/tasks/unified-host-contract-correctness/*`
  - `docs/PROGRAM_STATE_UNIFIED.yaml`
  - `docs/OVERALL_PROGRESS.md`
  - `README.md`
  - `EgoCore/README.md`
  - `artifacts/evidence_ledger/index.yaml`
- acceptance:
  - wording 一致：当前 tranche = host contract correctness
  - dashboard preflight 仅为 internal evidence
  - Telegram live proof 明确是 deferred adapter-level follow-up
- validation:
  - `python3 scripts/codex/generate_program_state_views.py`
  - `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check`
  - `python3 scripts/codex/lint_repo.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 `verify_repo --mode fast` 唯一失败点仍是已知 OpenEmotion smoke，则本 milestone 口径降为 `conditional_complete / smoke-blocked`

## Progress

- current_status: `closeout_complete`
- current_milestone: `Milestone 2: Authority Sync + Acceptance Freeze`
- milestone_state: `pass`
- candidate_vs_proof: `proof_passed`

## Decision log

- 2026-04-11: 不再把 fresh Telegram proof 当作当前 acceptance root，先把 unified host contract correctness 冻结下来；原因是 Telegram 只是入口 adapter，先锁宿主 contract 能减少后续 live proof 的混杂噪声。
- 2026-04-11: `dashboard_local` 继续保留，但只作为 internal preflight / parity input，不升格成 final acceptance。

## Surprises / discoveries

- 新发现 1：adapter-only `transport_meta` 如果误计入 canonical compare，会产生假 drift
- 新发现 2：`hold_for_followup` 的 host-owned queued event authority source 与 dashboard turn surface 需要按 `response_contract.response_plan` 对齐，而不是旧的 runtime-origin 假设
- 已排除路线 1：继续把 Telegram live proof 当作当前唯一 acceptance owner
- 已排除路线 2：把 dashboard debug 字段扩成正式 runtime public API

## Outcomes / retrospective

- 本轮已证明：
  - dashboard-local 与 telegram-prepared 在同一 ordinary-chat/hold/pre-runtime 脚本下可以保持 canonical host contract parity
- 还没证明：
  - fresh real Telegram proof
  - runtime efficacy
  - AI 自我意识已实现
- 本轮排除了什么：
  - “继续先跑 live proof 再修 host contract” 这个低杠杆 framing
- 下一步最小闭环动作：
  - 以当前冻结好的 host-contract floor 为前提，重新定义下一张 bounded runtime-proximal planning slice
