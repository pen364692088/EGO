# MVS / Proto-Self 任务安排

> 状态：MVS 主线唯一最终裁决源
> 执行层工作包：`Tasks/active/krd_mvs_mainline/` + 各阶段 child packs

## 一句话主线
先把 **EgoCore 宿主壳收稳**，再把 **OpenEmotion 的 Proto-Self Kernel** 以最小闭环方式接进主链，先拿到 **MVS（最小可持续主体）** 的真实证据，再进入 Developmental Sandbox。

## 裁决关系
- 本文件负责 `WP0~WP9` 的阶段、依赖、Gate、证据等级和停止条件。
- `Tasks/active/krd_mvs_mainline/` 只负责把 `WP0/WP1` 拆成可执行工作包与状态台账，不与本文件并列裁决。
- 本任务按 **主线原地替换** 推进，不开平行实现、不走双轨切换、不保留 shadow implementation。

## 当前真实状态
- 正式核心只有两个：**EgoCore**（对外宿主 / 运行时 / 执行 / 治理）与 **OpenEmotion**（identity / self-model / memory / appraisal / reflection 本体）。
- 当前阶段目标是 **MVS**，不是开放发展式自我。
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

**当前状态（2026-04-02）**
- `scripts/run_runtime_mainline_observation.py`、`OpenEmotion/tools/run_mvp12_controlled_evidence.py`、`OpenEmotion/tools/aggregate_mvp12_observations.py` 已按原路径重跑
- 最新 aggregate 为：`report_count = 7`、`direct_real_report_count = 6`、`direct_real_window_count_total = 12`、`governance_violation_total = 0`、`replay_consistent_all = true`、`span_hours = 14.098`
- `stability_gate.status = pass`；这意味着 `WP7/MVP12` 的 controlled observation thresholds 当前已达标
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

**本阶段第一刀范围**
- 只做 authority / contract / boundary freeze
- 不直接开 `MVP14` 代码
- 不把新能力塞回 `WP8`

**任务**
- capability ownership 固定为：
  - endogenous drive state / drive history / priority snapshot / maintenance candidate generation 归 `OpenEmotion/emotiond/drives/*`
  - runtime scheduling / final reply / tool execution / transport 仍归 `EgoCore`
- authority source 固定为：
  - 顶层裁决：`Tasks/MVS_task_plan.md`
  - `WP9` phase-detail authority：`Tasks/MVP14_task_plan.md`
  - version spec：`OpenEmotion/roadmap/versions/MVP14.spec.yaml`
  - technical reference：`OpenEmotion/docs/mvp14/*`
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
- `WP9/MVP14` 当前层级是 `strategy`
- 当前状态是 `authority_contract_freeze_only`
- 当前还没有 `MVP14` 代码实现、主链接入或生效证据
- 下一步最小动作是：在不改代码的前提下，冻结 capability ownership / authority source / IO contract / WP8 boundary / locked non-releases

---

## 串行依赖
- `WP0 -> WP2 -> WP3 -> WP6 -> WP7 -> WP8` 必须串行
- `WP8 -> WP9` 必须串行
- `WP1` 可与 `WP2 / WP3` 并行，但其表达 contract 不得反向覆盖 Proto-Self 边界定义
- `WP4 / WP5` 在 `WP2` 基础上推进

## 当前不做
- 开放发展式自我
- 强社会自我
- 具身闭环
- 无限工具自治
- 复杂情绪文案层
- 任何让 OpenEmotion 直接执行现实动作的设计
- 在 `WP8` 中复活旧 `MVP13 mirror / dual-write` 作为正式 owner path
- 因 `WP8` 收口就放开 `WP9` 的 direct reply / broader transport authority

## 最小里程碑定义
- **里程碑 A**：`WP0 + WP1`
- **里程碑 B**：`WP2 + WP3`
- **里程碑 C**：`WP4 + WP5`
- **里程碑 D**：`WP6`
- **里程碑 E**：`WP7`
- **里程碑 F**：`WP8`
- **里程碑 G**：`WP9`
