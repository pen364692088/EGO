# Mandatory Subject Ingress For All Authorized Turns - PLAN

## Task summary

这是一个 repo-level 主链修复任务。目标不是提升某一条 `WP` 能力，而是把“主体知晓”从当前分散、部分路径有效的 best-effort 状态，收紧为所有已授权事件的强制 gate。

本任务只修接线与强制顺序，不改 authority source：

- `OpenEmotion` 负责知晓、写回、主体语义
- `EgoCore` 仍负责 reply/tool/transport/runtime 的最终现实裁决

## Milestones

### Milestone 1: Subject Gate Skeleton

- scope:
  - 建立统一 host-side subject gate abstraction
  - 固定 `ingress / finalized_result / response_plan` 三段强制顺序
  - 固定 `subject_gate_failed` blocking policy
- files / areas likely touched:
  - `EgoCore/app/openemotion_hooks/`
  - `EgoCore/tests/`
- acceptance:
  - 存在唯一 gate abstraction
  - 低层发送 helper 不再被业务路径直接绕过
  - hooks failure 的 blocking policy 有定向测试
- validation:
  - `python3 -m py_compile ...`
  - 定向 gate/unit tests
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 回退到现有 best-effort hooks 使用方式，不保留半接线 gate

### Milestone 2: Telegram Runtime_V2 Early-Return Closure

- scope:
  - 修 `_handle_with_runtime_v2()`
  - 修 `plan_pre_runtime()` 产生的所有 host reply 早退分支
  - 确保 authorized turn 先 ingress，再 host branch，再 finalize
- files / areas likely touched:
  - `EgoCore/app/telegram_bot.py`
  - `EgoCore/app/telegram_runtime_bridge.py`
  - `EgoCore/tests/test_runtime_v2_cli_and_telegram.py`
- acceptance:
  - `profile_rule_registered`
  - `profile_rule_enforced`
  - `return_runtime_status`
  - `waiting_input`
  - `evidence_followup`
  - `task_conflict`
  - 以上路径都不再出现 authorized host-only success reply
- validation:
  - 定向 Telegram/runtime_v2 tests
  - `python3 scripts/codex/lint_repo.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 如 runtime_v2 主线出现 regressions，先保持 existing behavior，不提交半闭合 early-return patch

### Milestone 3: Command / Document / Legacy Closure

- scope:
  - 修 `handle_command()` 与 `_send_result()` finalize 缺口
  - 修 document/ingestion wrapper 中的 host failure 直返路径
  - 修 `_handle_with_new_runtime()` 的 ingress/finalize 缺口
- files / areas likely touched:
  - `EgoCore/app/telegram_bot.py`
  - `EgoCore/tests/test_telegram_session_commands.py`
  - `EgoCore/tests/` 下相关 document/runtime tests
- acceptance:
  - `/new /status /context /prompt /proto /replace /append /cancel` 和普通 command result 都 subject-gated
  - unsupported type / download failure / ingestion failure 也不再跳过 finalize
  - `new_runtime success/timeout/crash` 都 subject-gated
- validation:
  - 定向 command/document/new_runtime tests
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 保持 command ingress 现状，不接受只补一半 finalize 的 partial patch

### Milestone 4: Background / Proactive Closure

- scope:
  - 修 proactive/system user-visible send path
  - 明确 idle/developmental tick 与 final delivery 的主体 finalize 关系
- files / areas likely touched:
  - `EgoCore/app/telegram_bot.py`
  - `EgoCore/app/runtime_v2/proactive_telegram_cycle.py`
  - 相关 proactive tests
- acceptance:
  - proactive delivery 前存在 subject finalized-result + response-plan
  - 仍不放开 unsolicited authority；只是 delivery 前必须 subject-gated
- validation:
  - 定向 proactive tests
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 proactive send 变得不稳定，宁可保留 host hold，不接受绕过 subject finalize 的 send

### Milestone 5: Verification + Fresh Real Sample Audit

- scope:
  - 跑定向测试、fast/full verify
  - 采 fresh real Telegram 样本
  - 用现有审计脚本重跑新窗口
- files / areas likely touched:
  - `artifacts/telegram_real_mainline_v1/`
  - `docs/codex/tasks/telegram-subject-mainline-audit/` 只作为引用，不改 authority
- acceptance:
  - 新窗口 `unexpected_subject_miss = 0`
  - `policy_driven_host_interception` 变成“进主体后由宿主拦截”
  - 已授权 user-visible send 前都能看到 subject finalized-result / response-plan 证据
- validation:
  - `python3 scripts/codex/lint_repo.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - `python3 scripts/codex/verify_repo.py --mode full`
  - fresh capture + audit rerun
- rollback note:
  - 若新窗口仍存在 authorized bypass，维持任务 open，不对外宣称修复完成

### Milestone 6: Closeout

- scope:
  - 产出 current report
  - 收平 claim ceiling
  - 记录历史红点 vs 新窗口结果
- files / areas likely touched:
  - `docs/codex/tasks/mandatory-subject-ingress-all-turns/STATUS.md`
  - 相关 current report / handoff docs
- acceptance:
  - 明确区分“历史红点”与“修复后新窗口”
  - 不把本任务写成 authority release
- validation:
  - scoped `git diff --check`
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note:
  - closeout 文档不接受超前 claim；若 evidence 不足，保持任务 open

## Progress

- current_status: `in_progress`
- current_milestone: `Milestone 2: Telegram Runtime_V2 Early-Return Closure`
- milestone_state: `in_progress`

## Decision log

- 当前修复目标从“减少 Telegram 红点”收紧为 repo-level 不变量：所有已授权事件都必须 subject-aware
- 第一刀范围固定为“绝对所有事件”，不只修普通聊天
- gate 失败策略固定为硬阻断，不允许 host success fallback
- 未授权 / pre-auth 安全拒绝保留宿主前置，不进入主体
- `M1` 先只把统一 gate abstraction 落到 `openemotion_hooks`，并把 `_send_host_owned_reply()` 接进去，作为第一个 enforced host-owned path；不提前推进 `M2+` 的 pre-runtime/document/proactive closure

## Outcomes / retrospective

- `M1` 已完成：
  - 新增统一 `MandatorySubjectGate`
  - 固定 `SubjectGateVerdict`
  - `_send_host_owned_reply()` 现在必须先过 `finalized_result + response_plan`
  - hooks unavailable/disabled/failure 时，会显式送出 `subject_gate_failed`，而不是继续正常成功回复
- `M2` 当前在收口：
  - `_handle_with_runtime_v2()` 中 authorized early-return cases 已先 subject ingress
  - `pending task conflict` 已通过 subject-gated finalize path
  - `evidence followup reply` 与 `read_only_preflight` / `force_waiting_input` / `direct_reply_text` 正在补齐 subject-gated finalize / response-plan 强制路径
- 当前仍未证明：
  - command/result、document/ingestion、background/proactive 已完成 closure
  - fresh real window 已消除 authorized bypass

## Expected outcome

- authorized turn/event 不再存在“宿主先回了，主体完全不知晓”的主链漏洞
- live Telegram 新窗口中，authorized host-only success reply 应清零
- dashboard 新窗口里，`policy_driven_host_interception` 的语义从“没进主体”切换成“进主体后由宿主拦截”
