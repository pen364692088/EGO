# MVS / Proto-Self 任务安排

> 状态：MVS 主线唯一最终裁决源
> 执行层工作包：`Tasks/active/krd_mvs_mainline/` + 各阶段 child packs

## 一句话主线
先把 **EgoCore 宿主壳收稳**，再把 **OpenEmotion 的 Proto-Self Kernel** 以最小闭环方式接进主链，先拿到 **MVS（最小可持续主体）** 的真实证据，再进入 Developmental Sandbox。

## 裁决关系
- 本文件负责 `WP0~WP14` 的阶段、依赖、Gate、证据等级和停止条件。
- `Tasks/active/krd_mvs_mainline/` 只负责把 `WP0/WP1` 拆成可执行工作包与状态台账，不与本文件并列裁决。
- 本任务按 **主线原地替换** 推进，不开平行实现、不走双轨切换、不保留 shadow implementation。

## 当前真实状态
- 正式核心只有两个：**EgoCore**（对外宿主 / 运行时 / 执行 / 治理）与 **OpenEmotion**（identity / self-model / memory / appraisal / reflection 本体）。
- 当前主线已从 **MVS** 推进到其后的受治理扩展阶段；当前最新已收口阶段是 `WP13/MVP18`，其 authority freeze、`T10` formal owner package、`T20` proto-self embodied contract integration、`T30` EgoCore runtime bridge、`T40` legacy demotion / compat map、`T50` causal proof、`T60` single controlled observation、`T70` batch observation / aggregate 与 `T80` closeout / QA baseline 均已完成，当前已进入 `maintenance_mode`，不是 live embodied autonomy。
- 当前下一阶段已冻结为 `WP14/MVP19` 的 authority/task package，范围收窄为 `Cross-Axis Self-Integration / Self-Maintenance Arbitration`；当前只完成 authority freeze、phase-detail task plan 与执行包建档，claim ceiling 固定为 `authority_frozen / task_package_ready`，不代表 owner/runtime 实现、主链接线、`E4/E5`、observation、或 maintenance mode。
- 宿主壳已有多轮主链切片真实生效证据；Proto-Self 侧当前正式现实是 **`proto_self.v2 + seed_v0_2`**。
- 旧 `openemotion/proto_self/` 仍可存在，但从本计划开始只作为 compatibility / deletion inventory，对未来功能不再是正式落点。
- 所有验收必须遵守 E0-E6 证据分级，结论强度不得高于证据层级。

## 执行顺序
1. **WP0 v2 边界与契约冻结**
2. **WP1 宿主壳收稳（MVP11.5）**
3. **WP2 Proto-Self Kernel v2 / seed_v0_2 重标定**
4. **WP3 EgoCore 适配与 trace / replay 接线**
5. **WP4 升级到 7+2 状态（world / boundary / viability / meta / counterfactual）**
6. **WP5 反事实反思与因果测试**
7. **WP6 MVS 主链样本级生效**
8. **WP7 Developmental Sandbox**
9. **WP8 Persistent Self-Model**
10. **WP9 Endogenous Drives + Self-Maintenance**
11. **WP10 Reflective Self / Counterfactual Self**
12. **WP11 Host-governed Developmental Continuity（MVP16 第一正式切片）**
13. **WP12 Social Self / Other-Modeling（MVP17 第一正式切片）**
14. **WP13 Embodied Loop / Environment Coupling（MVP18 第一正式切片）**
15. **WP14 Cross-Axis Self-Integration / Self-Maintenance Arbitration（MVP19 第一正式切片）**

---

## WP0：v2 边界与契约冻结
**目标**：防止双真相源、接口漂移和 v1/v2 双规划口径。

**归属**：EgoCore + OpenEmotion 联合

**任务**
- 冻结权威源表：identity / self-model / memory / appraisal / reflection 归 OpenEmotion；运行时 / 工具 / response plan / audit 归 EgoCore。
- 给新能力补 6 问门禁：归属、权威源、耦合点、双主风险、shim 风险、失败兜底。
- 正式冻结 contract 族：
  - `event_v1`
  - `result_v1`
  - `proto_self.v2`
  - `proto_self_seed.v0.2`
  - `KernelOutput / UpdatePacketV2 / seed_event`
- 显式回答：
  - OpenEmotion 哪些字段是本体真相源
  - EgoCore 哪些字段是宿主真相源
  - 旧 `proto_self/` 哪些文件仍是 compatibility-only，哪些进入 D 池
- 在 `WP0` 完成前，禁止继续扩主体语义或新增 adapter 暗协议。

**交付物**
- `Tasks/active/krd_mvs_mainline/contracts/proto_self.v2.md`
- `Tasks/active/krd_mvs_mainline/contracts/examples/event_v1_user_message.json`
- `Tasks/active/krd_mvs_mainline/contracts/examples/result_v1_policy_hint.json`
- `Tasks/active/krd_mvs_mainline/contracts/examples/update_packet_v2_seed_user_event.json`
- `Tasks/active/krd_mvs_mainline/contracts/examples/update_packet_v2_exec_result.json`
- `Tasks/active/krd_mvs_mainline/SHIM_REGISTER.md`
- `Tasks/active/krd_mvs_mainline/BOUNDARY_DECISION_LOG.md`

**验收**
- Research Gate：每个核心字段都能回答“谁是权威源”。
- Engineering Gate：样例 payload 可跑静态校验，且引用到 repo-tracked canonical source。
- 证据层级目标：E0 -> E1

---

## WP1：宿主壳收稳（MVP11.5）
**目标**：先把“状态主权 + 表达主权”收稳，不让 LLM 越权说话。

**归属**：EgoCore

**已承认纳入 WP1 基线的主链切片**
- `InteractionKind`
- `normalize_user_turn`
- `ResponsePlan`
- `output_check`
- `tools.delivery_bridge`
- `chat_mainline`
- `reply_authority / reply_origin`
- evidence / status / chat 隔离

**任务**
- 跑满 SRAP Shadow 观察期，但不另造第二套表达 contract。
- 做一次方向复核，确认已落地主链切片确实服务“状态主权 + 表达主权”，没有把 host shortcut、legacy verbalizer 或 task runtime 偷渡成聊天主链。
- 将 `self_report_contract / SRAP` 相关约束收敛进现有宿主 contract，不再并行维护 `response_contract_v2`。
- 把以下表达约束统一收口到 `ResponsePlan`：
  - `speaker_mode`
  - `epistemic_status`
  - `commitment_level`
  - `must_include`
  - `must_not_upgrade`
  - `tone_bounds`
- 补齐 `memory_claim_gate`，并形成 readiness report。

**交付物**
- `ResponsePlan` 作为唯一宿主表达合同的设计与落地说明
- SRAP Shadow 报告
- testbot 场景与回放结果
- readiness report

**验收**
- `numeric_leak = 0`
- 样本量、误报 / 漏报达到可进入下一步的门槛
- 能明确说明哪些能力已到 E4，哪些仍停留在 E2/E3

---

## WP2：Proto-Self Kernel v2 / seed_v0_2 重标定
**目标**：确认当前 `proto_self_v2 + seed_v0_2` 是否已满足 MVS 最小主体核目标，不新开 v3，也不回退到旧 `proto_self/`。

**归属**：OpenEmotion

