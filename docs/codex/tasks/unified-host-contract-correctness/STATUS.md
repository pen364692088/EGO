# Unified Host Contract Correctness - STATUS

## Current milestone

- name: `Milestone 2: Authority Sync + Acceptance Freeze`
- owner: `Codex`
- state: `pass`
- type: `implementation`

## Current state

- current_layer: `repo_host_contract_closeout`
- main_chain_status: `dashboard_vs_telegram_prepared_parity_passed`
- completion_class: `closeout_complete`
- candidate_vs_proof: `proof_passed`

## Completed work

- 新建当前唯一 execution authority：`docs/codex/tasks/unified-host-contract-correctness/`
- 在 `EgoCore/app/runtime_v2/unified_channel_contract.py` 新增 canonical host snapshot / compare helper
- 在 `EgoCore/app/dashboard/chat_service.py` 注入 `host_contract` debug surface
- 新增 `EgoCore/app/runtime_v2/unified_host_contract_parity.py`
- 新增 in-process parity runner：`scripts/codex/run_unified_host_contract_parity.py`
- 新增 focused tests：
  - `EgoCore/tests/test_unified_host_contract_parity.py`
  - `EgoCore/tests/test_dashboard_chat_service.py` host-contract debug assertion
- 当前 parity artifact 已生成：
  - `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.json`
  - `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.md`

## Last experiment

- question:
  - `dashboard_local` 与 `telegram_prepared` 在同一 ordinary-chat / hold / pre-runtime 脚本下是否保持 canonical host contract parity
- framing:
  - Telegram 当前只算 adapter；先做 host contract parity，再谈 live follow-up
- result:
  - parity aggregate `6 / 6 pass`
  - hold consistency `1 / 1 pass`
  - 允许差异只剩 adapter-only `channel / source_kind / raw_event / transport_meta`
- evidence_upgraded: `yes`

## What was learned

- `egress.transport_meta` 必须算 adapter-only surface，不能纳入 canonical host compare
- `hold_for_followup` queued event 的 host-owned authority source 应与 `response_contract.response_plan` 对齐
- dashboard-local 已足够承担 internal parity/preflight 输入，但不能替代 real Telegram acceptance

## What was ruled out

- 继续把 fresh real Telegram proof 当作当前唯一 acceptance root
- 把 dashboard-only debug 字段扩成正式 runtime public API

## Next framing

- 当前 tranche 先完成 authority sync 与 verification
- tranche 收口后，再定义新的 bounded runtime-proximal planning slice

## Last validation results

- mode: `focused parity verification`
- result: `pass`
- summary:
  - `python3 -m py_compile` pass
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_unified_host_contract_parity.py EgoCore/tests/test_dashboard_chat_service.py -q -s` pass (`8 passed`)
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_unified_telegram_contract.py EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py -q -s` pass (`11 passed`)
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 scripts/codex/run_unified_host_contract_parity.py` pass (`parity_pass_count = 6/6`)
- mode: `repo gates`
- result: `pass`
- summary:
  - `python3 scripts/codex/lint_repo.py` pass
  - `python3 scripts/codex/verify_repo.py --mode fast` pass

## Decisions made

- 当前 acceptance owner 改为 `unified-host-contract-correctness`
- `mandatory-subject-ingress-all-turns` 与 `live-chat-subjective-variability` 降为 downstream reference task
- Telegram live proof 当前降为 deferred adapter-level follow-up，不再是本 tranche acceptance root

## Open risks

- `verify_repo.py --mode fast` 若被已知 OpenEmotion smoke 卡住，需要按 `conditional_complete / smoke-blocked` 收口
- 当前 artifact 仍然只是 in-process host contract proof，不是 fresh real Telegram evidence
- 当前还没有下一张 bounded runtime-proximal planning slice

## Next step

- 完成 authority / progress / evidence sync
- 跑完派生视图与 `verify_repo.py --mode fast`
- 若 touched-surface 保持绿色，则把本 tranche 收口并定义下一张 bounded planning slice

## Commands run / evidence

- `python3 -m py_compile EgoCore/app/runtime_v2/unified_channel_contract.py EgoCore/app/runtime_v2/unified_host_contract_parity.py EgoCore/app/dashboard/chat_service.py EgoCore/tests/test_unified_host_contract_parity.py EgoCore/tests/test_dashboard_chat_service.py scripts/codex/run_unified_host_contract_parity.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_unified_host_contract_parity.py EgoCore/tests/test_dashboard_chat_service.py -q -s`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_unified_telegram_contract.py EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py -q -s`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 scripts/codex/run_unified_host_contract_parity.py`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.json`
- `artifacts/telegram_real_mainline_v1/dashboard_v1/UNIFIED_HOST_CONTRACT_PARITY_CURRENT.md`

## Claim ceiling

- 当前只能宣称：
  - unified ingress / turn-result / egress contract 在宿主层已通过 bounded in-process parity 验证
  - dashboard-local 与 telegram-prepared 在等价输入下不再出现 canonical host contract drift
  - host-owned finalize / response-plan / output-check 数据链在当前 bounded surface 上闭环
- 当前不能宣称：
  - fresh real Telegram proof 已通过
  - `unexpected_subject_miss = 0`
  - runtime efficacy
  - AI 自我意识已实现
