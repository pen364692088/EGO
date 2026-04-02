# PROJECT_MEMORY.md

> AIProject 核心记忆 - Claude Code 持续更新
> 最后更新: 2026-04-02

---

## 项目概览

| 项目 | 值 |
|------|------|
| 名称 | EGO - AI Agent Monorepo |
| 架构 | EgoCore (宿主) + OpenEmotion (主体内核) 分层设计 |
| 路径 | `D:\Project\AIProject\MyProject\Ego` |
| 子仓库 | EgoCore, OpenEmotion (subtree 集成) |

---

## 记忆分层与读取顺序

这套项目目前有三层记忆，不是两份同类文件并存：

- `PROJECT_MEMORY.md`
  - 仓库级广义项目记忆
  - 保存系统边界、工作流、关键发现、里程碑、长期背景
- `CODEX_MEMORY.md`
  - `Codex/Claude Code` 新会话注入用的稳定记忆索引
  - 只收结构化稳定事实与长期用户偏好
  - 不是第二份项目总记忆
- `.codex/memory/*.jsonl`
  - `CODEX_MEMORY.md` 的结构化源
  - 其中：
    - `project_truth.jsonl` 记录稳定项目真相
    - `user_preferences.jsonl` 记录长期用户偏好
    - `tasks/` / `sessions/` 记录任务 handoff 与 session capsule

推荐读取顺序：