**任务**
- 只在 `openemotion/proto_self_v2/` 内继续收口。
- 做方向审计，必须回答：
  - 当前 `seed_v0_2` 是否只是 subject profile / 轻语义层，还是已经承担了最小主体核职责
  - 当前 `state / kernel / schemas / trace_types` 是否足以承担 `WP2` 的正式 MVS kernel
  - 若不足，缺口在 state shape、kernel loop、output boundary，还是 trace / replay
- 若需要补齐，继续沿现有 `proto_self_v2` 路径原地替换，不再新增平行路径。
- 明确禁止：直接工具执行命令、直接 response plan、直接高风险动作裁决。

**交付物**
- `proto_self_v2` 方向审计
- v2 gap list
- kernel / state / contract test matrix

**验收**
- T1 身份连续性
- T2 经历可塑性
- T3 drive / viability 对倾向有因果作用
- T4 repeated pattern strengthens cycle
- T5 kernel never returns direct tool execution
- 证据层级目标：E1 -> E2

---

## WP3：EgoCore 适配与 trace / replay 接线
**目标**：把 `proto_self_v2` 挂到壳里，但保证 replay / audit / Governor 不被破坏。

**归属**：EgoCore（宿主）+ OpenEmotion（配合）

**任务**
- 继续使用现有 adapter / trace / replay 路径，不新建并行 adapter。
- 让 `KernelOutput.trace_payload` 写进主链可审计产物。
- replay 时优先读 trace，不允许用当前 store 重算旧轮结果。
- host-side mirror 只缓存，不拥有解释权。
- 把 `policy_hint / response_tendency` 接入 response plan 前的决策链，但不得绕过 Governor。

**交付物**
- adapter
- trace bridge
- replay regression

**验收**
- 不破坏 deterministic / replay
- Proto-Self 输出只能影响排序与倾向，不能绕过 Governor
- 证据层级目标：E2 -> E3

---

## WP4：升级到 7+2 状态
**目标**：把 Proto-Self 从“会更新”升级到“有更像主体的承重结构”。

**归属**：OpenEmotion

**新增状态**
- `world_model`
- `boundary_model`
- `viability_appraisal_field`
- `meta_model`
- `counterfactual_buffer`

**任务**
- 补 `self / world / boundary` 三重模型
- 把 `drive_field` 升级为 viability-driven field
- 加入 attribution / ownership / controllability 字段
- 加入 meta 监控：不确定性、模式切换、confidence calibration
- 保留统一递归更新器，不拆成官僚模块堆

**交付物**
- state / schema 升级
- reducer / updater 升级
- probe tests

**验收**
- self / world attribution test
- boundary breach recovery test
- viability intervention changes policy test
- appraisal intervention changes policy test
- 证据层级目标：E2 -> E3

---

## WP5：反事实自我与反思写回
**目标**：让反思不只是日志，而是真的改变下一轮自己。

**归属**：OpenEmotion

**任务**
- `maybe_reflect()` 升级为：
  - self-counterfactual
  - regret estimate
  - proposed adjustment with expected viability gain
- 增加触发条件：
  - external failure
  - identity conflict
  - viability drop
  - repeated cycle failure
- 把反思结果写回：
  - mode
  - confidence
  - memory promotion threshold
  - boundary rigidity

**交付物**
- counterfactual reflection 模块
- compare / no-reflection baseline 报告

**验收**
- 失败后下一轮倾向发生预期变化
- 反思不是自由文本，而是结构化状态更新候选
- 证据层级目标：E2 -> E3

---

## WP6：MVS 主链样本级生效
**目标**：拿到真实主链证据，但不夸大为长期稳定。

**归属**：EgoCore + OpenEmotion

**任务**
- 先接 testbot / sandbox 近真实链路
- 再选一个受控真实入口跑样本
- 保存最小证据包：
  - 原始入口事件
  - 标准化 event
  - KernelOutput
  - response plan
  - 实际发送 / 行为记录
  - timeline / tape / replay artifact
- 建立失败归因：
  - `boundary_error`
  - `authority_source_error`
  - `contract_error`
  - `replay_mismatch`
  - `wording_overclaim`

**交付物**
- `MVS_E4_REPORT.md`
- 成功样本 + 失败样本
- 回归清单

**验收**
- 只在有真实主链证据时才写“已接主链 / 已启用 / 样本级生效”
- 没有 E5 不得写“稳定无未知”
- 证据层级目标：E4

---

## WP7：Developmental Sandbox
**前提**：只有 WP6 拿到 MVS 样本级生效后才启动。

**归属**：OpenEmotion（主体）+ EgoCore（壳）

**child authority**
- `Tasks/MVP12_task_plan.md`
- `Tasks/active/mvp12_developmental_sandbox/`

