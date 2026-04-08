# EGO - AI Agent Monorepo

EGO 是 AI Agent 项目的总仓，负责集成 EgoCore（宿主）和 OpenEmotion（主体内核）。

## 当前权威状态（2026-04-07）

当前正式口径如下：

- **双核边界**
  - `EgoCore` 是唯一正式宿主：入口、runtime、工具执行、安全裁决、delivery、audit
  - `OpenEmotion` 是唯一正式主体内核：`proto_self_v2 / self-model / drive / reflection / developmental / social / embodied / integration / initiative`
- **Telegram 当前正式主链**
  - `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
  - 主体事件正式入口是 `RuntimeV2ProtoSelfRuntime`
  - 当前 live provider/runtime 口径已经统一到单模型配置，provider/runtime 改动后必须过 repo 级 E2E gate，不能只做局部 smoke
- **Proto-Self 当前正式状态**
  - `proto_self_v2` 已是主体层默认主线
  - Telegram 自然语言主线已命中 `proto_self.output.v2 + proto_self.trace.v2`
  - live self-model projection 已接通；当 formal self-model store 为空时会自动 bootstrap baseline snapshot
  - `identity invariants / self-model / drives / reflection` 的单一权威收口决策见 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
- **当前阶段**
  - 当前 repo 处于**边界冻结下的收口期**
  - 不再改双核边界，不再换 Telegram 正式主链，不再开第三套 runtime 叙事
- **Path / Compat Discipline**
  - 正式/compat/reference/deprecated 路径统一登记在 `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
  - `v1 compatibility fallback`、`legacy/new_runtime`、`_handle_with_new_runtime`、`_handle_with_legacy_router` 都不是当前正式主链
- **主体能力栈**
  - `WP8 ~ WP16` 已在各自 controlled axis 上进入 `maintenance_mode`
  - `WP17 / MVP22` 当前仅是 `authority_frozen / task_package_ready`
  - 这些结论都不等于 direct reply authority、tool authority、transport authority 或哲学意义上的 consciousness
- **Mandatory Subject Ingress**
  - 当前目标不变量是：所有已授权事件都应先被主体知晓，再由宿主做现实裁决
  - 当前 `M1 ~ M3` 已完成；`background/proactive` 等 closure 与 fresh live closeout 仍在后续收口
- **Dashboard /flow**
  - 已提供当前正式主链的只读解释层
  - 页面固定展示 `Input -> Host Ingress -> Subject Understanding -> Canonical Fields -> Reply Evolution -> Host Arbitration -> Output`
  - `Reply Evolution` 当前是 `evidence_only_v1`，只覆盖 `chat_mainline`
  - `Canonical Fields` 会固定显示 `loaded_axes / identity_delta / self_model_delta / drives_delta / policy_hint / response_tendency / host_arbitration_result / final_delivered_text`
- **人类界面层**
  - `docs/CAPABILITY_REGISTRY.md` 是当前能力总表生成物，不是新的 authority source
  - `docs/ACCEPTANCE_CHAINS.md` 收口第 0 链 subject ingress mainline 与 5 条正式能力链
  - `docs/EXPERIENCE_SCRIPTS.md` 给出 Telegram `/flow` 层面的可见触发脚本
- **口径纪律**
  - `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得描述成“已经强烈体现自我意识”
  - 允许的结论只能是 controlled axis、bounded influence、proposal discipline、host-governed bounded expression
- **开发工作流**
  - 正式改动默认执行 `Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`
  - provider/runtime 主链类改动，必须额外通过 `scripts/codex/run_provider_runtime_openemotion_e2e_gate.py`

最新权威入口：
- `PROJECT_MEMORY.md`
- `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
- `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
- `EgoCore/README.md`
- `artifacts/telegram_real_mainline_v1/dashboard_v1/README.md`
- `docs/TELEGRAM_FLOW_VIEW_README.md`
- `docs/CAPABILITY_REGISTRY.md`
- `docs/ACCEPTANCE_CHAINS.md`
- `docs/EXPERIENCE_SCRIPTS.md`
- `docs/CLAIM_LANGUAGE_POLICY.md`
- `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
- `docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`