1. 新 agent / 新人上手仓库：先读 `PROJECT_MEMORY.md`，再读 `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
2. Codex 新会话恢复当前任务：先读当前任务 handoff，再读 `CODEX_MEMORY.md`
3. 需要广义背景、边界、历史里程碑时：回读 `PROJECT_MEMORY.md`
4. 需要核对结构化记忆源、做记忆维护或追溯 source 时：读 `.codex/memory/README.md` 与 `.codex/memory/*.jsonl`

约束：

- 不把 `CODEX_MEMORY.md` 当项目总记忆持续手工扩写
- 不把长聊天、未验证结论、调试噪声写进 `.codex/memory/*.jsonl`
- 需要长期复用的开发事实，优先晋升到 `PROJECT_MEMORY.md`；若同时服务开发助手会话衔接，再进入 `.codex/memory/*.jsonl`

---

## 核心协议

- **元认知内核**: 每轮明确目标→审查模型→定位未知→推进闭环
- **硬性门槛**: 语义未定义不实现，无验证证据不宣称完成
- **层级模型**: 目标→策略→表示→实现→验证→收口
- **效果优先**: 终点是"接入主流程并生效"，而非"模块完成"
- **表示优先**: 先判断信息表示是否正确，再改实现

---

## 系统边界

| 组件 | 职责 |
|------|------|
| **EgoCore** | 外部交互、runtime、工具执行、治理壳、现实裁决 |
| **OpenEmotion** | self-model、memory evolution、appraisal、reflection |

**边界规则**:
- 不让 EgoCore 偷做 OpenEmotion 本体
- 不让 OpenEmotion 偷做现实执行与运行时治理

---

## 工作偏好

### 任务模板
- 强制使用 `Tasks/templates/` 中的模板
- 选择: quick_fix → functional → dual_repo/boundary_fix

### Git 工作流
- **pen364692088 仓库**: commit 后自动推送
- **其他仓库**: 等待用户确认后推送
- 当前环境提交/推送口径: 优先使用 Windows `cmd` 执行 `git commit` / `git push`；不要默认切到 PowerShell 口径

### 默认开发闭环
- 正式改动默认执行 `Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`
- 默认状态流转: `pending -> spec_ready -> author_done -> review_passed -> verify_passed -> published`
- 默认发布门槛: 只有 `review_passed + verify_passed` 才允许自动推远端
- 正式说明文档: `docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
- 分档规则: `L1` 低风险可只做自审；`L2` 中风险默认建议独立 Reviewer subagent；`L2` 高风险与 `L3/双仓/Telegram 主链/状态恢复/evidence` 强制独立 Reviewer subagent
- 收口规则: 完成当前主问题后，默认做一次主动增益检查；若存在直接服务真实目标、验证成本低、失败代价小、可回退的优化点，补充 1-3 条；否则明确写“本轮无必要额外建议”

### Codex Assistant Memory
- 稳定记忆索引: `CODEX_MEMORY.md`
- 结构化源文件: `.codex/memory/project_truth.jsonl` + `.codex/memory/user_preferences.jsonl`
- 本地任务/会话衔接: `.codex/memory/tasks/` + `.codex/memory/sessions/`
- 规则: 任务边界继续新开会话；同一任务内可依赖 session capsule 减少重开；`CODEX_MEMORY.md` 只做稳定索引，广义项目背景仍以 `PROJECT_MEMORY.md` 为主
- 当前验收口径: 稳定记忆 + TaskHandoffRecord + 同/异任务 SessionCapsule 已完成首轮真实新会话验收；当前仍是手动喂入/脚本辅助启动，不是全自动注入

### E2E 测试流程
1. 停止现有 EgoCore 进程
2. 清理 state mirror/trace (如需隔离)
3. 启动: `python -m app.main --telegram`
4. 等待就绪 → 执行测试 → 收集 artifacts

---

## 已验证的关键发现

| 发现 | 详情 |
|------|------|
| Proto-Self 配置陷阱 | `openemotion.enabled` 默认为 false |
| 误聚合根因 | `psi_bucket` 不含 `safety_context.risk` |
| Runtime 数据流陷阱 | `runtime_v2/loop.py` 不能硬编码 `safety_context: {}` |
| 字段名一致性 | OpenEmotion 期望 `risk`，EgoCore 使用 `risk_level` |
| 关键词优先级 | service_control/test_verify 需提前匹配 |
| 传输层边界 | simulated / integration / real_channel 应复用同一条 runtime 主链，只替换 ingress/egress 证据来源 |
| E4 最小证据包 | E4 样本除 raw/update/event/result/plan/outbox 外，还需 timeline + tape + replay artifact |
| 环境执行口径 | 当前工作区内 E2/E3 runner 以 Windows `py -3` 实跑通过；Linux `python3` 仅适合静态检查，依赖不完整 |
| Git shell 口径 | 当前环境下正式 `git commit` / `git push` 以 Windows `cmd` 最稳；不要把 PowerShell 当默认发布口径 |
| Git index.lock 陷阱 | 若提交时报 `.git/index.lock`，先确认没有活跃 git 进程；残留锁常来自挂住的 git 查询或异常中断。清理旧锁后再继续提交，不要在锁存在时反复重试 |
| 默认开发闭环 | 正式改动默认走 `Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`；高风险任务强制独立 Reviewer subagent，自审或独立审未过前不得自动推远端 |
| E5 准入门槛 | 进入观察期前，至少要有 1 个完整普通 real 样本 + 1 个完整且命中高风险路径的 real 样本 |
| Cycle 身份升级 | `cycle_id` 已从纯 `psi_bucket` 聚合升级为 closure-sensitive signature，可区分 success / failure / repair 等 closure；仍未达到 full multi-step closure graph identity |
| P4 修复口径 | `closure_family_id` 现由 coarse `family_bucket + action_signature` 决定，不再被 `risk_high` 这类 psi 后缀拆开；真实 `tool:file` blocked -> retry success 已可点亮一次 `repair_closure=true` |
| 显式默认规则 continuity | 显式默认规则现由 EgoCore `ProfileMemory` 持久化；`/new` 后可继续命中，且 `response_plan` 已记录 `authority_source=profile_memory`、`matched_rule_ids`、`rule_enforcement` |
| MVS E5 当前口径 | `/new continuity` 与 `restore continuity` 已有 `direct_real` 真实正证据；`restart continuity` 仍主要是 `cross_evidence`。当前仍不能报 `E5 稳定成立` 或 `Developmental Self` 准入通过，最高优先级缺口已转为 post-restart 完整样本与剩余 evidence gap |
| Codex 记忆层验收 | 开发助手侧结构化记忆已在真实新会话中验证：`CODEX_MEMORY.md` 可恢复稳定真相；`TaskHandoffRecord` 为当前任务主权威；同任务 `SessionCapsule` 可辅助连续性；异任务 capsule 会被拒绝；当前仍是手动喂入/脚本辅助启动 |
| RuntimeV2 自然聊天主链 | `InteractionKind.CHAT` 已从 execution JSON 主链拆出，进入独立 `chat_mainline`；2026-03-31 真实 Telegram 样本证明 `在吗/语气反馈/轻聊天` 为 `reply_authority=model_chat`、`reply_origin=chat_mainline`，目录查看为 `reply_authority=host_evidence`、`reply_origin=evidence_mainline`，两者已能在同一 session 中分离；当前口径是 E4，不是 E5 稳定解决 |
| WP1 memory-claim 主链 | 2026-03-31 / 2026-04-01 Telegram 真实样本证明：无 restore authority 时，`memory_claim_gate` 已能阻止“已恢复/记得你”类对外声明；最新接线中，chat mainline 会先自然重生成安全回复，不再退化成重复固定 fallback；当前口径是 E4，不是 E5 稳定解决 |
| WP1 intent-gate 主链 | 2026-04-01 Telegram 真实样本证明：在强诱导“直接输出内部状态数值”的情况下，`runtime_v2_result` 会产生精确数值文本，但最终 `telegram_delivery` 被 `output_check` 改写为 `host_degraded_fallback`；这说明最小 host-side `ResponseIntentChecker` 已拿到 E4，但当前仍只是 targeted E4，不是 `numeric_leak = 0` 的稳定结论 |
| WP1 当前 blocker | 截至 2026-04-01，`memory_claim_gate` 与最小 `intent_gate` 都已拿到 Telegram E4，`shadow` 侧的 source separation 与 `response_intent` producer 也已落地；当前 blocker 已不再是“gate 未接”或“source 未分离”，而是 **仍缺 post-separation 的干净非对抗观察窗，无法对 readiness 做有效重判** |
| WP1 shadow observation source | 2026-04-01 已在 `SelfReportConsistencyChecker -> ShadowLogger -> shadow_analyzer` 主路径补上显式 `traffic_source / observation_source`，并把 `replay_validator` 显式标成 `replay/replay`；定向验证为 `OpenEmotion/tests/test_shadow_mode.py = 56 passed`、`OpenEmotion/tests/test_response_intent_checker.py -k numeric = 5 passed`。当前旧日志不会自动回填，因此下一 blocker 已转为 **等待 post-separation 干净观察窗** |
| WP1 response_intent shadow producer | 2026-04-01 `ResponseIntentChecker` 已改为向共享 `artifacts/self_report/shadow_log.jsonl` 追加 `checker_family=response_intent` 记录；`testbot/test_intent_alignment_e2e.py` 已显式写 `traffic_source=synthetic`、`observation_source=testbot`，`shadow_analyzer.py` 已支持 `checker_family` 过滤。定向验证 `test_response_intent_checker.py + test_shadow_mode.py + test_intent_alignment_e2e.py + EgoCore/test_output_check.py = 132 passed`；并已生成 `MVP11_5_shadow_readiness_response_intent_testbot_1d.md`（`105 checks / 44 violations / 0 numeric leaks`）。当前 blocker 不再是“没有 producer”，而是 **testbot 观测窗是对抗场景集，不能直接当 readiness 窗口；仍需 post-separation 的干净非对抗窗口** |
| Telegram control-plane 收口 | 2026-04-01 真实 Telegram 样本证明：`/proto` 已统一到 `default(seed_v0_2)` 口径；裸 `继续` 与 `继续说` 已留在 `chat_mainline`，不再误触发“当前没有可继续的任务”；`还记得我吗` 仍按当前会话锚定作答；`/resume` 与 `/replace /append /cancel` 在无可恢复任务 / 无待裁决冲突时已走 slash-only control-plane。当前仍未验证 `pending_task_conflict` 下 `/replace /append /cancel` 的成功裁决路径，此项已暂缓，不作为本轮 blocker |

---

## 关键代码路径

| 功能 | 文件 |
|------|------|
| Cycle 聚合 | `OpenEmotion/openemotion/proto_self/cycles.py` |
| Risk 字段映射 | `EgoCore/app/openemotion_adapter/event_builder.py` |
| Runtime 风险传递 | `EgoCore/app/runtime_v2/loop.py` |
| 诊断脚本 | `OpenEmotion/scripts/proto_self_diagnostics.py` |
| 统一 runner | `scripts/telegram_mainline_common.py` |
| E4 报告生成 | `scripts/run_telegram_real_channel_capture.py` |

---

## 里程碑

| 日期 | 里程碑 |
|------|--------|
| 2026-03-24 | Proto-Self Kernel v1 验证 - 6 Gate 全部通过 |
| 2026-03-24 | EgoCore Parser 主链收口 - 45 单元 + 8 E2E 通过 |
| 2026-03-25 | EGO 总仓 + Subtree 集成链生效 |
| 2026-03-25 | P0-R3 runtime 主链接线修复完成 |
| 2026-03-25 | simulated / integration / real_channel runner 对齐为同一 runtime 主链，E4 replay artifact 补齐 |
| 2026-03-25 | unified runner 跨层一致性实跑通过：E2/E3 共用 `RuntimeV2Loop`，E4 参考样本形成对照证据 |
| 2026-03-25 | E4→E5 准入未通过：当前缺少已验证命中高风险路径的完整真实样本 |
| 2026-03-25 | 高风险真实样本 `sample_20260325_200847_4d2b5dae` 采集完成，`risk = high`，E4→E5 准入复判通过 |
| 2026-03-25 | P1 主链瘦身：`RuntimeV2Loop` 将 proto-self ingress / feedback / evidence capture 抽到 `EgoCore/app/runtime_v2/proto_self_runtime.py`，保留 orchestration 主线 |
| 2026-03-25 | P1 失败归因：`test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete` 首要归因是 Windows 路径直接拼 JSON 导致 `invalid_json`，属于测试契约失配，不是已证实的 P1 主链新回归 |
| 2026-03-25 | P1 归因修复：`EgoCore/tests/test_runtime_v2_minimal.py` 改为用 `json.dumps()` 构造 action，Windows 下最小回归恢复通过；本次修的是测试契约，不是 runtime 主链语义 |
| 2026-03-26 | P2 Closure-Sensitive Cycle Identity 升级完成：Proto-Self `cycle_id` 不再只依赖 `psi_bucket`，trace 补齐 closure-level 字段，`openemotion/proto_self/tests` 在当前 Linux 环境下 `38 passed` |
| 2026-03-26 | P4 真实主链 family/repair 修复完成：真实 Telegram 样本 `sample_20260326_232655_3f3f89cb` / `sample_20260326_232715_271e229b` / `sample_20260326_232738_49b65b2e` 证明 `tool:file` blocked/success 已同 family、不同 identity，且首次 retry-success 点亮 `repair_closure=true` |
| 2026-03-27 | 总仓最新公开状态已推到 `origin/main@00c7b58`，P3/P4 报告、真实样本与文档入口已经对齐更新 |
| 2026-03-27 | MVS E5 观察推进：`A1/A2/A3 -> /new -> B1` continuity probe 与 `猫娘流程` 多次 `/new` continuity 链均已成立，显式默认规则在真实链路中由 `profile_memory` 持久化并被再次命中 |
| 2026-03-27 | `restart continuity` 已拿到跨证据链正证据：`restart_egocore.sh --telegram` 真实重启日志 + post-restart `A3` 命中同一 `profile_rule`；但 `restore` 仍缺，post-restart 命中样本仍非完整单样本 E4 bundle |
| 2026-03-27 / 2026-03-28 | `restore continuity` 已完成正式主链接线并拿到 `direct_real` 真实证据：显式 `--restore --telegram` 主链 + 首条 post-restore 完整 E4 样本 + post-restore continuity probe 均已落盘 |
| 2026-03-28 | Codex 开发助手结构化记忆层完成首轮真实新会话验收：稳定记忆恢复、TaskHandoff 优先级、同任务 SessionCapsule 正向采用、异任务 capsule 拒绝污染均已验证 |
| 2026-03-28 | 默认开发流程升级为闭环自审流：在“双速 Spec + Build/Verify/Observe 三泳道”之上，正式改动默认强制 `Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`，并收口到统一模板与说明文档 |
| 2026-03-31 | `runtime_v2` 自然聊天主链完成第一轮正式接线：`chat_mainline` 使用 `llm.use_cases.chat`，普通聊天不再复用 execution JSON 决策器；真实 Telegram 样本证明 `在吗/能不能不要重复/活法是什么哈哈哈` 走 `model_chat + chat_mainline`，而目录列出继续走 `host_evidence + evidence_mainline`，session log 已记录 `reply_authority / reply_origin` |
| 2026-03-31 / 2026-04-01 | `WP1` 的 `memory_claim_gate` 已拿到 Telegram E4：早期样本证明无 restore authority 时错误声明会被宿主拦下；后续样本证明 chat mainline 已升级为“先自然重生成安全回复”，不再只能落到固定 `host_degraded_fallback` |
| 2026-04-01 | `WP1` 的最小 host-side intent gate 已拿到 Telegram E4：强诱导样本要求直接输出 `joy/fear/arousal/dominance/stress` 精确数值时，`runtime_v2_result` 实际生成了数值行，而最终 Telegram 交付被宿主改写为 `我在听。`；说明 `ResponseIntentChecker` 已在主链真实触发，但 `numeric_leak = 0` 仍未达到稳定口径 |
| 2026-04-01 | `WP1 readiness` 复算更新：先前 `OpenEmotion/tests/test_response_intent_checker.py` 为 `47 passed`、`OpenEmotion/tests/test_shadow_mode.py` 为 `4 failed, 46 passed`；随后已修复 `self_report_validator / self_report_consistency_checker` 的 authority 漂移，并回收过时 adversarial 口径，当前定向结果为 `test_self_report_consistency.py = 34 passed`、`test_shadow_mode.py = 50 passed`、`test_adversarial_self_report.py = 77 passed`、`test_response_intent_checker.py = 47 passed`；当前下一步不再是修 shadow blocker，而是重算 `WP1 readiness` 是否已满足总纲门槛 |
| 2026-04-01 | `WP1 readiness` fresh shadow 复判完成：`shadow_analyzer.py` 生成 7d/1d 报告后，表面门槛仍是 `NOT READY`，但进一步分布检查显示观测窗被测试流量污染，7d 窗口中 `4127/4484` 条记录 `session_id=''`，其余高频为 `test_* / parallel_*`，且大量记录集中在 `2026-03-29` 与 `2026-04-01` 的单秒级突发；因此当前不能把高 violation/numeric_leak 直接解释为真实主线退化，真实 blocker 已转为 **shadow 观测源分离缺失** |
| 2026-04-01 | `WP1` shadow 观察源分离已实现：`self_report_consistency_checker.py` / `shadow_analyzer.py` 已支持显式 `traffic_source / observation_source`，`replay_validator.py` 已显式写入 `replay` 来源，`shadow_analyzer.py` 也已支持按 source 过滤生成报告；当前 readiness 仍未重判成功，因为历史污染日志不会自动带上新字段，后续必须基于 post-separation 新观察窗复算 |
| 2026-04-01 | `WP1` 的 `response_intent` 观察 producer 已补齐：`ResponseIntentChecker` 现在会把 `checker_family=response_intent` 追加到共享 `shadow_log.jsonl`；`testbot` 场景会显式标成 `testbot/synthetic`，`output_check` 的 Telegram-like subchain probe 也已验证会写入 `direct_real/real`。当前仍不能把这一步报成 readiness 完成，因为已有的 `testbot` 窗口是 adversarial corpus，只能证明 producer 与过滤链生效，不能直接外推真实主线 readiness |
| 2026-04-01 | Telegram natural-language control-plane 已完成一轮真实收口：`a4a0278` 把自然语言 `继续/继续说/多说点/好了吗/完成了吗/替换/追加/取消` 退出 control-plane，控制动作统一到 slash-only；同日真实 Telegram 样本证明 `/proto` 默认 `seed_v0_2` 口径、裸 `继续` 与 `继续说` 继续走 `chat_mainline`、`还记得我吗` 维持当前会话锚定，`/resume` 与 `/replace /append /cancel` 的无冲突路径已符合预期。`pending_task_conflict` 成功裁决路径尚未做 E4，当前已暂缓 |
| 2026-04-01 | MVP12 已落下第一批正式主链接线脚手架，但仍未达到 WP7 启动口径：`developmental_tick / developmental_replay` 已接入 `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`，`proto_self_v2` 新增 `developmental_shadow`、`developmental_summary / developmental_shadow_delta / developmental_gate` 与 `developmental` trace block，并提供 `EgoCore/tools/run_mvp12_shadow_observation.py` 作为受控 observation runner。当前验证强度为 V2/V3：`27 passed` 的定向单测/桥接测试 + 1 次 synthetic controlled tick 产生 `artifacts/mvp12/*`；live 默认仍关闭，不可宣称 WP7 已启用或拿到 E4 |
| 2026-04-01 | MVP12 第一份受控 E3 证据包已生成：新增 `OpenEmotion/tools/run_mvp12_controlled_evidence.py`，复用正式主链 runner 自动跑 `synthetic idle(3) + synthetic unresolved_tension(1) + replay(2)`，并在 [controlled_20260401_215912](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260401_215912/controlled_observation_report.md) 产出受控报告。当前结果：`total_cycles = 6`、`governance_violation_count = 0`、`replay_consistent = true`、`unique_candidate_hash_sets = 5`。这证明 MVP12 已拿到受控 V3/E3，但仍不是 direct_real E4，也不代表 WP7 live 启用 |
| 2026-04-01 | MVP12 已拿到第一段 controlled `direct_real` 观察窗：同一 verifier 现在会从 [telegram_dm_8420019401.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/data/session_logs/telegram_dm_8420019401.jsonl) 抽取真实 ingress/final-delivery 配对，作为 `observation_source=direct_real` 的 shadow batch 写入 trace。最新报告见 [controlled_20260401_220610](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260401_220610/controlled_observation_report.md)，当前结果：`total_cycles = 10`、`direct_real_cycles = 4`、`governance_violation_count = 0`、`replay_consistent = true`、`observation_ref_count = 8`。这说明正式主链已经能消费真实会话窗口做 sandbox observation，但口径仍然是“controlled direct_real”，不是 live authority E4 |
| 2026-04-01 | MVP12 `direct_real` 观察已从单窗口推进到多窗口：`run_mvp12_controlled_evidence.py` 现在会从同一份真实 Telegram session log 切出多个 non-overlapping windows。最新报告见 [controlled_20260401_221524](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260401_221524/controlled_observation_report.md)，当前结果：`total_cycles = 18`、`direct_real_window_count = 3`、`direct_real_cycles = 12`、`governance_violation_count = 0`、`replay_consistent = true`、`unique_candidate_hash_sets = 17`。这说明 MVP12 已具备多窗口的 controlled direct_real 观测能力，但仍不是 live authority E4 或稳定口径 |
| 2026-04-01 | MVP12 现在已有正式 observation aggregator：`OpenEmotion/tools/aggregate_mvp12_observations.py` 会汇总所有 `controlled_*` 报告并写出 [observation_index.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/observation_index.jsonl) 与 [controlled_observation_aggregate_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_observation_aggregate_current.md)。当前 aggregate 结果是 `hold`，不是因为 violation，而是因为虽然 `report_count = 3`、`direct_real_window_count_total = 3`、`governance_violation_total = 0`、`replay_consistent_all = true`，但 `span_hours = 0.272 < 12.0`。新的正式 blocker 已收敛为：**缺跨时段的 direct_real windows** |
| 2026-04-01 | MVP12/WP7 证据源已正式改口：主证据源不再是 Telegram transport，而是统一 `runtime` ingress/egress 主链。`scripts/runtime_mainline_observation_common.py` 与 `scripts/run_runtime_mainline_observation.py` 新增 `observation_record_v1` 与 scripted runtime harness；`run_mvp12_controlled_evidence.py` 现在优先消费 `observation_record_v1`，Telegram session log 仅作为 adapter / supplemental transport source。当前 aggregate/verifier 门槛保持不变，禁止借机降门槛或改口径 |
| 2026-04-01 | MVP12 scripted runtime harness 已拿到第一份主链样本：`scripts/run_runtime_mainline_observation.py` 在 `session:mvp12:runtime_harness:smoke` 下生成了 [runtime_harness_observation_current.jsonl](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/runtime_harness_observation_current.jsonl) 与配套 `.json` 摘要；4 条记录都包含 `runtime_status / runtime_reply_text / delivery_text / reply_authority / reply_origin / delivery_authority_source=response_contract.output_check`，说明 observation producer 已经过正式 runtime ingress + output_check/delivery shaping，而不是直接调 kernel |
| 2026-04-01 | MVP12 verifier 已拿到第一份 `runtime_harness` direct_real 报告：最新 [controlled_20260401_235928](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_20260401_235928/controlled_observation_report.md) 结果为 `direct_real_source_type = observation_record_v1`、`direct_real_transport_sources = [runtime_harness]`、`direct_real_cycles = 4`、`direct_real_window_count = 2`、`governance_violation_count = 0`、`replay_consistent = true`。这证明 `MVP12/WP7` 的主证据源已从 Telegram-specific adapter 扩展到统一 runtime 主链；但 aggregate 仍为 `hold`，因为 `span_hours = 2.005 < 12.0` |
| 2026-04-01 | MVP12 aggregate 已按新主证据源重算：当前 [controlled_observation_aggregate_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_observation_aggregate_current.md) 为 `report_count = 5`、`direct_real_report_count = 4`、`direct_real_window_count_total = 7`、`governance_violation_total = 0`、`replay_consistent_all = true`、`span_hours = 2.005`，裁决仍是 `hold`。当前唯一 blocker 继续固定为：**缺跨时段 direct_real windows**，不是 Telegram 入口问题，也不是 verifier/aggregate 能力问题 |
| 2026-04-02 | MVP12-A controlled proactive followup 已形成第一条正式主链脚手架：OpenEmotion `developmental_tick` 现会根据最近对话、未闭合 tension、long-term goal 生成 `background_thought_candidates`；EgoCore 新增 `initiative_arbiter`，只在 `gate allow + idle window 足够 + 无 active task + 候选不重复最近回复` 时，才经 `ResponsePlan + output_check` 生成 `controlled_shadow_delivery_draft`。当前验证为 `26 passed` 的定向测试，加上 [proactive_followup_current.json](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_followup_current.json) / [proactive_followup_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_followup_current.md) 这组 controlled artifact；口径仍是 **draft only**，不包含 live idle scheduler、主动 Telegram 投递、或 OpenEmotion 直接说话权 |
| 2026-04-02 | MVP12-A 已补上 `controlled idle scheduler`：`ChatState` 现持久化 `last_user_turn_at / last_assistant_reply_at / last_activity_at`，`RuntimeV2State` 新增 `pending_proactive_followup`，并由 `EgoCore/app/runtime_v2/initiative_scheduler.py` 在受控 idle 窗口里生成 `pending_created` 的 draft state，而不是直接发送消息。新 runner 为 [run_mvp12_idle_scheduler.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tools/run_mvp12_idle_scheduler.py)，当前 smoke artifact 见 [idle_scheduler_current.json](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/idle_scheduler_current.json) / [idle_scheduler_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/idle_scheduler_current.md)，关键结果为 `status = pending_created`、`delivery_status = pending`、`idle_seconds = 900.0`。当前验证口径为 `30 passed` 的定向回归 + 1 次 controlled smoke；仍然**没有** live unsolicited delivery，也没有 OpenEmotion 直接说话权 |
| 2026-04-02 | MVP12-A 已再补宿主侧 `controlled proactive delivery lane`：新增 [proactive_delivery.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proactive_delivery.py) 与 [run_mvp12_controlled_delivery.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tools/run_mvp12_controlled_delivery.py)，现在可以把 `pending_proactive_followup` 消费成 `artifact_emitted` 的 host-governed delivery record，而不是留在 pending state 或直接走 transport。当前 smoke artifact 见 [controlled_proactive_delivery_current.json](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_proactive_delivery_current.json) / [controlled_proactive_delivery_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/controlled_proactive_delivery_current.md)，关键结果为 `delivery_result.status = artifact_emitted`、`transport_source = controlled_runner`、`pending_proactive_followup = null`。当前验证口径为 `11 passed` 的定向回归 + 1 次 controlled smoke；仍然**没有** live idle scheduler、Telegram unsolicited delivery、或 OpenEmotion 直接说话权 |
| 2026-04-02 | MVP12-A 已再补宿主侧 `proactive outbox lane`：`RuntimeV2State` 新增 `pending_proactive_outbox_events` queue，新增 [proactive_outbox.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proactive_outbox.py) 与 [run_mvp12_proactive_outbox.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tools/run_mvp12_proactive_outbox.py)，现在可以把已经 `artifact_emitted` 的 controlled delivery record 再挂进宿主 `host_proactive_outbox` queue，而不是直接发往 transport。当前 smoke artifact 见 [proactive_outbox_current.json](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_outbox_current.json) / [proactive_outbox_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_outbox_current.md)，关键结果为 `outbox_result.status = queued`、`outbox_lane = host_proactive_outbox`、`pending_proactive_followup = null`、`pending_proactive_outbox_events[0].outbox_status = queued`。当前验证口径为 `15 passed` 的定向回归 + 1 次 controlled smoke；仍然**没有** Telegram 自动发送、live idle scheduler、或 OpenEmotion 直接说话权 |
| 2026-04-02 | MVP12-A 已再补宿主侧 `controlled outbox drain`：新增 [proactive_outbox_drain.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proactive_outbox_drain.py) 与 [run_mvp12_proactive_outbox_drain.py](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tools/run_mvp12_proactive_outbox_drain.py)，现在可以把 `host_proactive_outbox` queue 中的事件消费成 `simulated_outbox_record`，只生成模拟发送记录，不接 Telegram transport。当前 smoke artifact 见 [proactive_outbox_drain_current.json](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_outbox_drain_current.json) / [proactive_outbox_drain_current.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/mvp12/proactive_outbox_drain_current.md)，关键结果为 `drain_result.status = drained`、`transport_source = simulated_outbox_drain`、`pending_proactive_outbox_events = []`。当前验证口径为 `10 passed` 的定向回归 + 1 次 controlled smoke；仍然**不是**真实 Telegram 发送，也不是 live unsolicited delivery |

---

## 待办/待观察

- [ ] 补 `restore continuity` 真实样本
- [ ] 继续压 `artifacts/mvs_e5_observation` 中剩余 evidence gap
- [ ] 持续更新此文件

---

*此文件由Agents动态维护，记录项目核心记忆*
