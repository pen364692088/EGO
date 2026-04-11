# Live Chat Subjective Variability - STATUS

## Current milestone

- name: `Downstream Reference: Telegram adapter-level field proof`
- owner: `Codex`
- state: deferred_to_unified_host_contract_correctness

## Current state

- current_layer: `repo_live_chat_corrective_slice`
- main_chain_status: `host_governed_cadence_present`
- completion_class: `downstream_reference_task`

## Completed work

- 新建 long-run task package：
  - `SPEC.md`
  - `PLAN.md`
  - `IMPLEMENT.md`
  - `STATUS.md`
- 冻结 baseline 会话：
  - `session = telegram:dm:8420019401`
  - time window = `2026-04-05 18:01:43 -> 18:11:55`
  - sample range = `sample_20260405_180143_60904195` -> `sample_20260405_181155_09ded249`
- 冻结 baseline 结论：
  - ordinary chat turn 已持续 ingress 到主体
  - 当前 live Telegram chat 仍由宿主同步聊天契约主导：
    - `reply_authority = model_chat`
    - `reply_origin = chat_mainline`
    - `delivery_kind = chat`
  - 13 个 ordinary chat turn 的 tendency 基本恒定：
    - `preferred_mode = ask`
    - `preferred_tone = cautious`
    - `suggested_next_step = prioritize_closure`
  - 当前 richer bounded fields 在 live sample 中缺失：
    - `social_policy_hints`
    - `embodied_policy_hints`
    - `integrated_policy_hints`
    - `initiative_policy_hints`
- 锁定 `M2` 只做 richer subject surface，不提前做 M3/M4
- `M2 Rich Subject Surface` 已完成：
  - `RuntimeV2ProtoSelfRuntime` 现在会在 ingress / external_result / finalized_result / idle_check / developmental_tick 路径上显式规范 richer bounded subject fields
  - richer result fields 在 capture 时即使上游未提供，也会显式保留为 `{}`：
    - `social_policy_hints`
    - `embodied_policy_hints`
    - `integrated_policy_hints`
    - `initiative_policy_hints`
  - richer trace fields 在 capture 时即使上游未提供，也会显式保留为 `{}`：
    - `social_context`
    - `environment_context`
    - `selfhood_integration_context`
    - `initiative_realization_context`
    - `host_proactive_context`
  - focused runtime/evidence tests 已补齐 explicit-empty-field 断言
- `M3 Tendency-to-Reply Consumption` 已完成：
  - `chat_reply_engine` 现在会把 richer bounded subject surface、`reflection_note.trigger`、最近 3 条 tendency 摘要、以及 bounded `chat_expression_hint` 显式带入 live chat payload
  - `chat_mainline` 现在会把 `chat_expression_hint` 和 `response_tendency_summary` 写入：
    - runtime reply metadata
    - assistant history
    - response plan metadata
  - `short / normal / expand` reply shaping 已在 current chat mainline 生效
  - `presence_check` 等 ordinary chat 已能通过结构化 hint 改变实际 reply 长度，而不只是把 tendency 留在日志里
  - repo-wide `verify_repo.py --mode full` 已重新跑通，没有引入新的 collection / mainline regression
- `M4 Host-Governed Cadence` 代码已落地：
  - `response_plan` 现在保留 `chat_cadence_mode`
  - `chat_mainline` 现在会生成并传递：
    - `chat_expression_hint`
    - `response_tendency_summary`
    - `chat_cadence_mode`
  - current Telegram mainline 现在支持 host-governed：
    - `reply_now_short`
    - `reply_now_normal`
    - `reply_now_expand`
    - `hold_for_followup`
  - `hold_for_followup` 会在满足 ordinary chat / non-question / host proactive policy allow 的条件下进入现有 proactive outbox，而不是直接放开主体 authority
  - `TelegramRuntimeFallbackRunner` 现在会保留 runtime reply metadata，避免 Telegram adapter 无声丢失 cadence / expression fields
  - M4 focused tests、lint、`verify_repo.py --mode fast` 已通过
  - repo-wide `verify_repo.py --mode full` 本轮已验证到全量 EgoCore suite 通过，但在 OpenEmotion Windows interop 包装层未在可接受时间内返回；当前按 verification blocker 记录
