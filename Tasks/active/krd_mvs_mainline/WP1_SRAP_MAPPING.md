# WP1 SRAP / self_report -> ResponsePlan Mapping

> authority: `Tasks/MVS_task_plan.md`
> scope: `WP1 宿主壳收稳（MVP11.5）`
> date: 2026-04-01
> conclusion: `host_gate_connected_and_source_split_landed_but_not_ready`

## Summary

`ResponsePlan` 现在已经承载了 `WP1` 需要的核心表达字段，并且最小 host-side intent gate 已接入宿主输出主链，但当前结论仍只能到：

- **contract carrier 已成型**
- **最小 host-side SRAP gate 已接入**
- **尚未达到 readiness**
- **当前 shadow observation source 分离已落地，但 readiness 仍缺 post-separation 观察窗**

决定性证据有三条：

1. `ResponsePlan` 已正式带上 `speaker_mode / epistemic_status / commitment_level / must_include / must_not_upgrade / tone_bounds`
2. `EgoCore` 当前输出主链已在 `output_check` 中正式调用 `ResponseIntentChecker`
3. `allowed_claims / forbidden_claims / grounding` 已形成正式 host source，且当前 gate 已在最小 `model_chat + chat_mainline` 路径拿到 E4
4. `memory_claim_gate` 已在 Telegram 主链拿到 E4，且当前做法已从固定 fallback 升级为 chat mainline 自然规避

因此，`WP1` 当前不再是“字段未落地 / gate 未接 / 无真实样本”，而是“最小 gate 与 source 已接且有 E4，但 readiness 仍未收稳”。

## Authority Source