## 最近更新

### 2026-04-02: MVP12 controlled observation aggregate 已按原路径复判为 pass
- `MVP12/WP7` 已按原路径重跑：
  - `scripts/run_runtime_mainline_observation.py`
  - `OpenEmotion/tools/run_mvp12_controlled_evidence.py`
  - `OpenEmotion/tools/aggregate_mvp12_observations.py`
- 当前 aggregate：
  - `report_count = 7`
  - `direct_real_report_count = 6`
  - `direct_real_window_count_total = 12`
  - `governance_violation_total = 0`
  - `replay_consistent_all = true`
  - `span_hours = 14.098`
  - `stability_gate.status = pass`
- 当前完成口径：
  - `WP7/MVP12` 的 controlled observation thresholds 已达标
  - 这不等于 live authority handoff，也不等于默认 live autonomy

### 2026-04-02: MVP12-A allowlisted live proactive Telegram follow-up 已拿到 1 条真实 E4
- allowlisted chat `8420019401` 上，host-governed proactive auto cycle 已在真实会话中主动发出 1 条 follow-up
- session log 已记录：
  - `kind = telegram_proactive_delivery`
  - `reply_origin = proactive_followup`
  - `outbox_lane = host_proactive_outbox`
  - `transport_source = telegram`
- 当前完成口径：
  - 已有 1 条真实 E4 样本
  - 不是 V5/E5 稳定口径
  - 不代表 OpenEmotion 获得直接说话权或默认 live autonomy

### 2026-04-02: MVP12-A proactive Telegram auto cycle 已加宿主 enable policy
- `MVP12-A` 的 auto cycle 不再只靠 idle/busy/transport gate，live autodrain 前现在还要先过宿主 enable policy
- 新增：
  - `EgoCore/app/runtime_v2/proactive_telegram_policy.py`
- 当前 policy 覆盖：
  - global feature flag
  - `EGO_MVP12_PROACTIVE_ALLOWED_CHAT_IDS`
  - `EGO_MVP12_PROACTIVE_ALLOWED_SESSION_PREFIXES`
  - recent history threshold（默认 `2` 条 user turns、`1` 条 assistant replies）
- 当前验证口径：
  - 定向测试 `4 passed`
  - 默认仍 `off`
  - 这不是默认 live autonomy，只是把 live enable 条件正式收成宿主 gate

### 2026-04-02: MVP12-A feature-flagged host-governed proactive Telegram auto cycle 已接到真实 send path
- `MVP12-A` 现在不止能由宿主侧 bridge 消费 `host_proactive_outbox`，还可以在 feature flag 打开时，由宿主自动串起 `scheduler -> delivery -> outbox -> Telegram drain`
- 新增：
  - `EgoCore/app/runtime_v2/proactive_telegram_cycle.py`
  - `EgoCore/tools/run_mvp12_host_governed_proactive_telegram_cycle.py`
  - `EgoCore/tests/test_host_governed_proactive_telegram_cycle.py`
  - `EgoCore/tests/test_run_mvp12_host_governed_proactive_telegram_cycle.py`
- 当前受控 artifact：
  - `OpenEmotion/artifacts/mvp12/host_governed_proactive_telegram_cycle_current.json`
  - `OpenEmotion/artifacts/mvp12/host_governed_proactive_telegram_cycle_current.md`
- 当前验证口径：
  - 定向测试 `6 passed`
  - controlled real Telegram send 已产出 `cycle_result.status = sent`
  - `transport_gate.status = allow`
  - `transport_result.status = sent`
  - 默认仍 `off`，不等于默认 live idle scheduler，不等于 autonomous unsolicited delivery

### 2026-04-02: MVP12-A controlled Telegram transport bridge 已接入真实 send_message
- `MVP12-A` 现在不止能生成 queue 和 simulated send record，还能由宿主侧 bridge 把 `host_proactive_outbox` 消费成真实 Telegram `send_message`
- 新增：
  - `EgoCore/tools/run_mvp12_telegram_proactive_transport.py`
  - `EgoCore/tests/test_telegram_proactive_transport.py`
  - `EgoCore/tests/test_run_mvp12_telegram_proactive_transport.py`