- `M5 Fresh Real Telegram Proof` 已完成首轮 fresh-window 复盘：
  - proof script:
    - `scripts/codex/prove_live_chat_subjective_variability.py --since-commit 72148b3`
  - current artifacts:
    - `artifacts/telegram_real_mainline_v1/dashboard_v1/LIVE_CHAT_SUBJECTIVE_VARIABILITY_CURRENT.md`
    - `artifacts/telegram_real_mainline_v1/dashboard_v1/LIVE_CHAT_SUBJECTIVE_VARIABILITY_CURRENT.json`
  - fresh window 样本数：`6`
  - 样本分布：
    - `non_ordinary = 4`
    - `ordinary_text_policy_or_control = 2`
    - `ordinary_chat_mainline = 0`
  - 当前 fresh window 中没有 ordinary-chat mainline 样本，因此：
    - richer fields 没有 fresh ordinary-chat 证明
    - tendency delta 没有 fresh ordinary-chat 证明
    - cadence delta 没有 fresh ordinary-chat 证明
  - `M5` 当前结论是 blocker，不是 pass
- `mandatory-subject-ingress-all-turns / M4` 的 proactive/background user-visible send closure 已在本地落地并通过 targeted verify：
  - proactive transport 现在会先走 host-owned response plan + output check + `finalized_result + response_plan` subject gate
  - gate fail 时会保留 outbox 并返回 `held`
  - 这一步减少了 fresh live proof 前的主链前置缺口，但还不是 fresh Telegram ordinary-chat proof 本身

## Open risks

- 当前 baseline 已说明“主体已 ingress”，但还没有 live 可感变化证据
- 当前 baseline 仍不能证明 chat-level downstream tendency change 强成立
- 当前 corrective slice 不再被 `mandatory-subject-ingress-all-turns / M4` 本地 closure 卡住，但仍需要 publish 后的新窗口 real proof
- 当前还没有 fresh real Telegram window 证明同一 session 内已经出现稳定 tendency / cadence 差异；那是 `M5` 的范围
- 当前还没有 `hold_for_followup` 的真实 Telegram 新窗口证据；那是 `M5` 的范围
- 当前 repo-wide full verify 仍有一个外部验证 blocker：
  - `verify_repo.py --mode full` 在 WSL 下进入 OpenEmotion Windows interop 包装层后未在本轮可接受时间内返回
  - 当前没有看到新的 M4 回归信号，但也不能把这一步误记成 full green
- 当前 `M5` 的直接 blocker 已明确：
  - deploy 后虽然有 fresh real Telegram 样本，但它们是 `/new`、`profile_rule_registered`、`profile_rule_enforced`
  - 当前没有一条 fresh ordinary-chat mainline 样本进入证明窗口

## Next step

- 当前不再作为 acceptance owner 继续推进。
- 本任务现在只保留：
  - future Telegram adapter-level proof 的 authority
  - richer fields / tendency delta / cadence delta 的 live follow-up参考基线
- 当前唯一上游执行 owner 是：
  - `docs/codex/tasks/unified-host-contract-correctness/`

## Last validation results

- mode: `Milestone 5 fresh real Telegram proof`
- result: `blocked`
- summary:
  - fresh window 已按 deploy commit `72148b3` 之后的 real Telegram 样本复盘
  - 当前窗口共有 `6` 条样本，但 `ordinary_chat_mainline = 0`
  - 当前窗口没有可用于证明 richer fields / tendency delta / cadence delta 的 fresh ordinary-chat 证据
  - `M5` blocker 不是当前 chat mainline 必然失效，而是当前 fresh 样本类型不满足证明条件
- mode: `precondition tranche dependency update`
- result: `pass`
- summary:
  - `mandatory-subject-ingress-all-turns / M4` 已在本地补齐 proactive/background user-visible send 的 subject-finalize closure
  - `python3 -m py_compile EgoCore/app/telegram_bot.py EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py` pass
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py -q -s` pass (`8 passed`)
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest --basetemp=/tmp/ego_tranche_pytest EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_chat_hold_for_followup_queues_outbox_without_immediate_send EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_chat_hold_for_followup_blocked_for_explicit_question EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_host_owned_reply_captures_explicit_response_plan EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_host_owned_reply_blocks_when_subject_gate_fails EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_new_runtime_direct_reply_uses_runtime_authority_metadata -q -s` pass (`5 passed`)
  - `python3 scripts/codex/lint_repo.py` pass
  - `python3 scripts/codex/verify_repo.py --mode fast` pass
  - 当前仍未获得任何 post-patch fresh real Telegram ordinary-chat 样本，所以 `M5` 继续 blocked

