# K / R / D + 新主链 MVS 执行工作包

```yaml
task_id: L3-20260331-KRD-MVS
created_at: "2026-03-31T18:02:13Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: in_progress
parent_authority: "Tasks/MVS_task_plan.md"
scope: "WP0/WP1 execution package"
```

---

## 角色定位

本目录不是独立主任务，而是 [MVS_task_plan.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/MVS_task_plan.md) 的执行层工作包。

- `MVS_task_plan.md`：唯一最终裁决源
- `krd_mvs_mainline/`：把 `WP0 / WP1` 拆成可执行工作包、状态台账、边界决策和交付物

## 真实目标

为 MVS 主线先收稳：

1. `WP0`：`proto_self.v2 + seed_v0_2` 的边界、契约、shim、决策日志
2. `WP1`：宿主壳的状态主权与表达主权收口

## 成功判据

- [x] 首批 mainline-reachable 模块已纳入 K/R/D 总表
- [x] 首批迁移矩阵已按当前仓库现状映射到真实承接路径
- [x] 首批详表已覆盖 K 池、EgoCore R 池、OpenEmotion R 池、D 池
- [x] 每个条目都写明归属、权威源、主链接入状态、替代物或删除条件
- [x] `WP0` 的 task-scoped 边界与契约文档已落地
- [x] `WP1` 方向复核完成
- [x] `memory_claim_gate` 已纳入宿主表达主链
- [x] `memory_claim_gate` 已拿到 Telegram E4 真实样本
- [x] readiness report 已形成并区分 E4 / E2-E3
- [x] `WP1` readiness 复算已形成明确负向结论与缺口映射
- [x] 最小 host-side intent gate 的 `allowed_claims / forbidden_claims / grounding` 已形成正式 source
- [x] 最小 host-side intent gate 已拿到 Telegram E4 真实样本
- [x] Telegram 自然语言 control-plane 已完成一轮 direct_real 收口：默认 `seed_v0_2`、裸 `继续/继续说` 留在 `chat_mainline`、slash-only `/resume /replace /append /cancel` 的无冲突路径已拿到 E4

## 当前层级与主链状态

```yaml
current_layer: verification_blocked_by_clean_window
main_chain_status: partially_enabled
enabled_status: true
trigger_evidence:
  - host-chain slices have direct_real Telegram evidence
  - natural-language continue and slash-only control changes have direct_real Telegram evidence
  - WP0 docs are repo-tracked
  - fresh 7d/1d shadow reports exist, source separation is wired, and response_intent now appends checker_family-tagged shadow entries
  - WP7/MVP12 controlled observation aggregate currently passes thresholds on runtime_harness direct_real windows
```

## Authority Source

- `Tasks/MVS_task_plan.md`
- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- 当前仓库实际代码布局：
  - `EgoCore/app/interaction`
  - `EgoCore/app/runtime_v2`
  - `EgoCore/app/openemotion_adapter`
  - `EgoCore/app/response_contract`
  - `OpenEmotion/openemotion/contracts`
  - `OpenEmotion/openemotion/proto_self_v2`

## 本轮范围

- `WP0` 边界与契约冻结文档
- `WP1` 基线与缺口台账
- `WP1` 方向复核
- `WP1` readiness report
- 不实施 `WP2+`
- 不删旧路径
- 不创建平行主线

## 下一步最小闭环动作

1. 收集带新 `traffic_source / observation_source / checker_family` 字段的 post-separation 非对抗观察窗
2. 基于该干净窗口重跑 `numeric_leak` 与 SRAP Shadow readiness
3. `pending_task_conflict` 下 `/replace /append /cancel` 的成功路径当前已暂缓，不作为本轮 blocker；在获得干净观察窗前，不推进 `WP2`

## 对齐说明

- `WP7 / MVP12` 的第一批代码脚手架已经落在正式主链后面：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
  - `developmental_tick / developmental_replay`
  - `developmental_shadow` shadow-only writeback
- 2026-04-01 已补第一份 controlled evidence runner：
  - `OpenEmotion/tools/run_mvp12_controlled_evidence.py`
  - 当前已生成一份受控 E3 证据包：
    - `OpenEmotion/artifacts/mvp12/controlled_20260401_215912/*`
  - 结论：`governance_violation_count = 0`、`replay_consistent = true`
- 2026-04-01 同一 verifier 已补第一段 controlled `direct_real` 观察窗：
  - `OpenEmotion/artifacts/mvp12/controlled_20260401_220610/*`
  - 当前结果：`direct_real_cycles = 4`、`governance_violation_count = 0`、`observation_ref_count = 8`
  - 口径仍是 controlled observation，不等于 live 行为放权