**任务**
- 正式接线落点固定为：`runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- `WP7/MVP12` 的主证据源固定为统一 `runtime` ingress/egress 主链；`Telegram` 只作为 transport-specific claim 的补充证据
- `OpenEmotion/emotiond/developmental_core/` 仅作为实现库复用；`emotiond.daemon` 不再是正式 runtime owner
- 在 `proto_self_v2` 中新增隔离子状态：`developmental_shadow / shadow_self`
- 新增受控事件：
  - `developmental_tick`
  - `developmental_replay`
- 只输出：
  - latent hypotheses
  - self-model update candidates
  - cycle candidates
  - internal tensions
  - spontaneous rollouts
  - `background_thought_candidates`
- 允许一条受治理的 host-side proactive draft 子链：
  - `developmental_tick`
  - `background_thought_candidates`
  - `initiative_arbiter`
  - `controlled_idle_scheduler`
  - `pending_proactive_followup`
  - `controlled_proactive_delivery_lane`
  - `host_proactive_outbox_lane`
  - `controlled_outbox_drain`
  - `controlled_telegram_transport_bridge`
  - `feature_flagged_host_governed_proactive_telegram_auto_cycle`
  - `host_governed_proactive_telegram_enable_policy`
  - `ResponsePlan / output_check`
  - controlled proactive draft / delivery / outbox / simulated-send artifact / host-governed Telegram send record / host-governed auto-cycle send record
- 不拥有最终说话权
- 不拥有最终执行权
- 不直接生成 `response_plan`
- 不直接改正式 proto-self 状态；只允许 shadow-only writeback
- 所有内部发育产物都写 trace / replay
- 入口仅允许 controlled observation runner / replay runner；live 默认 off
- `direct_real` 重新定义为：任何非 mock、非旁路、真实穿过正式 runtime ingress/egress 主链并留下完整 `observation_record_v1` 的样本；不再等同于 Telegram session log

**交付物**
- sandbox runner
- scripted runtime mainline observation harness
- `observation_record_v1` contract
- `developmental_shadow` 状态与 trace contract
- `background_thought_candidate` contract
- host-side `initiative_arbiter` controlled draft runner
- controlled idle scheduler runner
- `pending_proactive_followup` state contract
- controlled proactive delivery runner
- host proactive outbox runner
- `pending_proactive_outbox_events` state contract
- controlled outbox drain runner
- controlled Telegram proactive transport runner
- host-governed proactive Telegram auto-cycle runner
- `artifacts/mvp12/` 下的 cycle / pool / shadow / replay / gate artifacts
- 观察报告

**验收**
- 在无外部输入时出现非随机内源活动
- 可在 controlled mode 下产出与最近对话 / tension 相关的 proactive draft candidate
- 可在 controlled idle 窗口里生成 `pending_proactive_followup`，但不得直接发送
- 可由宿主侧 controlled lane 将 `pending_proactive_followup` 消费成 `artifact_emitted` 的 delivery record，但不得直接走 transport
- 可由宿主侧 outbox lane 将 `artifact_emitted` 的 delivery record 挂入 `host_proactive_outbox` queue
- 可由 controlled drain 将 `host_proactive_outbox` queue 消费成 `simulated_outbox_record`，但不得冒充真实 outbox_record
- 可由宿主侧 controlled Telegram transport bridge 将 `host_proactive_outbox` queue 消费成真实 `send_message/outbox_record`，但不得冒充 live autonomous send
- 可由 feature-flagged host-governed proactive Telegram auto cycle 在宿主 idle/busy gate 通过时自动串起 scheduler -> delivery -> outbox -> Telegram drain，但默认必须 `off`，且不得冒充默认 live autonomy
- auto cycle 的 enable policy 必须由宿主明确裁决，至少覆盖：global feature flag、chat allowlist/session scope、最近聊天历史阈值；不得仅凭 transport gate 自动放开
- 不破坏当前主链 determinism / gate / safety
- 真实动作仍归 EgoCore 与 Governor 链
- runtime harness 样本可进入 `direct_real` 主证据路径
- proactive output 仍必须是 host-governed draft / host-governed send，不得成为 live direct reply authority
- transport-specific claim 仍需 Telegram 样本
- 证据层级目标：E3 -> E4（受控样本）

**当前状态（2026-04-03）**
- `scripts/run_runtime_mainline_observation.py`、`OpenEmotion/tools/run_mvp12_controlled_evidence.py`、`OpenEmotion/tools/aggregate_mvp12_observations.py` 已按原路径重跑
- 最新 aggregate 为：`report_count = 7`、`direct_real_report_count = 6`、`direct_real_window_count_total = 12`、`governance_violation_total = 0`、`replay_consistent_all = true`、`span_hours = 14.098`
- `stability_gate.status = pass`；这意味着 `WP7/MVP12` 的 controlled observation thresholds 当前已达标
- `WP7/MVP12` 当前可在 formal runtime sandbox + controlled observation 轴上收口进入 `maintenance_mode`
- 后续新增样本只进入 `Tasks/active/mvp12_developmental_sandbox/MAINTENANCE_LEDGER.md`，不自动触发 scope reopen
- 这不等于 live authority handoff，也不等于默认 live autonomy
- Telegram 侧另有 1 条 allowlisted host-governed proactive follow-up 真实 E4 样本；该样本只作为 transport/proactive path 的补充证据，不改变 controlled observation 的主证据定义

---

## WP8：Persistent Self-Model
**前提**：只有 `WP7/MVP12` 达到 controlled observation `pass` 后才启动。

**归属**：OpenEmotion（主体 owner）+ EgoCore（runtime / adapter 桥接）

**child authority**
- `Tasks/MVP13_task_plan.md`
- `Tasks/active/mvp13_persistent_self_model/`

**任务**
- `MVP13` 仍属于同一条 MVS 主线，不得另起平行主体或平行 authority 主线。
- 正式 owner 固定为：
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/schemas/self_model.schema.json`
- formal read path 固定为：
  - owner self-model store
  - `runtime_v2 -> proto_self_runtime`
  - `UpdatePacketV2.runtime_summary.self_model_context`
  - `proto_self_v2` read-only consumption
- formal write path 固定为：
  - `proto_self_v2` 只产出 `self_model_delta` / `self_model_update_candidates`
  - 经 `self_model_update_gate`
  - gate 通过后才写回 formal owner store
- `proto_self_v2.state.self_model` 不升格为第二真相源；`WP8 Phase 1` 中仅将其解释为 formal owner state 的 runtime-local projection。
- `WP8 Phase 1` 只使用当前 formal owner schema 已有字段：
  - `schema_version`
  - `identity_handle`
  - `capabilities`
  - `limitations`
  - `active_goals`
  - `standing_commitments`
  - `tool_authority_boundary`
  - `dependency_map`
  - `confidence_by_domain`
  - `known_unknowns`
  - `created_at`
  - `last_modified_at`
  - `modification_audit_trail`
- 旧 `MVP13 mirror / dual-write` 线全部降级为 reference-only：
  - `OpenEmotion/artifacts/mvp13/TASK.md`
  - `OpenEmotion/tools/mvp13_*`
  - `OpenEmotion/emotiond/self_model/*`
  - `OpenEmotion/emotiond/self_model_mirror.py`
  - `EgoCore/egocore/runtime/self_model_manager.py`
- `WP8 Phase 1` 不把 legacy 字段集升格为正式 contract：
  - `behavioral_tendencies`
  - `active_tensions`
  - `continuity_trace`
  - `revision_history`
  - `SelfModelManager`
- `MVP13` 仍不得：
  - 直接控制 final reply
  - 直接控制 tool execution
  - 绕过 Governor
  - 重新启用旧 `mirror / dual-write` 作为正式 owner path

**交付物**
- `Tasks/MVP13_task_plan.md`
- `Tasks/active/mvp13_persistent_self_model/README.md`
- `Tasks/active/mvp13_persistent_self_model/STATUS.md`
- `Tasks/active/mvp13_persistent_self_model/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp13_persistent_self_model/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp13_persistent_self_model/contracts/SELF_MODEL_OWNER_CONTRACT.md`
- `Tasks/active/mvp13_persistent_self_model/contracts/SELF_MODEL_UPDATE_GATE.md`
- `Tasks/active/mvp13_persistent_self_model/contracts/SELF_MODEL_REPLAY_CONTRACT.md`
- `Tasks/active/mvp13_persistent_self_model/cards/*.md`

**验收**
- `MVS_task_plan.md` 中已正式出现 `WP8: Persistent Self-Model`
- `Tasks/MVP13_task_plan.md` 已声明 parent-child 裁决关系
- `Tasks/active/mvp13_persistent_self_model/` 已声明：
  - `parent_authority = Tasks/MVS_task_plan.md`
  - `predecessor = WP7/MVP12`
  - `same_subject_line = true`
  - `not_parallel_track = true`
- 旧 `MVP13` mirror / dual-write 线被显式标记为 reference-only
- formal owner / read path / write path / compatibility semantics / no-bypass rules 全部在文档中锁死
- subtask cards 达到 subagent-ready，不留实现级空白决策
- 证据层级目标：E0 -> E1（文档冻结） -> E2（实现启动） -> E3（本地 formal-owner 证据包） -> E4（真实主链触发） -> E5（稳定观察）

**当前状态（2026-04-03）**
- `WP7/MVP12` 当前已达到 controlled observation `pass`
- `WP8/MVP13` 当前已完成 `T00/T10/T20/T30/T40/T50/T60/T70/T80`，并已通过 `repo_authored + open_license` scenario bank 的 controlled batch observation 拿到 `V5/E5` formal owner writeback 稳定样本集
- 当前 `WP8` 口径是：controlled observation `pass` 且可收口进入维护态；这不等于 live autonomy，也不等于 transport evidence
- `WP8` 后续新增样本只进入 `Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md`，不自动触发 scope reopen
- batch 中出现的 chat provider `429/401` 继续归类为外部预算层风险，不回灌为 `WP8` blocker，除非它导致 formal owner writeback 主链失效
- 若继续推进主线，下一步不再是扩 `WP8`，而是先定义 `WP9/MVP14` authority / contract