## Commands run / evidence

- `sed -n '1,160p' PROJECT_MEMORY.md`
- `sed -n '1,200p' docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `sed -n '1,200p' docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
- `sed -n '1,220p' README.md`
- `sed -n '1,220p' EgoCore/README.md`
- `sed -n '1,220p' Tasks/MVS_task_plan.md`
- `sed -n '1,240p' docs/TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md`
- `sed -n '1,260p' artifacts/telegram_real_mainline_v1/dashboard_v1/SUBJECT_MAINLINE_AUDIT_CURRENT.md`
- `sed -n '1,220p' docs/codex/tasks/mandatory-subject-ingress-all-turns/STATUS.md`
- `python3 - <<'PY' ...` against `artifacts/telegram_real_mainline_v1/real_telegram/sample_20260405_18*`
- `git diff --check -- docs/codex/tasks/live-chat-subjective-variability`
- `python3 -m py_compile EgoCore/app/runtime_v2/proto_self_runtime.py EgoCore/tests/test_runtime_v2_proto_self_runtime.py EgoCore/tests/test_telegram_proto_self_v2_evidence.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_runtime_v2_proto_self_runtime.py EgoCore/tests/test_telegram_proto_self_v2_evidence.py -q -s`
- `python3 -m py_compile EgoCore/app/runtime_v2/chat_reply_engine.py EgoCore/app/response_contract/response_plan.py EgoCore/tests/test_runtime_v2_chat_mainline.py EgoCore/tests/test_response_contract.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_runtime_v2_chat_mainline.py EgoCore/tests/test_response_contract.py -q -s`
- `python3 -m py_compile EgoCore/app/response_contract/response_plan.py EgoCore/app/runtime_v2/chat_reply_engine.py EgoCore/app/runtime_v2/proactive_outbox.py EgoCore/app/runtime_v2/proactive_outbox_drain.py EgoCore/app/telegram_bot.py EgoCore/app/telegram_runtime_result.py EgoCore/app/telegram_runtime_fallback.py EgoCore/tests/test_response_contract.py EgoCore/tests/test_runtime_v2_chat_mainline.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_response_contract.py EgoCore/tests/test_runtime_v2_chat_mainline.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py EgoCore/tests/test_proactive_outbox.py EgoCore/tests/test_telegram_proactive_transport.py -q -s`
- `python3 -m py_compile scripts/codex/prove_live_chat_subjective_variability.py`
- `python3 scripts/codex/prove_live_chat_subjective_variability.py --since-commit 72148b3`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/verify_repo.py --mode full`
- `python3 -m py_compile EgoCore/app/telegram_bot.py EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_telegram_proactive_transport.py EgoCore/tests/test_host_governed_proactive_telegram_cycle.py -q -s`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest --basetemp=/tmp/ego_tranche_pytest EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_chat_hold_for_followup_queues_outbox_without_immediate_send EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_chat_hold_for_followup_blocked_for_explicit_question EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_host_owned_reply_captures_explicit_response_plan EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_host_owned_reply_blocks_when_subject_gate_fails EgoCore/tests/test_runtime_v2_cli_and_telegram.py::test_telegram_bot_new_runtime_direct_reply_uses_runtime_authority_metadata -q -s`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`

## Claim ceiling

- 当前只能宣称：
  - `M1 Baseline Freeze` 已完成
  - `M2 Rich Subject Surface` 已完成
  - `M3 Tendency-to-Reply Consumption` 已完成
  - `M4 Host-Governed Cadence` 代码已接入 current Telegram mainline
  - `M5` 首轮 fresh-window 复盘已完成，并已证明当前窗口不足以通过 acceptance
  - richer bounded subject fields 已进入 current live-artifact surface
  - tendency 已开始进入 current live reply shaping
  - `reply_now_short / reply_now_normal / reply_now_expand / hold_for_followup` 已在 host-governed contract 中建模
- 当前不能宣称：
  - live Telegram chat 已具备稳定可感变化
  - `M5` 已通过
  - `hold_for_followup` 已在 fresh real Telegram 新窗口中证明生效
  - repo-wide full verify 当前为 green
  - unrestricted autonomy / direct reply authority release
  - 本任务仍是当前 acceptance root
