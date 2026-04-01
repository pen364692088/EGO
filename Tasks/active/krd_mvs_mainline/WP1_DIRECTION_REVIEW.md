# WP1 方向复核

> authority: `Tasks/MVS_task_plan.md`
> scope: `WP1 宿主壳收稳（MVP11.5）`
> date: 2026-03-31
> conclusion: `direction_correct_with_gaps`

## 复核问题

当前已经落地的宿主主链切片，是否真的服务于 `WP1` 的目标:

- 收稳 `状态主权 + 表达主权`
- 不让 LLM 越权说话
- 不让 host shortcut、legacy verbalizer、task runtime 偷渡成聊天主链
- 不再另造第二套表达 contract

## Authority Source

- [MVS_task_plan.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/MVS_task_plan.md)
- [R-EGOCORE_HOST_CHAIN.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/krd_mvs_mainline/ITEMS/R-EGOCORE_HOST_CHAIN.md)
- [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
- [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
- [memory_claim_gate.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/memory_claim_gate.py)
- [chat_reply_engine.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/chat_reply_engine.py)
- [delivery_bridge.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/tools/delivery_bridge.py)
- [telegram_dm_8420019401.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl)

## 已证实

### 1. chat 已从 execution JSON 主链拆出
- 证据:
  - [chat_reply_engine.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/chat_reply_engine.py)
  - [test_runtime_v2_chat_mainline.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_runtime_v2_chat_mainline.py)
  - 2026-03-31 Telegram 真实样本
- 结论:
  - `InteractionKind.CHAT` 已进入 `llm.use_cases.chat`
  - 普通聊天不再复用 execution decision contract
  - 这是 `WP1` 方向正确的核心正证据

### 2. reply authority 已正式分层
- 证据:
  - [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
  - [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
- 结论:
  - 当前已稳定存在:
    - `model_chat`
    - `host_evidence`
    - `host_status`
    - `host_terminal`
    - `host_degraded_fallback`
  - `reply_origin` 也已分出 `chat_mainline / evidence_mainline / status_mainline / task_mainline`
  - 这证明“表达主权”已经开始收口到宿主 contract，而不是散在 verbalizer

### 3. evidence delivery 已从“有回复就算过”升级为可审计桥
- 证据:
  - [delivery_bridge.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/tools/delivery_bridge.py)
  - [test_tool_delivery_bridge.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_tool_delivery_bridge.py)
- 结论:
  - `tool success -> user-visible delivery` 已有单一路径和可审计字段
  - `fidelity_mode / fidelity_gap` 已能表达“送到了”与“内容失真了”的区别
  - 这和 `WP1` 的表达主权方向一致

### 4. evidence / chat / status 已初步隔离
- 证据:
  - [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
  - [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
  - 2026-03-31 Telegram 真实样本
- 结论:
  - 目录列出等 evidence turn 已能走 `host_evidence`
  - 后续普通聊天可以回到 `model_chat`
  - 方向上没有把 evidence host shortcut 偷渡成普通聊天主链

## 已证实但仍不完整

### 5. `ResponsePlan` 已经从宿主表达合同骨架升级到 `WP1` 主合同候选
- 当前已有字段:
  - `kind`
  - `reply_text`
  - `delivery_kind`
  - `authority_source`
  - `reply_authority`
  - `memory_claim_verdict`
  - `metadata`
- 当前状态:
  - 上述字段已并入 `ResponsePlan`
  - 现阶段缺口已从“字段未落地”收敛为“约束是否足以覆盖 SRAP / self_report_contract 目标”
- 判定:
  - 方向正确
  - 不需要重写主线
  - 继续在现有 `ResponsePlan` 上收口，而不是再造 `response_contract_v2`

### 6. `memory_claim_gate` 已进入正式宿主表达主链，但仍缺真实样本级证据
- 证据:
  - [memory_claim_gate.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/memory_claim_gate.py)
  - [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
  - [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py:563)
- 当前状态:
  - gate 已实现
  - 已接入 `build_direct_response_plan()`
  - 已接入 `build_runtime_result_response_plan()`
  - 已接入 `build_status_response_plan()`
  - focused tests 已覆盖
- 缺口:
  - 还没有 E4 真实样本证明它在 Telegram 主链上拦住了错误 memory claim

## 风险与未证实项

### 7. legacy verbalizer / social_chat_handler 仍在仓内
- 证据:
  - [verbalizer.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer.py)
  - [verbalizer_v3.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer_v3.py)
  - [social_chat_handler.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/handlers/social_chat_handler.py)
- 判定:
  - 目前未见它们重新主导 `chat_mainline` 的正证据
  - 但仍是回流风险
  - 应继续留在 `WP1` 方向复核范围，不应误报为“已完全剥离”

### 8. `numeric_leak = 0` 还没有当前口径的 readiness 证据
- `MVS_task_plan.md` 把它列为 `WP1` 验收条件之一
- 当前这轮没有看到新的 readiness rerun / readiness report / shadow report 正证据
- 结论:
  - 不能宣称 `WP1 ready`

## 总结判定

- 结论: **方向正确，不需要从零重写宿主主链**
- 理由:
  - 当前主线已经把 `chat / evidence / status / terminal` 的 owner 拆出来
  - `chat_mainline` 已不再复用 task JSON 决策器
  - `ResponsePlan` 已经成为唯一可继续扩展的宿主表达合同
- 当前真正缺口:
  - `self_report_contract / SRAP` 剩余约束尚未完全映射到 `ResponsePlan`
  - `memory_claim_gate` 尚未拿到 E4 真实样本
  - readiness 口径尚未复算，`numeric_leak = 0` 未证实

## 唯一最高优先级下一步

在现有主路径上继续，不重写:

1. 把 `speaker_mode / epistemic_status / commitment_level / must_include / must_not_upgrade / tone_bounds` 并入 `ResponsePlan`
2. 对 `self_report_contract / SRAP` 剩余约束做映射清单
3. 跑一轮 `WP1 readiness` 复算，明确 `numeric_leak` 与 SRAP Shadow 当前结论