- [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
- [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
- [memory_claim_gate.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/memory_claim_gate.py)
- [response_intent_checker.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/response_intent_checker.py)
- [core.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/core.py)
- [test_response_intent_checker.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/test_response_intent_checker.py)
- [test_shadow_mode.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/test_shadow_mode.py)

## 映射表

| SRAP / self_report 约束 | 当前宿主承载点 | 状态 | 说明 |
|---|---|---|---|
| `speaker_mode` | `ResponsePlan.speaker_mode` | 已映射 | 已进入 direct/runtime/status plan builder |
| `epistemic_status` | `ResponsePlan.epistemic_status` | 已映射 | 已进入宿主表达合同 |
| `commitment_level` | `ResponsePlan.commitment_level` | 已映射 | 已进入宿主表达合同 |
| `must_not_upgrade` | `ResponsePlan.must_not_upgrade` | 已映射 | 现有默认值已覆盖 `epistemic/commitment/tone` |
| `tone_bounds` | `ResponsePlan.tone_bounds` + `output_check` | 已映射 | 已进入最小 host-side checker |
| `must_include` | `ResponsePlan.must_include` | 部分映射 | 已落成 tuple[str]，但丢失了 `type / position` 这类结构化语义 |
| `allowed_claims` | `ResponsePlan.metadata.intent_contract_source.allowed_claims` | 已映射 | 已由宿主单一 source builder 正式归一化 |
| `forbidden_claims` | `ResponsePlan.metadata.intent_contract_source.forbidden_claims` | 已映射 | 已由宿主单一 source builder 正式归一化 |
| `grounding / raw_state` | `ResponsePlan.metadata.intent_contract_source.grounding` | 部分映射 | grounding source 已形成，但当前仍以 host expression / proto-self mirror 为主，不等于完整 raw_state authority |
| `violation result` (`status / would_block / confidence / violation_class`) | `OutputCheckVerdict` | 已映射 | 宿主已生成 intent gate verdict 并写入交付证据 |
| `shadow logging / SRAP report` | OpenEmotion shadow path | 未接宿主主链 | 仍停在 OpenEmotion 侧 shadow 观察，不是 EgoCore host gate |

## 当前已证实

### 1. 宿主表达合同字段已形成

证据：

- [response_plan.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/response_plan.py)
- [test_response_contract.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_response_contract.py)

结论：

- `ResponsePlan` 已经不只是 skeleton
- 它已经能承载 `WP1` 要求的核心表达边界字段
- 这证明方向正确，不需要另造 `response_contract_v2`

### 2. `numeric_leak` checker 本体可工作，且最小 host-side gate 已接入

复算证据：

- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_response_intent_checker.py -k numeric`
  - `5 passed`
- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_response_intent_checker.py`
  - `47 passed`
- `env PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest -s -q EgoCore/tests/test_output_check.py EgoCore/tests/test_response_contract.py EgoCore/tests/test_runtime_v2_chat_mainline.py EgoCore/tests/test_runtime_v2_cli_and_telegram.py`
  - `31 passed, 1 warning`

结论：

- OpenEmotion 侧 `ResponseIntentChecker` 本体不是坏的
- `numeric_leak` 规则族在局部验证层面是成立的
- EgoCore host 输出主链现在也已经接上最小 `ResponsePlan -> ResponseIntentChecker`
- `allowed_claims / forbidden_claims / grounding` 已进入单一 host source builder

### 3. `memory_claim_gate` 已拿到 Telegram E4，且不再只能依赖固定 fallback

证据：

- [memory_claim_gate.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/memory_claim_gate.py)
- [chat_reply_engine.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/chat_reply_engine.py)
- [telegram_dm_8420019401.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl#L1686)

结论：

- 无 restore authority 时，Telegram 真链路已能禁止“已恢复/记得你”类对外声明
- 当前对话不会再退化成重复固定 fallback，而是保持 `model_chat + chat_mainline`
- 这证明 `WP1` 的表达主权收口又前进一步，但还不等于整体 readiness 成立

### 4. `ResponseIntentChecker` host gate 已拿到 Telegram E4

证据：

- [output_check.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response_contract/output_check.py)
- [telegram_dm_8420019401.jsonl#L1708](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl#L1708)

结论：

- 2026-04-01 真实样本里，模型原始输出给出了精确数值：
  - `joy=0.21 fear=0.08 arousal=0.44 dominance=0.37 stress=0.19`
- 最终 Telegram 交付被改写为 `我在听。`
- 这证明最小 host-side intent gate 已在 Telegram 主链真实触发
- 但当前仍是 targeted E4，不是稳定 `numeric_leak = 0`

## 当前决定性缺口

### 1. host-side gate 与 source 已接，但 `ResponseIntentChecker` 只覆盖最小 `model_chat` 路径

代码证据：

- `rg -n "check_intent\\(|ResponseIntentChecker\\(" EgoCore/app OpenEmotion/emotiond OpenEmotion/tests/testbot`
- 结果显示：
  - `EgoCore/app/response_contract/output_check.py` 已有调用
  - `OpenEmotion/emotiond/core.py` 有 shadow path 调用

结论：

  - 当前最小 SRAP intent gate 已进入 EgoCore 宿主正式输出主链
  - `allowed_claims / forbidden_claims / grounding` 也已形成正式 host source
  - 它已在最小 `model_chat + chat_mainline` 路径拿到 E4
- 但路径覆盖仍窄，且 readiness 仍未完成，因此 `WP1` 仍不能宣称“表达主权已 fully enforced”

### 2. SRAP shadow 代码级 blocker 已清，source 分离也已落地，但 readiness 仍缺干净观察窗

复算证据：

- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_response_intent_checker.py`
  - 结果：`47 passed`
- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_self_report_consistency.py`
  - 结果：`34 passed`
- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_shadow_mode.py`
  - 结果：`50 passed`
- `env PYTHONPATH=OpenEmotion python3 -m pytest -s -q --noconftest OpenEmotion/tests/test_adversarial_self_report.py`
  - 结果：`77 passed`
- `python3 OpenEmotion/emotiond/shadow_analyzer.py --days 7 --output OpenEmotion/artifacts/self_report/MVP11_5_shadow_readiness_current_7d.md`
  - 结果：`4484 checks / 979 violations / 720 numeric leaks`
- `python3 OpenEmotion/emotiond/shadow_analyzer.py --days 1 --output OpenEmotion/artifacts/self_report/MVP11_5_shadow_readiness_current_1d.md`
  - 结果：`558 checks / 231 violations / 137 numeric leaks`
- 分布检查：
  - 7d 窗口 `4127/4484` 条记录 `session_id=''`
  - 其余高频以 `test_* / parallel_*` 为主
- source 分离实现：
  - `SelfReportConsistencyChecker` / `ShadowLogger` 现已记录 `traffic_source / observation_source`
  - `shadow_analyzer.py` 现已支持按 source 过滤
  - `replay_validator.py` 已显式标记 `replay/replay`
  - 定向验证：`test_shadow_mode.py = 56 passed`

结论：

- 当前不能把上述绿色测试直接等同于 readiness 完成证据
- `numeric_leak = 0` 也不能仅凭定向 suite 通过就直接宣称稳定成立
- 当前 blocker 已从 shadow 语义失败转为 **需要新的 post-separation 观察窗，才能对 readiness 门槛做有效重判**
- 结合 [MVS_task_plan.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/MVS_task_plan.md) 的 `WP1` 交付物与验收要求，仍需对样本量、误报、漏报做明确裁决

## Readiness 裁决

- `WP1` 方向：正确
- `WP1` 当前 readiness：待重判
- 根因层级：不是字段缺失，也不再是“无真实样本”或“shadow tests 失败”；当前是 **host gate 已达 E4、代码级 shadow suite 已绿、source 分离已落地，但历史日志仍被 test/synthetic traffic 污染**

## 下一步唯一最高优先级动作

在现有主路径上继续，不再扩 contract 范围；下一步收集带新 source 字段的干净观察窗，再基于该窗口重跑 `WP1 readiness` 复算。
