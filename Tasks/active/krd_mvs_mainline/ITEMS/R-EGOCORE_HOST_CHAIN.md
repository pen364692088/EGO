## [R-EGOCORE-HOST] EgoCore 宿主主链壳

### 当前层级
- 实现级 / 验证级交界

### 主链接入状态
- 已接入

### 启用状态
- 部分启用，`chat_mainline` 已启用

### 真实触发证据
- evidence_id: Telegram real samples at 2026-03-31 19:47-19:50
- source_type: direct_real
- artifact_path:
  - `EgoCore/data/session_logs/telegram_dm_8420019401.jsonl`
  - `EgoCore/artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json`
  - `EgoCore/app/telegram_bot.py`
  - `EgoCore/app/telegram_runtime_bridge.py`
  - `EgoCore/app/runtime_v2/semantic_parser.py`
  - `EgoCore/app/runtime_v2/loop.py`
  - `EgoCore/app/runtime_v2/state.py`
  - `EgoCore/app/runtime_v2/chat_reply_engine.py`
  - `EgoCore/app/runtime_v2/chat_state.py`
  - `EgoCore/app/response_contract/response_plan.py`
  - `EgoCore/app/response_contract/output_check.py`
- proves:
  - 宿主已能真实驱动 Telegram 主链、run/item、tool delivery
  - response_plan / delivery / blocked / final 已有 E4 正证据
  - 普通聊天已能从 execution JSON 主链中拆出，进入 `model_chat + chat_mainline`
  - `reply_authority` 与 `reply_origin` 已在真实 Telegram 样本中对齐：
    - `在吗 / 能不能不要重复 / 活法是什么哈哈哈` -> `model_chat + chat_mainline`
    - `看一下目录...` -> `host_evidence + evidence_mainline`
- does_not_prove:
  - interaction control-plane 已有单一 authority
  - response contract 已从 renderer 中完全剥离
  - 自然聊天已达到 V5 稳定解决

### 当前确定项
- `InteractionKind`、`normalize_user_turn`、`ResponsePlan`、`output_check`、`tools.delivery_bridge` 已完成第一轮宿主 authority 收口
- `InteractionKind.CHAT` 已不再复用 task execution decision contract
- `telegram_bot._should_use_native_loop()` 的旧接线 bug 已修正，普通 chat 不再被 native loop 抢回旧路径
- `WP1` 方向复核结论已明确：方向正确，不需要从零重写宿主主链
- `ResponsePlan` 已吸收 `speaker_mode / epistemic_status / commitment_level / must_include / must_not_upgrade / tone_bounds`
- `memory_claim_gate` 已接入 `build_direct_response_plan / build_runtime_result_response_plan / build_status_response_plan`
- `ResponsePlan -> ResponseIntentChecker` 最小 host-side intent gate 已接到 `output_check`
- `ResponsePlan -> ResponseIntentChecker` 最小 host-side intent gate 已拿到 Telegram E4：模型原始数值输出会被宿主改写
- `ResponseIntentChecker` 现已向共享 `shadow_log.jsonl` 追加 `checker_family=response_intent` 观察记录
- `output_check` 的 Telegram-like subchain probe 已证实会写入 `traffic_source=real`、`observation_source=direct_real`
- `WP1` readiness 复算已经得到决定性负证据：当前不是“gate 未接”，也不再是“source 未形成 / 无 E4”，而是“最小 gate 已到 E4，但 readiness 未稳”
- session/task runtime 仍有继续拆层空间
- `memory_claim_gate` 已拿到 Telegram E4，且聊天已从固定 fallback 升级为自然规避错误 claim

### 关键未知
- chat 主链在更长窗口、更多 persona 形态下是否能稳定维持非机械回复而不回退到任务导向
- 最小 host-side intent gate 拿到 E4 后，`numeric_leak = 0` 是否成立
- `self_report_contract / SRAP` 当前还有哪些约束未真正并入并 enforce 到 `ResponsePlan`
- 当前还缺非对抗的 post-separation observation window；现有 `testbot` 窗口是 adversarial corpus，不能直接当 readiness 窗口

### 六问门禁
1. 归属是谁：EgoCore
2. 权威源是谁：宿主 control plane / response contract / runtime state
3. 与谁耦合：Telegram ingress、runtime_v2、response verbalizer、tools
4. 是否引入双主：当前存在风险
5. 是否把 shim 变成黑箱：当前存在 risk，如果不显式抽层会继续扩大
6. 失败谁兜底：宿主 blocked / delivery / verify gate

### 判定
- R

### 判定理由
- 同类问题已经多轮出现过：交付断链、状态混用、回复 authority 漂移
- 它承担的是宿主主链壳，不应继续靠零散 bridge 和 verbalizer 隐式持有 authority

### 本轮最小闭环动作
- 第一实现轮中，`InteractionKind`、最小 `ResponsePlan`、`output_check`、`chat_mainline` 已落地并拿到 E4
- 当前不再需要从零重写方向；最小 `ResponsePlan -> ResponseIntentChecker` 与 intent contract source 都已接入，下一最小闭环动作改为：
  - 收集带 `traffic_source / observation_source / checker_family` 的非对抗 post-separation observation window
  - 再重跑 `numeric_leak / SRAP Shadow / self_report_contract` readiness

### 完成定义
- `chat/task/admin/ask/wait/resume` 有唯一 authority
- final / ask / blocked / resume 的宿主回复骨架不再由 verbalizer 自由决定
- “我记得你/已恢复”类声明能被 gate 拦住或放行
- SRAP intent 约束不只存在于字段层，而是已形成宿主输出 gate

### 若为迁移件
- 替代物：
  - `interaction.classify_interaction`
  - `response_contract.response_plan`
  - `response_contract.memory_claim_gate`
- 迁移目标版本：MVS host-chain skeleton v1
- 删除条件：
  - 新 skeleton 达到 E3
  - Telegram 关键路径拿到 E4
  - 旧 generic fallback 不再主导