- 2026-04-01 verifier 已进一步支持多窗口 `direct_real`：
  - `OpenEmotion/artifacts/mvp12/controlled_20260401_221524/*`
  - 当前结果：`direct_real_window_count = 3`、`direct_real_cycles = 12`、`governance_violation_count = 0`
  - 口径仍然是 controlled direct_real，不可冒充 `WP7 E4`
- 2026-04-01 observation aggregator 已落地：
  - `OpenEmotion/tools/aggregate_mvp12_observations.py`
  - `OpenEmotion/artifacts/mvp12/observation_index.jsonl`
  - `OpenEmotion/artifacts/mvp12/controlled_observation_aggregate_current.md`
  - 当前 aggregate gate = `hold`
  - 当前 blocker 已明确收敛为：缺跨时段 `direct_real` windows，不再是缺 verifier / 缺聚合能力
- 2026-04-01 `MVP12/WP7` 证据源口径已重定义：
  - primary evidence source = 统一 runtime ingress/egress 主链
  - `Telegram` = transport-specific supplemental evidence
  - `direct_real` 不再等同于 Telegram session log；正式输入改为 `observation_record_v1`
- 2026-04-01 scripted runtime harness 已落地并通过最小主链验证：
  - `scripts/run_runtime_mainline_observation.py`
  - `scripts/runtime_mainline_observation_common.py`
  - 当前已生成 `OpenEmotion/artifacts/mvp12/runtime_harness_observation_current.jsonl`
  - `run_mvp12_controlled_evidence.py` 已优先消费该 observation log，并在 `controlled_20260401_235928/*` 产出新报告
  - 当前结果：`direct_real_source_type = observation_record_v1`、`direct_real_transport_sources = [runtime_harness]`、`governance_violation_count = 0`
  - 最新 aggregate 已重算为：`report_count = 7`、`direct_real_report_count = 6`、`direct_real_window_count_total = 12`、`governance_violation_total = 0`、`replay_consistent_all = true`、`span_hours = 14.098`、`gate_status = pass`
- 2026-04-02 `WP7/MVP12` 的 controlled observation thresholds 已达标：
  - 最新 aggregate 已从 `hold` 变为 `pass`
  - 这说明 cross-timespan `direct_real` windows 的 blocker 已对 `WP7` controlled observation 口径清除
  - 当前口径必须保持：这是 **controlled observation pass**，不是 live authority handoff，不是默认 live autonomy
- 2026-04-02 `MVP12-A` 已补第一条 controlled proactive followup draft 链：
  - OpenEmotion `developmental_tick` 现会输出 `background_thought_candidates`
  - EgoCore `initiative_arbiter` 只在 `gate allow + idle window 足够 + 无 active task + 不重复最近回复` 时，才经 `ResponsePlan / output_check` 生成 `controlled_shadow_delivery_draft`
  - 新 runner：`EgoCore/tools/run_mvp12_proactive_followup.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/proactive_followup_current.json` / `.md`
  - 当前验证结果：`26 passed`
  - 当前口径必须保持：**draft only**，不是 live proactive speaking，不是 Telegram unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补 `controlled idle scheduler`：
  - `ChatState` 现持久化最近 user/assistant/activity 时间戳
  - `RuntimeV2State` 新增 `pending_proactive_followup`
  - `EgoCore/app/runtime_v2/initiative_scheduler.py` 会在 controlled idle 窗口里把 proactive draft 挂成 pending state，而不是直接发送
  - 新 runner：`EgoCore/tools/run_mvp12_idle_scheduler.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/idle_scheduler_current.json` / `.md`
  - 当前验证结果：`30 passed`
  - 当前口径必须保持：**pending only**，不是 live idle scheduler，不是 Telegram unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补宿主侧 `controlled proactive delivery lane`：
  - `EgoCore/app/runtime_v2/proactive_delivery.py` 会消费 `pending_proactive_followup`
  - 新 runner：`EgoCore/tools/run_mvp12_controlled_delivery.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/controlled_proactive_delivery_current.json` / `.md`
  - 当前 smoke 结果：`delivery_result.status = artifact_emitted`、`transport_source = controlled_runner`、`pending_proactive_followup = null`
  - 当前验证结果：`11 passed`
  - 当前口径必须保持：**artifact only**，不是 live transport delivery，不是 Telegram unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补宿主侧 `proactive outbox lane`：
  - `RuntimeV2State` 新增 `pending_proactive_outbox_events`
  - `EgoCore/app/runtime_v2/proactive_outbox.py` 会把 `artifact_emitted` 的 delivery record 挂进 `host_proactive_outbox` queue
  - 新 runner：`EgoCore/tools/run_mvp12_proactive_outbox.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/proactive_outbox_current.json` / `.md`
  - 当前 smoke 结果：`outbox_result.status = queued`、`outbox_lane = host_proactive_outbox`、`pending_proactive_followup = null`
  - 当前验证结果：`15 passed`
  - 当前口径必须保持：**queued only**，不是 Telegram 自动发送，不是 live proactive speaking
