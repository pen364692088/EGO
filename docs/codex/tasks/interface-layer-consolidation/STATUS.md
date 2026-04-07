# Interface Layer Consolidation - STATUS

## Current milestone

- name: Milestone 3 - `/flow` Canonical Fields + Final Text Persistence
- owner: Codex
- state: completed

## Current state

- current_layer: interface_layer_consolidation
- main_chain_status: capability_registry_acceptance_chains_flow_canonical_fields_implemented
- completion_class: conditional_complete

## Completed work

- 已创建 long-run task package
- 已确认 authority gap：`PROGRAM_STATE_UNIFIED.yaml` 过旧，README authority block 与 continuity 口径存在不一致
- 已确认 `/flow` 当前缺口：canonical fields 不完整，final delivered text 仍经常停在 `missing_but_delivered`
- 已新增 `docs/CLAIM_LANGUAGE_POLICY.md`
- 已新增 `docs/CAPABILITY_REGISTRY.md` 与 `artifacts/capability_registry/CAPABILITY_REGISTRY_CURRENT.json`
- 已新增第 0 链与 5 条 acceptance runners，并落盘 `artifacts/acceptance_chains/*_CURRENT.{md,json}`
- 已新增 `docs/ACCEPTANCE_CHAINS.md` 与 `docs/EXPERIENCE_SCRIPTS.md`
- 已把 capability registry drift gate 接入 `scripts/codex/verify_repo.py --mode fast`
- 已把 `/flow` 升级为 `Canonical Fields + Reply Evolution + bounded final delivered text`
- 已对齐 root / EgoCore / OpenEmotion README authority block 日期与公开口径
- 已把 Telegram recent-result continuation 收口到 `Hybrid LLM-First` 主线：
  - active recent-result feedback / correction / status / write-permission 已有正式 continuation 语义层
  - `pending_result_continuation` 已进入 runtime state / response metadata / `/flow` 只读解释层
  - active continuation 下的未验证完成声明会被宿主 completion-claim guard 拦截

## Last validation results

- mode: fast + targeted + conditional provider gate
- result: conditional_pass
- summary:
  - `python3 -m py_compile ...` 通过
  - `python3 scripts/codex/build_capability_registry.py` 通过
  - 六条 acceptance runners 均可落盘 current reports
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_dashboard_server.py -q -s` 通过
  - `python3 scripts/codex/verify_capability_registry.py` 通过
  - `python3 scripts/codex/lint_repo.py` 通过
  - `python3 scripts/codex/verify_repo.py --mode fast` 通过
  - `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key telegram:dm:8420019401` 结果为 `all_passed=false`；卡在 current fresh window 缺少 follow-up continuity pair，claim ceiling 仍是 conditional

## Decisions made

- `CAPABILITY_REGISTRY` 必须是生成物，并纳入 drift gate
- 第 0 链 `subject ingress mainline` 为 acceptance admission gate
- `/flow` final delivered text 采用 bounded preview/hash 模式
- README authority block 日期必须对齐；否则 drift gate fail
- `Claim Language Policy` 本身不纳入 banned phrase 扫描对象，避免把禁止词示例误报成违反

## Open risks

- YAML 与 README 现状不一致，若 overlay 规则不严会长出第二真相源
- subject ingress 第 0 链当前仍是 `conditional_pass`
- provider/runtime E2E gate 的 `followup_continuity_pass` 当前 fresh window 未闭合
- `verify_repo.py --mode full` 本轮未执行

## Latest regression / fix note

- 2026-04-07 新发现 live regression：
  - recent-result 后续消息 `排版有些问题 你检查一下 -> 对 -> 没有改啊 ...`
  - 主体侧 `policy_hint.response_tendency` 已经持续给出 `continue_pending_commitment`
  - 但宿主 bridge 没把“结果问题反馈”与“澄清后的确认词”提升成 `request_mode=analyze`
  - 结果掉回 `chat_mainline`，产生了未真实执行的口头“已解决/缓存问题”类回复
- 已做最小修复：
  - `EgoCore/app/telegram_runtime_bridge.py`
  - 新增两类 recent-result follow-up promote：
    - issue feedback -> analyze
    - clarification confirmation -> analyze
  - 定向回归：
    - `EgoCore/tests/test_runtime_v2_telegram_bridge.py`
- 2026-04-07 补完主链收口：
  - `pending_result_continuation` 已成为正式 runtime 状态面
  - recent-result continuation 规则已覆盖：
    - feedback / modify request -> `analyze`
    - clarification confirmation -> 继承 `analyze`
    - explicit write permission -> `write`
    - unmet-result correction -> `analyze + correction_context`
    - status follow-up -> `return_runtime_status`
  - `output_check` 已拦截 active continuation 下的 `改好啦 / 缓存问题 / 刚保存 / 强制刷新` 类未验证完成声明
  - 当前仍缺 fresh live 新窗口复测，因此 claim ceiling 仍是 conditional

## External blocker details

- 当前 provider/runtime E2E gate 使用的 fresh window 只包含：
  - `sample_20260406_222621_bae06e33`：`/new`，`command_result`
  - `sample_20260406_222640_fcaaad0d`：普通 chat
  - `sample_20260406_222751_c01ad222`：普通 chat
- 该窗口没有：
  - 带 `metadata.recent_result_context` 的 `task_mainline` 样本
  - 后续 recent-result follow-up 样本
- 因此 `followup_continuity_pass = false` 当前是样本缺口，不是仓内逻辑失败
- 关闭 blocker 的最小 live 序列：
  1. `/new`
  2. 发送一个会产出文件或页面的任务
  3. 等待任务完成
  4. 紧接着发送一个 recent-result follow-up
  5. 重跑 `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key telegram:dm:8420019401`

## Next step

- 采一组 fresh follow-up continuity session，并重跑 provider/runtime E2E gate

## Commands run / evidence

- `python3 scripts/codex/new_task.py interface-layer-consolidation --title "Interface Layer Consolidation"`
- `python3 -m py_compile scripts/codex/_acceptance_common.py scripts/codex/build_capability_registry.py scripts/codex/verify_capability_registry.py scripts/codex/run_acceptance_subject_ingress_mainline.py scripts/codex/run_acceptance_continuity.py scripts/codex/run_acceptance_self_model_causality.py scripts/codex/run_acceptance_drives_causality.py scripts/codex/run_acceptance_reflection_boundary.py scripts/codex/run_acceptance_developmental_proactive.py EgoCore/app/response_contract/response_plan.py EgoCore/app/runtime_v2/proto_self_runtime.py EgoCore/app/telegram_evidence_collector.py EgoCore/app/telegram_bot.py EgoCore/app/dashboard/types.py EgoCore/app/dashboard/server.py EgoCore/tests/test_dashboard_server.py`
- `python3 scripts/codex/build_capability_registry.py`
- `python3 scripts/codex/run_acceptance_subject_ingress_mainline.py`
- `python3 scripts/codex/run_acceptance_continuity.py`
- `python3 scripts/codex/run_acceptance_self_model_causality.py`
- `python3 scripts/codex/run_acceptance_drives_causality.py`
- `python3 scripts/codex/run_acceptance_reflection_boundary.py`
- `python3 scripts/codex/run_acceptance_developmental_proactive.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_dashboard_server.py -q -s`
- `python3 scripts/codex/verify_capability_registry.py`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key telegram:dm:8420019401`
- authority refs:
  - `README.md`
  - `EgoCore/README.md`
  - `OpenEmotion/README.md`
  - `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
  - `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