---

## WP9：Endogenous Drives + Self-Maintenance
**前提**：只有 `WP8/MVP13` 进入 `maintenance_mode` 后才启动。

**归属**：OpenEmotion（drive / maintenance owner target）+ EgoCore（runtime / Governor / delivery）

**child authority**
- `Tasks/MVP14_task_plan.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/`

**本阶段当前范围**
- authority / contract / boundary freeze 已完成
- formal owner package / proto-self contract / runtime bridge / legacy demotion / causal proof 已完成
- controlled observation batch 已通过，当前进入 `maintenance_mode`；live 默认 off
- 不把新能力塞回 `WP8`

**任务**
- capability ownership 固定为：
  - endogenous drive state / drive history / priority snapshot / maintenance candidate generation 归 `OpenEmotion/openemotion/endogenous_drives/*`
  - runtime scheduling / final reply / tool execution / transport 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP9` phase-detail authority：`Tasks/MVP14_task_plan.md`
  - version spec：`OpenEmotion/roadmap/versions/MVP14.spec.yaml`
  - technical reference：`OpenEmotion/docs/mvp14/*`
- migration/reference surfaces 固定为：
  - `OpenEmotion/emotiond/drives/*`
  - `OpenEmotion/emotiond/drive_adapter.py`
  - `OpenEmotion/emotiond/drive_homeostasis.py`
  - `OpenEmotion/emotiond/homeostasis.py`
- input / output contract 先冻结，再开实现：
  - 输入只允许结构化内部状态、self-model projection、continuity / drift / debt / replay 等信号
  - 输出只允许 governed priority / maintenance candidates / drive audit artifacts
  - 不允许输出 final reply / tool command / transport directive
- `WP8` 边界冻结：
  - `WP8` 继续是 `maintenance_mode`
  - 新样本只进 maintenance ledger
  - 不因 `WP9` 启动而改写 `WP8` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - drive bypass of Governor
  - drive-authored privileged execution

**交付物**
- `Tasks/MVP14_task_plan.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/README.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/STATUS.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/contracts/DRIVE_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/contracts/DRIVE_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/contracts/DRIVE_IO_CONTRACT.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/contracts/WP8_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/contracts/LOCKED_NON_RELEASES.md`

**验收**
- `STATUS / README / task plan` 三方口径一致，不把 `WP8` 的轴内 `E5` 误写成全局成熟
- `WP8` 新增样本只进入 maintenance ledger，不自动触发 `WP8` scope reopen
- provider `429/401` 被持续标注为外部预算层风险，不回灌为 `WP8` blocker
- `WP9` 从 authority / contract 开始，而不是把新能力塞进 `WP8`
- 文档中没有出现“因为 `WP8 pass`，所以 OpenEmotion 可以直接说话 / 直接拿 transport claim”这类边界回退
- 证据层级目标：E0 -> E1（authority / contract freeze）

**当前状态（2026-04-03）**
- `WP9/MVP14` 当前层级是 `closure`
- 当前状态是 `maintenance_mode`
- formal owner 已迁到 `OpenEmotion/openemotion/endogenous_drives/*`
- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 已观测到 `endogenous_drive_writeback`
- 首个 controlled observation 结果见 `OpenEmotion/artifacts/mvp14/mvp14_controlled_observation_current.md`
  - `status = pass`
  - `verification_level = V4`
  - `evidence_level = E4`
  - `gate_verdict = allow_writeback`
  - `maintenance_candidate_present = true`
  - `replay_valid = true`
- controlled batch 结果见 `OpenEmotion/artifacts/mvp14/mvp14_controlled_observation_batch_current.md`
  - `report_count = 3`
  - `accepted_count = 3`
  - `replay_consistent_count = 3`
  - `maintenance_candidate_present_count = 3`
  - `invariant_violation_count = 0`
  - `verification_level = V5`
  - `evidence_level = E5`
- 当前 blocker：controlled observation 范围内无主 blocker；provider `429/401` 继续记为外部预算层风险，不回灌为 `WP9` 主链 blocker

---

## WP10：Reflective Self / Counterfactual Self
**前提**：只有 `WP9/MVP14` 进入 `maintenance_mode` 后才启动。

**归属**：OpenEmotion（reflective self / counterfactual owner target）+ EgoCore（runtime / Governor / delivery）

**child authority**
- `Tasks/MVP15_task_plan.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/`

**本阶段当前范围**
- formal owner package
- replay / audit / proposal state
- bounded proto-self reflective contract
- EgoCore runtime reflective bridge
- legacy reflection / counterfactual surfaces demotion
- paired causal validation
- controlled observation
- 不把新能力塞回 `WP9`

**任务**
- capability ownership 固定为：
  - reflection queue / diagnosis records / counterfactual records / revision proposal candidates / reflection history / replay-linked audit 归 `OpenEmotion/openemotion/reflective_self/*`
  - runtime scheduling / Governor / final reply / tool execution / transport 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP10` phase-detail authority：`Tasks/MVP15_task_plan.md`
  - version spec：`OpenEmotion/roadmap/versions/MVP15.spec.yaml`
  - technical reference：`OpenEmotion/docs/mvp15/*`
- migration/reference surfaces 固定为：
  - `OpenEmotion/emotiond/reflection_engine/*`
  - `OpenEmotion/emotiond/reflection_adapter.py`
  - `OpenEmotion/emotiond/reflection_shadow.py`
  - `OpenEmotion/emotiond/self_counterfactual.py`
  - `OpenEmotion/emotiond/core.py`
  - `OpenEmotion/emotiond/api.py`
  - `OpenEmotion/emotiond/workspace.py`
- input / output contract 先冻结，再开实现：
  - 输入只允许结构化自我状态、drive projection、developmental / replay / maintenance / decision evidence
  - 输出只允许 governed reflection deltas、diagnosis / counterfactual / revision proposals、confidence / maintenance priority hints 与 trace artifacts
  - 不允许输出 final reply / tool command / transport directive / direct policy rewrite
- `WP9` 边界冻结：
  - `WP9` 继续是 `maintenance_mode`
  - 新样本只进 maintenance ledger
  - 不因 `WP10` 启动而改写 `WP9` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - reflection bypass of Governor
  - counterfactual-authored action selection
  - unconstrained self-rewrite

**交付物**
- `Tasks/MVP15_task_plan.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/README.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/STATUS.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/contracts/REFLECTION_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/contracts/REFLECTION_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/contracts/REFLECTION_IO_CONTRACT.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/contracts/WP9_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp15_reflective_self_counterfactual/contracts/LOCKED_NON_RELEASES.md`

**验收**
- `STATUS / README / task plan` 三方口径一致，不把旧 `MVP15` bounded / shadow 线误写成当前 formal owner maturity
- `WP9` 新增样本只进入 maintenance ledger，不自动触发 `WP9` scope reopen
- provider `429/401` 被持续标注为外部预算层风险，不回灌为 `WP9` blocker
- `WP10` 保持 proposal-only reflective path，不放开 live autonomy / direct reply / broader transport claims
- 文档中没有出现“因为 `WP10` 观察到 reflective writeback，所以 OpenEmotion 可以直接反思发言 / 直接拿 transport claim”这类边界回退
- 证据层级目标：E1 -> E5（current mainline observation stable on the controlled axis）

**当前状态（2026-04-03）**
- `WP10/MVP15` 当前层级是 `closure`
- 当前状态是 `maintenance_mode`
- 旧 `MVP15` reflection / counterfactual infra、shadow artifact、bounded `/plan` / `/decision/target` consumer 与 paired relevance proof 都存在，但全部属于 legacy/reference input，不自动构成当前 formal owner / current-runtime mainline 证据
- 当前 formal owner target 固定为 `OpenEmotion/openemotion/reflective_self/*`
- 当前 formal owner package、bounded reflective consumer、runtime bridge 与 governed reflective writeback 已落地
- 当前 causal proof 报告为 `OpenEmotion/artifacts/mvp15/mvp15_causal_validation_current.md`，结果 `status = pass`、`verification_level = V3`、`evidence_level = E3`
- 当前 single controlled observation 报告为 `OpenEmotion/artifacts/mvp15/mvp15_controlled_observation_current.md`，结果 `status = pass`、`verification_level = V4`、`evidence_level = E4`、`gate_verdict = allow_writeback`、`replay_valid = true`
- 当前 batch controlled observation 报告为 `OpenEmotion/artifacts/mvp15/mvp15_controlled_observation_batch_current.md`，结果 `status = pass`、`verification_level = V5`、`evidence_level = E5`、`report_count = 3`、`accepted_count = 3`、`proposal_discipline_consistent_count = 3`、`behavioral_authority_none_count = 3`
- 当前 blocker：controlled observation 范围内无主 blocker；provider `429/401` 继续记为外部预算层风险，不回灌为 `WP10` 主链 blocker

---

## WP11：Host-governed Developmental Continuity
**前提**：只有 `WP10/MVP15` 进入 `maintenance_mode` 后才启动。

**归属**：OpenEmotion（developmental self / continuity owner target）+ EgoCore（runtime / Governor / delivery / observation）

**child authority**
- `Tasks/MVP16_task_plan.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/`

**本阶段当前范围**
- formal developmental owner package
- bounded developmental continuity / intake / promotion semantics
- bounded proto-self developmental contract
- EgoCore runtime developmental bridge
- legacy developmental surfaces demotion
- causal validation
- controlled observation
- scenario-bank batch observation
- maintenance closeout baseline
- 不把新能力塞回 `WP7~WP10`

**任务**
- capability ownership 固定为：
  - developmental self state / continuity state / identity-preserving adaptation proposals / trajectory summary / promotion semantics / developmental governance ledger 归 `OpenEmotion/openemotion/developmental_self/*`
  - runtime scheduling / proposal intake / Governor / final reply / tool execution / delivery / observation aggregate 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP11` phase-detail authority：`Tasks/MVP16_task_plan.md`
  - version spec：`OpenEmotion/roadmap/versions/MVP16.spec.yaml`
  - technical reference：`OpenEmotion/docs/mvp16/*`
- migration/reference surfaces 固定为：
  - `OpenEmotion/emotiond/developmental/*`
  - `OpenEmotion/emotiond/developmental_core/*`
  - `OpenEmotion/tools/mvp16_daily_check.py`
  - `OpenEmotion/tools/mvp16_real_trajectory_sync.py`
  - `OpenEmotion/tools/mvp16_anomaly_handler.py`
  - `OpenEmotion/tools/persistence_restart_experiments.py`
  - `OpenEmotion/tools/causal_intervention_experiments.py`
  - `Tasks/active/SELF_AWARE_STEP_07*`
  - `Tasks/active/SELF_AWARE_STEP_08*`
- input / output contract 先冻结，再开实现：
  - 输入只允许结构化 `developmental_context`、`developmental_self_context`、`self_model_context`、`endogenous_drive_context`、`reflective_self_context` 与 runtime evidence
  - 输出只允许 governed developmental deltas / proposal candidates / continuity snapshot / priority hints / audit entries / writeback candidate / trace artifacts
  - 不允许输出 final reply / tool command / transport directive / authority escalation
- `WP10` 边界冻结：
  - `WP7~WP10` 继续是 `maintenance_mode`
  - 新样本只进各自 maintenance ledger
  - 不因 `WP11` 启动而改写 `WP7~WP10` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - developmental bypass of Governor
  - developmental-authored action selection
  - unconstrained self-rewrite

**交付物**
- `Tasks/MVP16_task_plan.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/README.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/STATUS.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/contracts/DEVELOPMENTAL_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/contracts/DEVELOPMENTAL_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/contracts/DEVELOPMENTAL_IO_CONTRACT.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/contracts/WP10_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/contracts/LOCKED_NON_RELEASES.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T00_AUTHORITY_FREEZE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T10_FORMAL_OWNER_PACKAGE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T20_PROTO_SELF_CONTRACT_INTEGRATION.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T30_EGOCORE_RUNTIME_BRIDGE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T40_LEGACY_DEMOTION_AND_COMPAT_MAP.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T50_CAUSAL_VALIDATION.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T60_CONTROLLED_OBSERVATION_SINGLE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T70_BATCH_OBSERVATION_AND_AGGREGATE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T80_CLOSEOUT_AND_QA_BASELINE.md`
- `Tasks/active/mvp16_host_governed_developmental_continuity/cards/T90_SUBAGENT_ASSIGNMENT.md`

**验收**
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP11`
- `Tasks/MVP16_task_plan.md`、执行包 `README / STATUS / contracts / cards` 口径一致
- `WP7~WP10` 继续处于 `maintenance_mode`，没有被 `WP11` reopen
- 旧 `emotiond/developmental/*`、`developmental_core/*`、`mvp16_*` 工具与旧 admission docs 被显式标成 reference-only 或 input-only
- `WP11` 文档没有把 `bounded developmental continuity` 漂成“完整开放发展式自我”
- 证据层级目标：E1 -> E5（controlled axis only）

**当前状态（2026-04-03）**
- `WP11/MVP16` 当前层级是 `maintenance`
- 当前状态是 `maintenance_mode`
- 当前 formal owner 已固定并落地于 `OpenEmotion/openemotion/developmental_self/*`
- 当前 formal runtime read surface 固定为 `runtime_summary.developmental_self_context`
- 当前正式主链已形成 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- 当前证据栈：
  - causal proof `V3/E3`
  - single controlled observation `V4/E4`
  - batch controlled observation `V5/E5`
- 当前 legacy `MVP16` specs / docs / tools / admission materials 仍全部属于 technical reference 或 reference-only input，不自动构成 formal owner / current-runtime mainline 证据
- 当前 blocker：受控轴内无主 blocker；仅保留 maintenance verification / bugfix / evidence refresh

---

## WP12：Social Self / Other-Modeling
**前提**：只有 `WP11/MVP16` 进入 `maintenance_mode` 后才启动。

**归属**：OpenEmotion（social self / relation / trust / commitment / repair owner target）+ EgoCore（runtime / Governor / delivery / observation）

**child authority**
- `Tasks/MVP17_task_plan.md`
- `Tasks/active/mvp17_social_self_other_modeling/`

**本阶段当前范围**
- authority / contract / boundary freeze
- formal social owner package 落地
- bounded proto-self social contract target 定义
- EgoCore runtime social bridge target 定义
- historical social / relation materials demotion
- subagent-ready task decomposition
- 不把新能力塞回 `WP11`

**任务**
- capability ownership 固定为：
  - relation memory / other-model state / trust state / commitment state / repair state / social boundary state / relationship update semantics 归 `OpenEmotion/openemotion/social_self/*`
  - runtime scheduling / outward response / tool execution / transport / Governor / observation aggregate 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP12` phase-detail authority：`Tasks/MVP17_task_plan.md`
  - technical reference：`OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`、`OpenEmotion/roadmap/VersionRoadmap.md`、`OpenEmotion/docs/archive/mvp9/MVP9_SPEC.md`
  - 当前没有 repo-tracked `MVP17` version spec；若后续补写，也不得自动覆盖 `Tasks/*` authority
- phase 1 scope 固定为：
  - `trust`
  - `commitment`
  - `repair`
  - bounded `other-model` / `social role continuity` 只作为结构化状态，不做泛化心智解读
- migration/reference surfaces 固定为：
  - `EgoCore/app/response/relationship_context.py`
  - `EgoCore/app/handlers/social_chat_handler.py`
  - `EgoCore/app/runtime/repair_context_manager.py`
  - `EgoCore/app/bridges/openemotion_bridge.py`
  - `OpenEmotion/emotiond/db.py`
  - `OpenEmotion/emotiond/state.py`
  - `OpenEmotion/emotiond/api.py`
  - `OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
  - `OpenEmotion/docs/archive/mvp9/MVP9_SPEC.md`
- input / output contract 先冻结，再开实现：
  - 输入只允许结构化 `social_context`、`social_self_context`、`self_model_context`、`endogenous_drive_context`、`reflective_self_context`、`developmental_self_context` 与 runtime evidence
  - 输出只允许 governed social deltas / relation update candidates / trust-commitment snapshot / social policy hints / repair proposal candidates / writeback candidate / trace artifacts
  - 不允许输出 final reply / tool command / transport directive / authority escalation / autonomous outreach
- `WP11` 边界冻结：
  - `WP7~WP11` 继续是 `maintenance_mode`
  - 新样本只进各自 maintenance ledger
  - 不因 `WP12` 启动而改写 `WP7~WP11` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - autonomous social outreach
  - social bypass of Governor
  - unconstrained other-model mind-reading
  - unrestricted commitment escalation

**交付物**
- `Tasks/MVP17_task_plan.md`
- `Tasks/active/mvp17_social_self_other_modeling/README.md`
- `Tasks/active/mvp17_social_self_other_modeling/STATUS.md`
- `Tasks/active/mvp17_social_self_other_modeling/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp17_social_self_other_modeling/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp17_social_self_other_modeling/contracts/SOCIAL_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp17_social_self_other_modeling/contracts/SOCIAL_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp17_social_self_other_modeling/contracts/SOCIAL_IO_CONTRACT.md`
- `Tasks/active/mvp17_social_self_other_modeling/contracts/WP11_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp17_social_self_other_modeling/contracts/LOCKED_NON_RELEASES.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T00_AUTHORITY_FREEZE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T10_FORMAL_OWNER_PACKAGE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T20_PROTO_SELF_CONTRACT_INTEGRATION.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T30_EGOCORE_RUNTIME_BRIDGE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T40_LEGACY_DEMOTION_AND_COMPAT_MAP.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T50_CAUSAL_VALIDATION.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T60_CONTROLLED_OBSERVATION_SINGLE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T70_BATCH_OBSERVATION_AND_AGGREGATE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T80_CLOSEOUT_AND_QA_BASELINE.md`
- `Tasks/active/mvp17_social_self_other_modeling/cards/T90_SUBAGENT_ASSIGNMENT.md`

**验收**
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP12`
- `Tasks/MVP17_task_plan.md`、执行包 `README / STATUS / contracts / cards` 口径一致
- `WP7~WP11` 继续处于 `maintenance_mode`，没有被 `WP12` reopen
- historical social / relation materials 被显式标成 technical reference、reference-only 或 input-only
- `WP12` 文档没有把 bounded social self 漂成 live social autonomy、direct reply authority 或 broader transport maturity
- 证据层级目标：E0 -> E1（authority / contract freeze）

**当前状态（2026-04-04）**
- `WP12/MVP17` 当前层级是 `maintenance`
- 当前状态是 `maintenance_mode`
- 当前 formal owner target 固定为 `OpenEmotion/openemotion/social_self/*`
- 当前正式主链接线目标固定为 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- 当前 phase 1 只冻结 `trust / commitment / repair`，不实现更宽的 social self
- 当前已证实：`OpenEmotion/openemotion/social_self/*` 的 owner / store / governance / replay 基础、`proto_self_v2` bounded social contract、EgoCore runtime thin bridge、legacy social / relation surfaces 的 reference-only / input-only demotion、trust / commitment / boundary shifts 对 bounded downstream weighting 的 causal proof、single controlled mainline `V4/E4` 样本、以及 repeated controlled mainline social proposal-only writeback `V5/E5` aggregate 均已落地；`WP12_QA_BASELINE.md` 与 `MVP17_COMPLETION_CURRENT.*` 已冻结
- 当前 blocker：formal owner + proposal-only social writeback + controlled observation 轴内无主 blocker；后续只做 maintenance verification，不扩 `WP12` scope

---

## 串行依赖
- `WP0 -> WP2 -> WP3 -> WP6 -> WP7 -> WP8` 必须串行
- `WP8 -> WP9 -> WP10 -> WP11 -> WP12` 必须串行
- `WP1` 可与 `WP2 / WP3` 并行，但其表达 contract 不得反向覆盖 Proto-Self 边界定义
- `WP4 / WP5` 在 `WP2` 基础上推进

## 当前不做
- 开放发展式自我
- 强社会自我
- 具身闭环
- 无限工具自治
- 复杂情绪文案层
- 完整开放发展式自我
- live social autonomy
- direct social reply authority
- 任何让 OpenEmotion 直接执行现实动作的设计
- 在 `WP8` 中复活旧 `MVP13 mirror / dual-write` 作为正式 owner path
- 因 `WP8` 收口就放开 `WP9` 的 direct reply / broader transport authority
- 因 `WP11` 收口就放开 `WP12` 的 social outreach / broader transport authority

## 最小里程碑定义
- **里程碑 A**：`WP0 + WP1`
- **里程碑 B**：`WP2 + WP3`
- **里程碑 C**：`WP4 + WP5`
- **里程碑 D**：`WP6`
- **里程碑 E**：`WP7`
- **里程碑 F**：`WP8`
- **里程碑 G**：`WP9`
- **里程碑 H**：`WP10`
- **里程碑 I**：`WP11`
- **里程碑 J**：`WP12`
- **里程碑 K**：`WP13`

---

## WP13：Embodied Loop / Environment Coupling
**前提**：只有 `WP12/MVP17` 完成 maintenance institutionalization 后才启动。

**归属**：OpenEmotion（embodied owner / consequence semantics / boundary pressure owner target）+ EgoCore（runtime / Governor / delivery / transport / environment adjudication）

**child authority**
- `Tasks/MVP18_task_plan.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/`

**本阶段当前范围**
- authority / contract / boundary freeze
- formal embodied owner package target 定义
- bounded action-consequence / resource-boundary proto-self contract target 定义
- EgoCore runtime embodied bridge target 定义
- historical consequence / intervention materials demotion
- subagent-ready task decomposition
- 不把新能力塞回 `WP12`

**任务**
- capability ownership 固定为：
  - embodied state / environment coupling state / resource pressure state / boundary pressure state / action consequence memory / self-world boundary semantics 归 `OpenEmotion/openemotion/embodied_self/*`
  - runtime scheduling / outward response / tool execution / transport / Governor / observation aggregate 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP13` phase-detail authority：`Tasks/MVP18_task_plan.md`
  - technical reference：`OpenEmotion/roadmap/VersionRoadmap.md`
  - 当前没有 repo-tracked `MVP18` version spec；若后续补写，也不得自动覆盖 `Tasks/*` authority
- phase 1 scope 固定为：
  - `resource / slack pressure`
  - `action -> consequence` bounded writeback
  - `self / world boundary pressure` 的结构化 proposal
- migration/reference surfaces 固定为：
  - `OpenEmotion/emotiond/consequence.py`
  - `OpenEmotion/emotiond/science/interventions.py`
  - `OpenEmotion/roadmap/VersionRoadmap.md`
- input / output contract 先冻结，再开实现：
  - 输入只允许结构化 `embodied_self_context`、`environment_context`、`self_model_context`、`endogenous_drive_context`、`reflective_self_context`、`developmental_self_context`、`social_self_context` 与 runtime evidence
  - 输出只允许 governed embodied deltas / consequence update candidates / resource-boundary snapshot / embodied policy hints / repair-or-stabilize proposal candidates / writeback candidate / trace artifacts
  - 不允许输出 final reply / tool command / transport directive / authority escalation / embodied takeover
- `WP12` 边界冻结：
  - `WP7~WP12` 继续是 `maintenance_mode`
  - 新样本只进各自 maintenance ledger
  - 不因 `WP13` 启动而改写 `WP7~WP12` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - embodied takeover
  - sustained proactive outreach
  - autonomous tool expansion
  - ungoverned environment action authority

**交付物**
- `Tasks/MVP18_task_plan.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/README.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/STATUS.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/contracts/EMBODIED_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/contracts/EMBODIED_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/contracts/EMBODIED_IO_CONTRACT.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/contracts/WP12_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/contracts/LOCKED_NON_RELEASES.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T00_AUTHORITY_FREEZE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T10_FORMAL_OWNER_PACKAGE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T20_PROTO_SELF_CONTRACT_INTEGRATION.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T30_EGOCORE_RUNTIME_BRIDGE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T40_LEGACY_DEMOTION_AND_COMPAT_MAP.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T50_CAUSAL_VALIDATION.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T60_CONTROLLED_OBSERVATION_SINGLE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T70_BATCH_OBSERVATION_AND_AGGREGATE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T80_CLOSEOUT_AND_QA_BASELINE.md`
- `Tasks/active/mvp18_embodied_loop_environment_coupling/cards/T90_SUBAGENT_ASSIGNMENT.md`

**验收**
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP13`
- `Tasks/MVP18_task_plan.md`、执行包 `README / STATUS / contracts / cards` 口径一致
- `WP7~WP12` 继续处于 `maintenance_mode`，没有被 `WP13` reopen
- historical consequence / intervention materials 被显式标成 technical reference、reference-only 或 input-only
- `WP13` 文档没有把 host-governed embodied loop 漂成 live autonomy、direct reply authority 或 broader transport maturity
- 证据层级目标：E0 -> E1（authority / contract freeze）

**当前状态（2026-04-04）**
- `WP13/MVP18` 当前层级是 `implementation`
- 当前状态是 `observation_started`
- 当前 formal owner target 固定为 `OpenEmotion/openemotion/embodied_self/*`
- 当前正式主链接线目标固定为 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- 当前 phase 1 只冻结 `resource/slack pressure`、`action -> consequence` bounded writeback、`self/world boundary pressure` proposal；不实现更宽的 embodied loop
- 当前已证实：`WP12` 已完成 maintenance institutionalization；当前 `WP13` 已完成 authority / contract / boundary freeze，已落地 `OpenEmotion/openemotion/embodied_self/*` formal owner package，已把 `runtime_summary.embodied_self_context / environment_context` 通过 `proto_self_v2` bounded contract 接入 `KernelOutputV2` 与 trace，并已通过 `verify_mvp18_mainline_wiring.py` 证明旧 consequence / intervention historical surfaces 仍是 `technical reference / reference-only / input-only`
- 当前已证实：`OpenEmotion/openemotion/embodied_self/*` 的 owner / store / governance / replay 基础、`proto_self_v2` bounded embodied contract、EgoCore runtime thin bridge、legacy consequence / intervention historical surfaces 的 reference-only / input-only demotion，以及 resource/slack pressure、consequence memory、self/world boundary pressure 对 bounded downstream embodied weighting 的 causal proof 均已落地；当前 causal artifact 见 `OpenEmotion/artifacts/mvp18/mvp18_causal_validation_current.md`，结果为 `status = pass`、`verification_level = V3`、`evidence_level = E3`、`pair_count = 4`、`passed_count = 4`
- 当前已证实：`OpenEmotion/tools/run_mvp18_controlled_observation.py` 已生成首个 controlled runtime-mainline embodied observation artifact，当前 `OpenEmotion/artifacts/mvp18/mvp18_controlled_observation_current.md` 的结果为 `status = pass`、`verification_level = V4`、`evidence_level = E4`、`embodied_writeback_gate = allow_writeback`、`embodied_proposal_present = true`、`proposal_only_discipline_consistent = true`、`behavioral_authority_none = true`、`bounded_influence_present = true`、`replay_valid = true`
- 当前已证实：`OpenEmotion/tools/run_mvp18_controlled_observation_batch.py` 已生成 repeated controlled runtime-mainline embodied aggregate artifact，当前 `OpenEmotion/artifacts/mvp18/mvp18_controlled_observation_batch_current.md` 的结果为 `status = pass`、`verification_level = V5`、`evidence_level = E5`、`report_count = 3`、`accepted_count = 3`、`proposal_only_discipline_count = 3`、`behavioral_authority_none_count = 3`、`bounded_influence_present_count = 3`
- 当前 blocker：`WP13` 仍缺 `T80` closeout / QA baseline；当前不能宣称收口或 `maintenance_mode`

---

## WP14：Cross-Axis Self-Integration / Self-Maintenance Arbitration
**前提**：只有 `WP13/MVP18` 进入 `maintenance_mode` 后才启动。

**归属**：OpenEmotion（cross-axis integration semantics / arbitration owner target）+ EgoCore（runtime / session / task / tool / transport / outward response / gate / audit / real-world adjudication）

**child authority**
- `Tasks/MVP19_task_plan.md`
- `Tasks/active/mvp19_cross_axis_self_integration/`

**本阶段当前范围**
- authority / contract / boundary freeze
- formal selfhood integration owner package target 定义
- bounded proto-self selfhood integration contract target 定义
- EgoCore runtime selfhood integration bridge target 定义
- upstream `WP8~WP13` read-surface freeze
- legacy / compat / upstream read-only register
- subagent-ready task decomposition
- 不把新能力塞回 `WP8~WP13`

**任务**
- capability ownership 固定为：
  - `integration_state / cross_axis_priority_state / proposal_conflict_state / stabilize_explore_balance / repair_progress_balance / social_boundary_balance / integrated_tendency_proposal / axis_arbitration_hints / integration_ledger` 归 `OpenEmotion/openemotion/selfhood_integration/*`
  - runtime / session / task / tool / transport、outward response contract、ask / wait / block / escalate、trace / replay / gate / audit / maintenance ledger、real-world execution / risk adjudication 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP14` phase-detail authority：`Tasks/MVP19_task_plan.md`
  - technical reference：`Tasks/MVP13_task_plan.md`、`Tasks/MVP14_task_plan.md`、`Tasks/MVP15_task_plan.md`、`Tasks/MVP16_task_plan.md`、`Tasks/MVP17_task_plan.md`、`Tasks/MVP18_task_plan.md`、`OpenEmotion/roadmap/VersionRoadmap.md`
  - 当前没有 repo-tracked `MVP19` version spec；若后续补写，也不得自动覆盖 `Tasks/*` authority
- phase 1 formal intake 固定为：
  - `runtime_summary.self_model_context`
  - `runtime_summary.endogenous_drive_context`
  - `runtime_summary.reflective_self_context`
  - `runtime_summary.developmental_self_context`
  - `runtime_summary.social_self_context`
  - `runtime_summary.embodied_self_context`
  - `runtime_summary.maintenance_context`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.idle_window`
  - `WP8`: self-model confidence / identity consistency / known-unknowns constraints
  - `WP9`: `candidate_bias_terms` / `priority_snapshot` / `self_maintenance_candidate`
  - `WP10`: `revision_proposal_candidates` / `confidence_adjustment_hints` / `maintenance_priority_hints`
  - `WP11`: `developmental_proposal_candidates` / `developmental_priority_hints` / `developmental_continuity_snapshot`
  - `WP12`: `relation_update_candidates` / `repair_proposal_candidates` / `social_policy_hints` / `trust_commitment_snapshot`
  - `WP13`: `consequence_update_candidates` / `repair_or_stabilize_proposal_candidates` / `embodied_policy_hints` / `resource_boundary_snapshot`
- phase 1 formal outputs 固定为：
  - `self_integration_delta`
  - `cross_axis_priority_snapshot`
  - `proposal_conflict_snapshot`
  - `integrated_policy_hints`
  - `integrated_tendency_proposal`
  - `axis_arbitration_hints`
  - `integration_audit_entries`
  - `self_integration_writeback_candidate`
  - `trace_payload.selfhood_integration_context`
- output discipline 固定为：
  - `proposal_only = true`
  - `behavioral_authority = none`
  - `required_gate = self_integration_writeback_gate`
  - `axis_arbitration_hints` 只是 advisory，不能直接改写 `WP8~WP13` owner state
  - 不允许输出 final reply / tool command / transport directive / authority escalation
- phase 1 arbitration policy 固定为 `stability-first`：
  - priority 1：若 `WP8` 低 confidence，或 `WP9/WP13` 出现高 maintenance / resource / boundary pressure，则优先 `stabilize / conserve / guard / review`
  - priority 2：否则，`WP12` commitment / repair risk 可抬高 repair bias
  - priority 3：否则，`WP11` growth / continuity 可抬高 growth bias
  - priority 4：`WP10` reflective revision 只作 modifier，不是 phase 1 的更高优先轴
- `WP8~WP13` 边界冻结：
  - `WP8~WP13` 都继续是 maintenance / frozen upstreams
  - 新样本只进各自 maintenance ledger
  - 不因 `WP14` 启动而改写 `WP8~WP13` formal owner、formal read/write path、或 evidence claim
- 显式锁定当前仍不放开的能力：
  - live autonomy
  - OpenEmotion direct reply authority
  - broader transport claims
  - direct mutation of `reflective_self/*`、`developmental_self/*`、`social_self/*`、`embodied_self/*`、`self_model/*`、`endogenous_drives/*`
  - direct reply / tool / transport / authority escalation

**交付物**
- `Tasks/MVP19_task_plan.md`
- `Tasks/active/mvp19_cross_axis_self_integration/README.md`
- `Tasks/active/mvp19_cross_axis_self_integration/STATUS.md`
- `Tasks/active/mvp19_cross_axis_self_integration/LEGACY_REFERENCE_REGISTER.md`
- `Tasks/active/mvp19_cross_axis_self_integration/SUBAGENT_ASSIGNMENT.md`
- `Tasks/active/mvp19_cross_axis_self_integration/contracts/SELFHOOD_INTEGRATION_CAPABILITY_OWNERSHIP.md`
- `Tasks/active/mvp19_cross_axis_self_integration/contracts/SELFHOOD_INTEGRATION_AUTHORITY_SOURCE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/contracts/SELFHOOD_INTEGRATION_IO_CONTRACT.md`
- `Tasks/active/mvp19_cross_axis_self_integration/contracts/WP8_WP13_BOUNDARY_FREEZE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/contracts/LOCKED_NON_RELEASES.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T00_AUTHORITY_FREEZE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T10_FORMAL_OWNER_PACKAGE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T20_PROTO_SELF_CONTRACT_INTEGRATION.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T30_EGOCORE_RUNTIME_BRIDGE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T40_LEGACY_DEMOTION_AND_COMPAT_MAP.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T50_CAUSAL_VALIDATION.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T60_CONTROLLED_OBSERVATION_SINGLE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T70_BATCH_OBSERVATION_AND_AGGREGATE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T80_CLOSEOUT_AND_QA_BASELINE.md`
- `Tasks/active/mvp19_cross_axis_self_integration/cards/T90_SUBAGENT_ASSIGNMENT.md`

**验收**
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP14`
- `Tasks/MVP19_task_plan.md`、执行包 `README / STATUS / contracts / cards` 口径一致
- `WP8~WP13` 继续处于 maintenance / frozen upstream 状态，没有被 `WP14` reopen
- formal intake / outputs / stability-first arbitration policy 已冻结成唯一 authority package
- `WP14` 文档没有把 cross-axis self-integration 漂成实现完成、主链接线、`E4/E5`、observation、或 maintenance mode
- 证据层级目标：E0 -> E1（authority / contract freeze）

**当前状态（2026-04-04）**
- `WP14/MVP19` 当前层级是 `authority`
- 当前状态是 `authority_frozen`
- 当前 formal owner target 固定为 `OpenEmotion/openemotion/selfhood_integration/*`
- 当前正式主链接线目标固定为 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
- 当前 phase 1 只冻结 cross-axis integration semantics、formal intake/output、stability-first arbitration policy 与 boundary / non-release 约束；不证明 owner/runtime 实现
- 当前已证实：`Tasks/MVP19_task_plan.md` 与 `Tasks/active/mvp19_cross_axis_self_integration/*` 已把 capability ownership、authority source、IO contract、`WP8~WP13` boundary freeze、subagent assignment 与 task cards 收成一致 authority package
- 当前 blocker：按设计停在 docs-only authority freeze；下一步最小闭环动作是 `T10_FORMAL_OWNER_PACKAGE`