- 2026-04-02 `MVP12-A` 已再补 `controlled outbox drain`：
  - `EgoCore/app/runtime_v2/proactive_outbox_drain.py` 会把 `host_proactive_outbox` 中的 queue 事件消费成 `simulated_outbox_record`
  - 新 runner：`EgoCore/tools/run_mvp12_proactive_outbox_drain.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/proactive_outbox_drain_current.json` / `.md`
  - 当前 smoke 结果：`drain_result.status = drained`、`transport_source = simulated_outbox_drain`、`pending_proactive_outbox_events = []`
  - 当前验证结果：`10 passed`
  - 当前口径必须保持：**simulated send only**，不是 Telegram 真发送，不是 live unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补宿主侧 `controlled Telegram transport bridge`：
  - `EgoCore/app/telegram_bot.py` 现可把 `host_proactive_outbox` queue 消费成真实 Telegram `send_message`
  - 新 runner：`EgoCore/tools/run_mvp12_telegram_proactive_transport.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/telegram_proactive_transport_current.json` / `.md`
  - 当前 smoke 结果：`telegram_transport_result.status = sent`、`transport_source = telegram`、`last_message_id = 3030`
  - 当前验证结果：`8 passed`
  - 当前口径必须保持：**host-governed Telegram transport connected**，不是 live idle scheduler，不是 autonomous unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补 `feature-flagged host-governed proactive Telegram auto cycle`：
  - `EgoCore/app/runtime_v2/proactive_telegram_cycle.py` 现在会在宿主 idle/busy gate 通过时串起 `scheduler -> delivery -> outbox -> Telegram drain`
  - `EgoCore/app/telegram_bot.py` 新增默认 `off` 的 `_mvp12_proactive_telegram_autodrain_enabled` 背景循环
  - 新 runner：`EgoCore/tools/run_mvp12_host_governed_proactive_telegram_cycle.py`
  - 新 artifact：`OpenEmotion/artifacts/mvp12/host_governed_proactive_telegram_cycle_current.json` / `.md`
  - 当前 smoke 结果：`cycle_result.status = sent`、`transport_gate.status = allow`、`transport_result.status = sent`、`last_message_id = 3031`
  - 当前验证结果：`6 passed`
  - 当前口径必须保持：**feature-flagged host-governed auto cycle only**，默认 `off`，不是默认 live idle scheduler，不是 autonomous unsolicited delivery
- 2026-04-02 `MVP12-A` 已再补 `host-governed proactive Telegram enable policy`：
  - 新增 `EgoCore/app/runtime_v2/proactive_telegram_policy.py`
  - `TelegramBot` 现在在 live autodrain 前先过 `enable_policy`
  - 当前 policy 最少覆盖：
    - global feature flag
    - chat allowlist：`EGO_MVP12_PROACTIVE_ALLOWED_CHAT_IDS`
    - session scope：`EGO_MVP12_PROACTIVE_ALLOWED_SESSION_PREFIXES`
    - recent history threshold：默认 `min_recent_user_turns=2`、`min_recent_assistant_replies=1`
  - 当前验证结果：`4 passed`
  - 当前口径必须保持：**enable policy only**，仍然默认 `off`，不等于默认 live autonomy
- 2026-04-02 `MVP12-A` allowlisted live host-governed proactive follow-up 已拿到 1 条真实 Telegram E4：
  - 会话：`telegram:dm:8420019401`
  - 真实日志已记录 `kind=telegram_proactive_delivery`、`reply_origin=proactive_followup`、`outbox_lane=host_proactive_outbox`、`transport_source=telegram`
  - 当前口径必须保持：**single E4 sample only**，不是 V5/E5 稳定结论，不等于默认 live autonomy
- 这不改变本执行包当前 scope 仍以 `WP0 / WP1` 为主。
- 当前口径必须保持：
  - `WP7` 还未正式启动
  - live 默认 `off`
  - 现有证据最高到受控主链 real-send E4，不得冒充默认开启的 `WP7` live autonomy