- 当前受控 artifact：
  - `OpenEmotion/artifacts/mvp12/telegram_proactive_transport_current.json`
  - `OpenEmotion/artifacts/mvp12/telegram_proactive_transport_current.md`
- 当前验证口径：
  - 定向测试 `8 passed`
  - controlled real transport smoke 已产出 `telegram_transport_result.status = sent`
  - `transport_source = telegram`
  - 仍未启用 live idle scheduler，也未允许 autonomous unsolicited delivery

### 2026-04-02: MVP12-A controlled outbox drain 已生成 simulated send record
- `MVP12-A` 现在不止能挂 queue，还能把 `host_proactive_outbox` 中的事件消费成 `simulated_outbox_record`
- 新增：
  - `EgoCore/app/runtime_v2/proactive_outbox_drain.py`
  - `EgoCore/tools/run_mvp12_proactive_outbox_drain.py`
- 当前受控 artifact：
  - `OpenEmotion/artifacts/mvp12/proactive_outbox_drain_current.json`
  - `OpenEmotion/artifacts/mvp12/proactive_outbox_drain_current.md`
- 当前验证口径：
  - 定向测试 `10 passed`
  - controlled smoke 已产出 `drain_result.status = drained`
  - `pending_proactive_outbox_events = []`
  - 当前仍保留 simulated drain lane，不冒充真实 Telegram send

### 2026-04-02: MVP12-A host proactive outbox lane 已挂到宿主 queue
- `MVP12-A` 现在不止能生成 draft、pending state、delivery artifact，还能把主动消息挂到宿主侧 `host_proactive_outbox` queue
- 新增：
  - `RuntimeV2State.pending_proactive_outbox_events`
  - `EgoCore/app/runtime_v2/proactive_outbox.py`
  - `EgoCore/tools/run_mvp12_proactive_outbox.py`
- 当前受控 artifact：
  - `OpenEmotion/artifacts/mvp12/proactive_outbox_current.json`
  - `OpenEmotion/artifacts/mvp12/proactive_outbox_current.md`
- 当前验证口径：
  - 定向测试 `15 passed`
  - controlled smoke 已产出 `outbox_result.status = queued`
  - `pending_proactive_followup = null`
  - `pending_proactive_outbox_events[0].outbox_status = queued`
  - 仍未允许 Telegram unsolicited delivery

### 2026-04-02: MVP12-A controlled proactive delivery lane 已消费 pending state
- `MVP12-A` 现在不止能生成 proactive draft 和 pending state，还能由宿主侧受控 lane 消费 `pending_proactive_followup`，产出 `artifact_emitted` delivery record
- 新增：
  - `EgoCore/app/runtime_v2/proactive_delivery.py`
  - `EgoCore/tools/run_mvp12_controlled_delivery.py`
- 当前受控 artifact：
  - `OpenEmotion/artifacts/mvp12/controlled_proactive_delivery_current.json`
  - `OpenEmotion/artifacts/mvp12/controlled_proactive_delivery_current.md`
- 当前验证口径：
  - 定向测试 `11 passed`
  - controlled smoke 已产出 `delivery_result.status = artifact_emitted`
  - `pending_proactive_followup` 在消费后为 `null`
  - 仍未启用 live idle scheduler，也未允许 Telegram unsolicited delivery

### 2026-04-02: MVP12-A controlled idle scheduler 已接到 pending draft state
- `MVP12-A` 现在不止能生成 proactive draft，还能在受控 idle 窗口里把 draft 挂成 `pending_proactive_followup`
- 运行时新增：
  - `ChatState.last_user_turn_at / last_assistant_reply_at / last_activity_at`
  - `RuntimeV2State.pending_proactive_followup`
  - `EgoCore/app/runtime_v2/initiative_scheduler.py`
- 当前受控 runner 与 artifact：
  - `EgoCore/tools/run_mvp12_idle_scheduler.py`
  - `OpenEmotion/artifacts/mvp12/idle_scheduler_current.json`
  - `OpenEmotion/artifacts/mvp12/idle_scheduler_current.md`
