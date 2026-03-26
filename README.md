# EGO - AI Agent Monorepo

EGO 是 AI Agent 项目的总仓，负责集成 EgoCore（宿主）和 OpenEmotion（主体内核）。

## 当前状态

**Proto-Self Kernel v1** 已完成稳态收口：
- ✅ Cycle 聚合机制正常工作
- ✅ Reflection 机制正常工作
- ✅ 高风险操作与低风险操作被正确区分
- ✅ `safety_context.risk` 从 EgoCore 正确传递到 OpenEmotion
- ✅ **真实 Telegram 已满足 E5 准入门槛，可进入 E5 观察期**

## 最近更新

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
- 真实 Telegram 双样本验证通过

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

## 最近更新

### 2026-03-25: P0-R2 Risk Signal 接线
- 修复 `safety_context.risk` 字段名不匹配问题
- 高风险操作 psi_bucket 包含 `:risk_high` 后缀
- 高低风险操作被分配到不同 cycle

### 2026-03-25: P0-R1 真实 Telegram 验证
- EgoCore 服务在真实 Telegram 环境正常运行
- Cycle 聚合机制工作正常
- Reflection 机制工作正常

### 2026-03-25: P0 高风险误聚合修复
- psi_bucket 追加 risk_level 区分
- 关键词优先级冲突修复
- 5/5 回归测试通过

---

*此文件随项目演进持续更新*
