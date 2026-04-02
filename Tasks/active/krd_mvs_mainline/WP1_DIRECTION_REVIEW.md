# WP1 方向复核

> authority: `Tasks/MVS_task_plan.md`
> scope: `WP1 宿主壳收稳（MVP11.5）`
> date: 2026-04-01
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
  - 2026-04-01 真实 Telegram 样本进一步证明：
    - `/proto` 默认口径已统一到 `default(seed_v0_2)`
    - 裸 `继续` 与 `继续说` 已留在 `chat_mainline`
    - `/resume` 与 `/replace /append /cancel` 已退出自然语言 control-plane，仅保留 slash-only 入口

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
  - 现阶段缺口已从“字段未落地”收敛为“约束是否足以覆盖 SRAP / self_report_contract 目标，并真正形成 host-side gate”
- 判定:
  - 方向正确
  - 不需要重写主线
  - 继续在现有 `ResponsePlan` 上收口，而不是再造 `response_contract_v2`

### 6. `memory_claim_gate` 已进入正式宿主表达主链，并已拿到 E4 真实样本
- 证据:
  - [memory_claim_gate.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/memory_claim_gate.py)
  - [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
  - [chat_reply_engine.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/chat_reply_engine.py)
  - [telegram_dm_8420019401.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl#L1686)
- 当前状态:
  - gate 已实现
  - 已接入 `build_direct_response_plan()`
  - 已接入 `build_runtime_result_response_plan()`
  - 已接入 `build_status_response_plan()`
  - focused tests 已覆盖
  - 2026-03-31 / 2026-04-01 Telegram 真实样本已证明：
    - 无 restore authority 时，不会对外声称“已恢复成功 / 记得你”
    - 普通聊天仍保持 `model_chat + chat_mainline`
    - 不再退化成重复的固定 `host_degraded_fallback`
- 缺口:
  - 仍缺“有 restore authority 时允许正向表述”的 E4 正样本

### 7. SRAP 核心字段已进入 `ResponsePlan`，且宿主最小 intent gate 已形成并拿到 E4
- 证据:
  - [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
  - [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
  - [response_intent_checker.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/response_intent_checker.py)
  - [core.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/core.py)
  - [WP1_SRAP_MAPPING.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/krd_mvs_mainline/WP1_SRAP_MAPPING.md)
- 当前状态:
  - `speaker_mode / epistemic_status / commitment_level / must_include / must_not_upgrade / tone_bounds` 已在宿主合同里
  - `violation verdict` 已进入 EgoCore host 输出主链
  - `allowed_claims / forbidden_claims / grounding` 已形成正式 host source
  - `ResponseIntentChecker` 现在同时存在于 OpenEmotion shadow/runtime 与 EgoCore host gate 路径
  - 2026-04-01 Telegram 真实样本已证明：模型原始输出会给出精确内部数值，最终 Telegram 交付被宿主改写为安全 fallback
- 判定:
  - `WP1` 当前不是字段缺失问题
  - 而是 host-side gate 已接且 source 已形成，并已拿到 E4；剩余问题收敛为 readiness / shadow 稳态

## 风险与未证实项

### 8. legacy verbalizer / social_chat_handler 仍在仓内
- 证据:
  - [verbalizer.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer.py)
  - [verbalizer_v3.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer_v3.py)
  - [social_chat_handler.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/handlers/social_chat_handler.py)
- 判定:
  - 目前未见它们重新主导 `chat_mainline` 的正证据
  - 但仍是回流风险
  - 应继续留在 `WP1` 方向复核范围，不应误报为“已完全剥离”

### 8a. slash-only control-plane 的 pending conflict 成功路径仍未做 E4
- 证据:
  - [telegram_bot.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py)
  - 2026-04-01 Telegram 真实样本
- 判定:
  - 目前已证实的只有：
    - `/resume` 无可恢复任务时的短错路径
    - `/replace /append /cancel` 无待裁决冲突时的短错路径
  - 尚未证实：
    - `pending_task_conflict` 真实存在时，三条 slash 命令的成功裁决路径
  - 该缺口当前已明确暂缓，不作为 `WP1` readiness blocker

### 9. `numeric_leak = 0` 当前已有 E4，但仍缺稳定性结论
- `MVS_task_plan.md` 把它列为 `WP1` 验收条件之一
- 本轮复算结果：
  - `test_response_intent_checker.py -k numeric`：`5 passed`
  - `test_response_intent_checker.py`：`47 passed`
  - `EgoCore` focused regression：`31 passed, 1 warning`
  - `test_shadow_mode.py`：并入复算后 `4 failed`
- 额外代码证据：
  - `EgoCore/app/response_contract/output_check.py` 已有 `ResponseIntentChecker` 调用
 - 真实样本证据：
   - [telegram_dm_8420019401.jsonl#L1708](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl#L1708)
   - 该样本里 `runtime_v2_result.reply_text` 为精确数值：
     - `joy=0.21 fear=0.08 arousal=0.44 dominance=0.37 stress=0.19`
   - 最终 `telegram_delivery` 被改写为 `我在听。`
   - `reply_authority = host_degraded_fallback`
- 结论:
  - 可以确认最小 host-side numeric leak gate 已达 E4
  - 仍不能宣称 `numeric_leak = 0` 稳定成立
  - 也仍不能宣称 `WP1 ready`

### 10. 当前 `WP1` blocker 已从 shadow 代码回归收敛到 post-separation 非对抗观察窗缺失

- 2026-04-01 复算：
  - `OpenEmotion/tests/test_response_intent_checker.py`：`47 passed`
  - `OpenEmotion/tests/test_shadow_mode.py`：先前 `4 failed, 46 passed`，最新已恢复为 `50 passed`
  - `OpenEmotion/tests/test_self_report_consistency.py`：`34 passed`
  - `OpenEmotion/tests/test_adversarial_self_report.py`：`77 passed`
- 2026-04-01 fresh shadow 报告：
  - 7d：`4484 checks / 979 violations / 720 numeric leaks`
  - 1d：`558 checks / 231 violations / 137 numeric leaks`
- 2026-04-01 新进展：
  - `self_report_consistency_checker.py` 已显式记录 `traffic_source / observation_source`
  - `shadow_analyzer.py` 已支持按 source 过滤
  - `replay_validator.py` 已显式写入 `replay/replay`
  - 定向验证：`test_shadow_mode.py = 56 passed`
  - `ResponseIntentChecker` 已改为向共享 `shadow_log.jsonl` 追加 `checker_family=response_intent`
  - `testbot/test_intent_alignment_e2e.py` 已显式标记 `traffic_source=synthetic`、`observation_source=testbot`
  - 新报告 [MVP11_5_shadow_readiness_response_intent_testbot_1d.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/self_report/MVP11_5_shadow_readiness_response_intent_testbot_1d.md) 显示：`105 checks / 44 violations / 0 numeric leaks`
  - local Telegram-like subchain probe 已证实 `output_check` 会写入 `traffic_source=real`、`observation_source=direct_real`、`checker_family=response_intent`
- 同步分布检查：
  - 7d 窗口 `4127/4484` 条记录 `session_id=''`
  - 其余高频条目以 `test_* / parallel_*` 为主
  - 时间分布主要集中在 `2026-03-29` 和 `2026-04-01` 的测试突发窗口
- 判定：
  - 宿主主链当前已经具备：
    - `memory_claim_gate` 的 Telegram E4
    - `ResponseIntentChecker` / intent gate 的 Telegram E4
    - `response_intent` shadow producer
  - OpenEmotion 侧 `SRAP shadow` 代码级回归已清，当前不应再把 blocker 表述成“shadow tests 失败”
  - 结合 [MVS_task_plan.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/MVS_task_plan.md) 的 `WP1` 交付物与验收要求，当前剩余问题转为 **是否已有带新 source 字段的干净非对抗观察窗，能支持门槛裁决**
  - `testbot` 窗口当前不能直接用于 readiness，因为它是 adversarial corpus，设计目标是触发 violation，不是近真实稳态分布

## 总结判定

- 结论: **方向正确，不需要从零重写宿主主链**
- 理由:
  - 当前主线已经把 `chat / evidence / status / terminal` 的 owner 拆出来
  - `chat_mainline` 已不再复用 task JSON 决策器
  - `ResponsePlan` 已经成为唯一可继续扩展的宿主表达合同
- 当前真正缺口:
  - shadow/readiness 仍缺 post-separation 干净非对抗观察窗
  - `numeric_leak = 0` 仍未达到可用于 readiness 裁决的干净观测口径

## 唯一最高优先级下一步

在现有主路径上继续，不重写:

1. 保持 `ResponsePlan` 作为唯一宿主表达合同，不另造第二份 contract
2. 收集带新 `traffic_source / observation_source / checker_family` 字段的干净非对抗观察窗，再基于该窗口重算 `WP1 readiness`
3. 若样本量 / 误报 / 漏报门槛仍不清，再补 authority 口径或观察证据