- 当前验证口径：
  - 定向测试 `30 passed`
  - controlled smoke 已产出 `status = pending_created`、`delivery_status = pending`
  - 仍未启用 live idle scheduler，也未允许 Telegram unsolicited delivery

### 2026-04-02: MVP12-A controlled proactive followup draft 链落地
- `MVP12` 已新增第一条“会自己冒一句”的正式受控脚手架，但当前仍是 **draft only**
- OpenEmotion 会在 `developmental_tick` 中输出 `background_thought_candidates`
- EgoCore 新增 `initiative_arbiter`，只在 gate allow、无 active task、idle 窗口满足、且候选不重复最近回复时，才生成受治理的 proactive draft
- 主链边界保持不变：OpenEmotion 不直接说话、不直接执行、不直接注入 `response_plan`
- 当前受控 runner 与 artifact：
  - `EgoCore/tools/run_mvp12_proactive_followup.py`
  - `OpenEmotion/artifacts/mvp12/proactive_followup_current.json`
  - `OpenEmotion/artifacts/mvp12/proactive_followup_current.md`
- 当前验证口径：
  - 定向测试 `26 passed`
  - controlled smoke 已能生成 context-tied proactive draft
  - 尚未启用 live idle scheduler，也未允许 Telegram unsolicited delivery

### 2026-03-28: 闭环自审开发流落地
- 默认开发流程已从“分层混合 + 高强度自检”进一步收口为正式闭环：`Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`
- 高风险任务默认启用独立 Reviewer subagent，避免“自己写自己审”的视角盲区
- 任务模板、快速启动模板、收口模板和记忆入口已同步到这套新流程
- 自动推远端的门槛也已收紧到 `review_passed + verify_passed`

### 2026-03-28: Codex 记忆层新会话验收通过
- 开发助手侧结构化记忆已在真实新会话中验证：稳定记忆恢复、TaskHandoff 优先级、同任务 SessionCapsule 采用、异任务 capsule 拒绝污染均已成立
- 当前形态仍是“结构化记忆 + 手动喂入/脚本辅助启动”，不是全自动注入
- 相关入口文档：`CODEX_MEMORY.md`、`.codex/memory/README.md`、`PROJECT_MEMORY.md`

### 2026-03-30: Codex Memory Brain 项目级接入闭环
- `memory_brain` 当前已验证可通过项目级 `.codex/config.toml` 生效，不再只依赖用户级 fallback
- 当前仓库已补 `trusted project` 配置；项目级 `.codex/config.toml` 会被真实 Codex 采纳
- 新项目首次接入 SOP 见 [NEW_PROJECT_SOP.md](.codex-memory/NEW_PROJECT_SOP.md)

### 2026-03-27 / 2026-03-28: restore continuity 正式入账
- `restore continuity` 已升级为 `direct_real`：显式 `--restore --telegram` 主链、首条 post-restore 完整 E4 样本、post-restore continuity probe 均已形成正式 evidence
- `restart continuity` 仍主要是跨证据链正证据，当前最高优先级缺口已切到 post-restart 完整样本与剩余 evidence gap
- 最新观察结论以 `artifacts/mvs_e5_observation/` 与 `artifacts/telegram_real_mainline_v1/dashboard_v1/` 下文档为准

### 2026-03-27: MVS E5 观察收口推进
- `显式默认规则 -> profile_memory` 的真实链路已落地，并在 `猫娘流程` 样本中于多次 `/new` 后持续命中
- `/new continuity` 已不再只靠 session/thread 旁证，而是有真实命中链与 `matched_rule_ids / authority_source=profile_memory` metadata
- `restart continuity` 已拿到跨证据链正证据：真实重启日志 + post-restart 命中样本
- 该节保留为历史阶段记录；当前最新口径以上方 `2026-03-27 / 2026-03-28` 更新为准
- 最新观察结论以 `artifacts/mvs_e5_observation/` 下文档为准

