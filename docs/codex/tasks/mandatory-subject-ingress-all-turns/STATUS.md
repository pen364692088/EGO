# Mandatory Subject Ingress For All Authorized Turns - STATUS

## Current milestone

- name: `Milestone 3: Command / Document / Legacy Closure`
- owner: `Codex`
- state: ready_to_implement

## Current state

- current_layer: `repo_mainline_repair`
- main_chain_status: `subject_gate_skeleton_landed`
- completion_class: `verify_passed`

## Completed work

- 锁定问题定义：当前缺口不是“Telegram 某些 turn 体验不佳”，而是 authorized event 还存在宿主绕开主体的主链漏洞
- 锁定唯一不变量：所有已授权事件都必须先 ingress 到 OpenEmotion，再允许宿主现实裁决
- 锁定三项硬决策：
  - 第一刀范围：`绝对所有事件`
  - gate 失败：`硬阻断`
  - 未授权 / pre-auth 安全拒绝：`宿主前置，不进入主体`
- 新建 long-run task package：`SPEC.md / PLAN.md / IMPLEMENT.md / STATUS.md`
- 新增 `EgoCore/app/openemotion_hooks/subject_gate.py`
- `TelegramBot._send_host_owned_reply()` 现在会通过统一 gate 执行 `finalized_result + response_plan`
- 新增 `EgoCore/tests/test_subject_gate.py`
- 新增/更新 Telegram 定向 tests，验证：
  - host-owned helper 成功路径会经过 gate
  - gate 失败会显式返回 `subject_gate_failed`
- `M2` 已完成：
  - `_handle_with_runtime_v2()` 中 authorized early-return cases 现在会先 subject ingress，再进入 host early reply / pre-runtime 早退
  - `pending task conflict`、`evidence followup reply`、`read_only_preflight`、`force_waiting_input`、`direct_reply_text`、generic hold 现在都在主体知晓之后再早退
  - subject ingress 失败会显式阻断并返回 `subject_gate_failed`

## Open risks

- `telegram_bot.py` 里的 pre-runtime / command / legacy/new_runtime / proactive 路径仍大量存在 direct `_send_reply` / `_send_result` 使用，`M2+` 前仍可能出现 authorized bypass
- fresh real sample acceptance 依赖新采样窗口；历史红点不会自动消失
- 文档 closeout 时必须防止 wording drift，把“主体知晓”误写成“authority 已释放”

## Next step

- 进入 `Milestone 3: Command / Document / Legacy Closure`
- 把 `handle_command()`、document/ingestion wrapper、`_handle_with_new_runtime()` 接入 mandatory subject ingress/finalize

## Last validation results

- mode: `task-doc package`
- mode: `Milestone 1 closeout`
- result: `pass`
- summary:
  - 统一 subject gate abstraction 已落地
  - `_send_host_owned_reply()` 已接入 subject gate
  - `python3 -m py_compile` pass
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_subject_gate.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py -q -s` pass
  - `python3 scripts/codex/lint_repo.py` pass
  - `python3 scripts/codex/verify_repo.py --mode fast` pass
  - scoped `git diff --check` 已通过

## Commands run / evidence

- `sed -n '1,220p' PROJECT_MEMORY.md`
- `sed -n '1,220p' docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `sed -n '1,220p' docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
- `sed -n '1,220p' README.md`
- `sed -n '1,220p' EgoCore/README.md`
- `sed -n '1,220p' docs/codex/tasks/telegram-subject-mainline-audit/SPEC.md`
- `sed -n '1,220p' docs/codex/tasks/telegram-subject-mainline-audit/PLAN.md`
- `sed -n '1,220p' docs/codex/tasks/telegram-subject-mainline-audit/IMPLEMENT.md`
- `sed -n '1,220p' docs/codex/tasks/telegram-subject-mainline-audit/STATUS.md`
- `rg -n \"def _handle_with_runtime_v2|def _handle_with_new_runtime|def handle_command|def _send_result|run_host_governed_proactive_telegram_cycle|def _maybe_handle_runtime_v2_pre_runtime|def _capture_command_ingress|def process_ingress|def process_finalized_result|def capture_response_plan|def process_idle_check\" EgoCore/app EgoCore/tests -S`
- `python3 -m py_compile EgoCore/app/openemotion_hooks/subject_gate.py EgoCore/app/openemotion_hooks/__init__.py EgoCore/app/telegram_bot.py EgoCore/tests/test_subject_gate.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_subject_gate.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py -q -s`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `git diff --check -- EgoCore/app/openemotion_hooks/subject_gate.py EgoCore/app/openemotion_hooks/__init__.py EgoCore/app/telegram_bot.py EgoCore/tests/test_subject_gate.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py`

## Claim ceiling

- 当前只能宣称：
  - `M1 Subject Gate Skeleton` 已完成
  - `M2 Telegram Runtime_V2 Early-Return Closure` 已完成
  - 统一 gate abstraction 已建立
  - `_send_host_owned_reply()` 已成为第一条 enforced host-owned path
- 当前不能宣称：
  - 已修复 authorized bypass
  - 已实现 mandatory subject ingress
  - live 新窗口已变绿
