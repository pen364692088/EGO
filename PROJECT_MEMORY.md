# PROJECT_MEMORY.md

> AIProject 核心记忆 - Claude Code 持续更新
> 最后更新: 2026-03-28

---

## 项目概览

| 项目 | 值 |
|------|------|
| 名称 | EGO - AI Agent Monorepo |
| 架构 | EgoCore (宿主) + OpenEmotion (主体内核) 分层设计 |
| 路径 | `D:\Project\AIProject\MyProject\Ego` |
| 子仓库 | EgoCore, OpenEmotion (subtree 集成) |

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

### Codex Assistant Memory
- 稳定记忆索引: `CODEX_MEMORY.md`
- 结构化源文件: `.codex/memory/project_truth.jsonl` + `.codex/memory/user_preferences.jsonl`
- 本地任务/会话衔接: `.codex/memory/tasks/` + `.codex/memory/sessions/`
- 规则: 任务边界继续新开会话；同一任务内可依赖 session capsule 减少重开
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
| E5 准入门槛 | 进入观察期前，至少要有 1 个完整普通 real 样本 + 1 个完整且命中高风险路径的 real 样本 |
| Cycle 身份升级 | `cycle_id` 已从纯 `psi_bucket` 聚合升级为 closure-sensitive signature，可区分 success / failure / repair 等 closure；仍未达到 full multi-step closure graph identity |
| P4 修复口径 | `closure_family_id` 现由 coarse `family_bucket + action_signature` 决定，不再被 `risk_high` 这类 psi 后缀拆开；真实 `tool:file` blocked -> retry success 已可点亮一次 `repair_closure=true` |
| 显式默认规则 continuity | 显式默认规则现由 EgoCore `ProfileMemory` 持久化；`/new` 后可继续命中，且 `response_plan` 已记录 `authority_source=profile_memory`、`matched_rule_ids`、`rule_enforcement` |
| MVS E5 当前口径 | `/new continuity` 与 `restore continuity` 已有 `direct_real` 真实正证据；`restart continuity` 仍主要是 `cross_evidence`。当前仍不能报 `E5 稳定成立` 或 `Developmental Self` 准入通过，最高优先级缺口已转为 post-restart 完整样本与剩余 evidence gap |
| Codex 记忆层验收 | 开发助手侧结构化记忆已在真实新会话中验证：`CODEX_MEMORY.md` 可恢复稳定真相；`TaskHandoffRecord` 为当前任务主权威；同任务 `SessionCapsule` 可辅助连续性；异任务 capsule 会被拒绝；当前仍是手动喂入/脚本辅助启动 |

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

---

## 待办/待观察

- [ ] 补 `restore continuity` 真实样本
- [ ] 继续压 `artifacts/mvs_e5_observation` 中剩余 evidence gap
- [ ] 持续更新此文件

---

*此文件由Agents动态维护，记录项目核心记忆*