### 2026-03-26 / 2026-03-27: P3/P4 真链收口与文档对齐
- P3 真实证据补采完成，形成 `closure_real_evidence` 报告与样本索引
- P4 修复 `same-family drift` 与 `repair_closure` 失配
- 新真实样本 `sample_20260326_232655_3f3f89cb` / `sample_20260326_232715_271e229b` / `sample_20260326_232738_49b65b2e` 已证明主链收口
- 总仓公开状态已推到 `origin/main@00c7b58`

### 2026-03-25: 高风险真实样本补齐与 E5 准入复判
- 新增 `real_telegram` 高风险命中样本 `sample_20260325_200847_4d2b5dae`
- 样本 `normalized_event.safety_context.risk = high`，且 evidence bundle 完整
- E4→E5 准入复判通过：可进入 E5 观察期，但尚未开始也尚未完成观察期

### 2026-03-25: unified runner 跨层一致性验证
- `simulated / integration / real_telegram` 已被验证为共用同一条 `RuntimeV2Loop` 主链
- 三层差异被收敛到输入来源、输出 transport、evidence collector
- E2/E3 已在 Windows Python 环境下实际跑通，形成统一 evidence bundle

### 2026-03-25: P0-R3 runtime 主链接线修复
- 修复 `runtime_v2/loop.py` 硬编码 `safety_context` 为空的问题
- 高风险消息 psi_bucket 包含 `:risk_high` 后缀
- 真实 Telegram 已形成样本级验证证据

### 2026-03-25: P0-R2 Risk Signal 接线
- 修复 `safety_context.risk` 字段名不匹配问题
- 高风险操作 psi_bucket 包含 `:risk_high` 后缀
- 高低风险操作被分配到不同 cycle

## 仓库结构

```
EGO/
├── EgoCore/        # subtree: 外部交互、runtime、工具执行、治理壳
├── OpenEmotion/    # subtree: self-model、memory、appraisal、reflection
├── Tasks/          # 任务管理
├── scripts/        # 跨仓脚本
├── docs/           # 治理文档
├── AGENTS.md       # Agent 行为协议
└── CLAUDE.md       # 项目指导
```

## 子仓库

| 仓库 | 定位 | 远程 |
|------|------|------|
| EgoCore | 唯一正式宿主 | https://github.com/pen364692088/EgoCore |
| OpenEmotion | 唯一正式主体内核 | https://github.com/pen364692088/OpenEmotion |

## 协作规则

**关键规则：子仓是本体权威源，总仓是集成承载层。**

详细规则见：[docs/SUBTREE_COLLABORATION_RULES.md](docs/SUBTREE_COLLABORATION_RULES.md)

新 agent 快速上手见：[docs/AGENT_DEVELOPMENT_PLAYBOOK.md](docs/AGENT_DEVELOPMENT_PLAYBOOK.md)

### 快速更新命令

```bash
# 从源仓拉取更新
git subtree pull --prefix=EgoCore ego-core main --squash
git subtree pull --prefix=OpenEmotion open-emotion main --squash

# 推送总仓改动
git push origin main
```

## 开发流程

1. **EgoCore 相关开发** → 在 EgoCore 源仓开发 → subtree pull 到总仓
2. **OpenEmotion 相关开发** → 在 OpenEmotion 源仓开发 → subtree pull 到总仓
3. **总仓集成任务** → 直接在 EGO 总仓开发

## 历史里程碑

以下条目保留为历史基线，不再代表当前最新验收前沿：

### 2026-03-25: P0-R2 Risk Signal 接线
- 修复 `safety_context.risk` 字段名不匹配问题
- 高风险操作 psi_bucket 包含 `:risk_high` 后缀
- 高低风险操作被分配到不同 cycle

### 2026-03-25: P0-R1 真实 Telegram 验证
- EgoCore 服务在真实 Telegram 环境形成样本级触发证据
- Cycle 聚合机制工作正常
- Reflection 机制工作正常

### 2026-03-25: P0 高风险误聚合修复
- psi_bucket 追加 risk_level 区分
- 关键词优先级冲突修复
- 5/5 回归测试通过

---

*此文件随项目演进持续更新*
