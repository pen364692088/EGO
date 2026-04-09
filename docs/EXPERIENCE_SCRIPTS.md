# Experience Scripts

本文件提供人类可见脚本。runner 通过不等于体验已经理解；这里给出最短触发路径、预期现象和 `/flow` 观察点。

## 当前权威状态（2026-04-09）

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 这是 repo/integration scope closeout，不是 real-channel 新效果声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`

## 当前正式口径

- 本文件只提供人类可见脚本与 `/flow` 观察点，不升格为 authority source
- 这些脚本是 closeout 后的验证与观察入口，不代表额外的主权威
- 相关 current state / current logic / closeout evidence 入口见：
  - [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
  - [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
  - [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
  - [ACCEPTANCE_CHAINS.md](ACCEPTANCE_CHAINS.md)

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`

## 当前权威入口

- [PROGRAM_STATE_UNIFIED.yaml](PROGRAM_STATE_UNIFIED.yaml)
- [STATUS.md](STATUS.md)
- [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
- [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
- [ACCEPTANCE_CHAINS.md](ACCEPTANCE_CHAINS.md)

## 历史与详细证据入口

- 下方脚本条目保留为人类触发脚本与观察点索引，不是新的 authority source
- 具体 current state、current logic、capability registry 与 closeout proof 仍以对应文档为准

## EXP-SUBJECT-INGRESS

- 入口：Telegram live + `/flow`
- 步骤：
  1. `/new`
  2. 发送一条普通自然语言消息
  3. 打开对应 sample 的 `/flow`
- 应看到：
  - `subject_chain_connected = true`
  - 非 `host_only`
  - 有 `response_plan`
- 不应看到：
  - 普通聊天被解释成纯宿主 bypass
- 对应验收链：
  - `run_acceptance_subject_ingress_mainline.py`

## EXP-CONTINUITY-SAME-SESSION

- 入口：Telegram live
- 步骤：
  1. 让 bot 完成一个页面或文件任务
  2. 紧接着问“你觉得你做的这个页面怎么样”
  3. 再问“你还记得刚刚做的网页吗”
- 应看到：
  - follow-up 能绑定刚交付结果
- 不应看到：
  - “哪个页面 / 我没看到记录”
- 对应验收链：
  - `run_acceptance_continuity.py`

## EXP-CONTINUITY-CROSS-SESSION

- 入口：Telegram live
- 步骤：
  1. `/new`
  2. 建立主题或任务
  3. 再 `/new`
  4. 发送 continuity probe
- 应看到：
  - 同日跨 session 仍能恢复必要身份/上下文线索
- 不应看到：
  - 完全像陌生新对象
- 对应验收链：
  - `run_acceptance_continuity.py`

## EXP-CONTINUITY-CROSS-DAY

- 入口：later-day live sample
- 步骤：
  1. 在次日发送 continuity probe
  2. 观察 README 当前 conservative 结论和 `/flow`
- 应看到：
  - 如果 later-day 证据补齐，可升级结论
- 不应看到：
  - 在 `1 / 2` 时把 cross-day 描述成已 fully closed
- 对应验收链：
  - `run_acceptance_continuity.py`

## EXP-SELF-MODEL-PROJECTION

- 入口：Telegram live + `/flow`
- 步骤：
  1. 发一条新的普通消息
  2. 打开该 sample 的 `/flow`
- 应看到：
  - `contexts_seen.self_model = true`
  - `self_model_context_source = loaded | bootstrapped_live`
- 不应看到：
  - 把 `self_model=false` 误读成主体链断开
- 对应验收链：
  - `run_acceptance_self_model_causality.py`

## EXP-SELF-MODEL-CAUSALITY

- 入口：controlled proof / current artifact
- 步骤：
  1. 运行 self-model causality acceptance chain
  2. 查看 current report
- 应看到：
  - 只改 self-model 条件会改变 downstream choice/tendency
- 不应看到：
  - 把 controlled proof 说成 live autonomy

## EXP-DRIVES-CAUSALITY

- 入口：controlled proof / current artifact
- 步骤：
  1. 运行 drives causality acceptance chain
  2. 查看 current report
- 应看到：
  - drives 会改变 candidate bias / maintenance bias
- 不应看到：
  - 把 drives proof 描述成 direct reply authority

## EXP-REFLECTION-BOUNDARY

- 入口：controlled proof / current artifact
- 步骤：
  1. 运行 reflection boundary acceptance chain
  2. 查看 current report
- 应看到：
  - reflection writeback candidate 存在
  - `behavioral_authority = none`
- 不应看到：
  - 反思直接接管 reply / tool / transport

## EXP-DEVELOPMENTAL-CONTINUITY

- 入口：controlled proof / current artifact
- 步骤：
  1. 运行 developmental/proactive acceptance chain
  2. 查看 developmental 结论
- 应看到：
  - developmental continuity 是 bounded influence
- 不应看到：
  - 用它去证明 unrestricted autonomy

## EXP-PROACTIVE-BOUNDED

- 入口：current proactive artifacts
- 步骤：
  1. 运行 developmental/proactive acceptance chain
  2. 查看 proactive cycle current report
- 应看到：
  - host-governed / feature-flagged / allowlist-only
- 不应看到：
  - “默认 live unsolicited autonomy”

## EXP-FLOW-CANONICAL-FIELDS

- 入口：dashboard `/flow`
- 步骤：
  1. 打开最新样本 `/flow`
  2. 观察 `Canonical Fields`
- 应看到：
  - `loaded_axes`
  - `identity_delta`
  - `self_model_delta`
  - `drives_delta`
  - `policy_hint`
  - `response_tendency`
  - `host_arbitration_result`
  - `final_delivered_text`
- 不应看到：
  - 关键字段只能在 engineering fields 里翻找

## EXP-PROVIDER-RUNTIME-GATE

- 入口：repo runner
- 步骤：
  1. 运行 `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>`
  2. 查看 current report
- 应看到：
  - config / chat / execution / telegram / OpenEmotion evidence / continuity 都在一张 admission report 里
- 不应看到：
  - 只测 chat smoke 就宣称切换完成

## EXP-PROVIDER-RUNTIME-GATE-CLOSURE

- 入口：Telegram live + repo runner + `/flow`
- 步骤：
  1. `/new`
  2. 发送一个会产出文件或页面的任务
  3. 等待任务完成
  4. 紧接着发送一个 recent-result follow-up，例如“你觉得你做的这个页面怎么样”或“你还记得刚刚做的网页吗”
  5. 运行 `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>`
- 应看到：
  - current fresh window 里至少有一个 `task_mainline` 样本
  - follow-up 样本能绑定 `recent_result_context`
  - provider/runtime E2E gate 的 `followup_continuity_pass = true`
- 不应看到：
  - fresh window 里只有 `/new` 或普通聊天样本，却期待 gate 自动转绿
  - 没有 follow-up continuity pair 就把 live E2E gate 说成 fully closed
