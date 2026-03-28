# EGO - AI Agent Monorepo

EGO 是 AI Agent 项目的总仓，负责集成 EgoCore（宿主）和 OpenEmotion（主体内核）。

## 当前权威状态

截至 2026-03-28，当前入口口径统一如下：

- **Proto-Self Kernel v1** 已完成真实 Telegram 主链接入，并完成 P4 真链修复
  - `tool:file` blocked / success 已在真实样本中同 family、不同 identity
  - 首次 retry-success 已在真实样本中点亮 `repair_closure=true`
- **MVS E5 观察状态**：`/new continuity` 与 `restore continuity` 已有 `direct_real` 真实正证据，`restart continuity` 仍主要是跨证据链正证据
  - 显式默认规则现已在真实链路中由 `profile_memory` 持久化并在多次 `/new` 后继续命中
  - `restore continuity` 已有显式 `--restore --telegram` 主链、首条 post-restore 完整 E4 样本、以及 post-restore continuity probe
  - `restart continuity` 已有“真实重启日志 + post-restart 命中样本”的跨证据链正证据，但 post-restart 命中样本仍非完整单样本 E4 bundle
  - 当前仍不能宣称 `E5 稳定成立` 或 `Developmental Self` 准入通过
- **Codex Assistant Memory**：开发助手侧结构化持久记忆已完成首轮真实新会话验收
  - `CODEX_MEMORY.md` 可恢复稳定项目真相与长期偏好
  - `TaskHandoffRecord` 为当前任务主权威
  - 同任务 `SessionCapsule` 可补充连续性，异任务 capsule 会被明确拒绝
  - 当前仍是手动喂入/脚本辅助启动，不是全自动注入
- **EgoCore Telegram 正式主线** 是：
  - `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
  - 旧 `runtime_v2` 保留为兼容/桥接层，不再是 Telegram 当前正式执行口径
- **最新报告**
  - `artifacts/closure_real_evidence/CLOSURE_REAL_EVIDENCE_REPORT.md`
  - `artifacts/closure_repair_fix/CLOSURE_REPAIR_FIX_REPORT.md`
  - `artifacts/mvs_e5_observation/MVS_E5_OBSERVATION_REPORT.md`
  - `artifacts/mvs_e5_observation/OBSERVATION_SAMPLE_INDEX.md`
  - `artifacts/mvs_e5_observation/TARGETED_CAPTURE_PLAN.md`
  - `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
  - `PROJECT_MEMORY.md`

## 最近更新

### 2026-03-28: Codex 记忆层新会话验收通过
- 开发助手侧结构化记忆已在真实新会话中验证：稳定记忆恢复、TaskHandoff 优先级、同任务 SessionCapsule 采用、异任务 capsule 拒绝污染均已成立
- 当前形态仍是“结构化记忆 + 手动喂入/脚本辅助启动”，不是全自动注入
- 相关入口文档：`CODEX_MEMORY.md`、`.codex/memory/README.md`、`PROJECT_MEMORY.md`

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
