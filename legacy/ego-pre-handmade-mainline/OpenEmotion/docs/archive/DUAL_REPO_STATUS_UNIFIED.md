# DUAL_REPO_STATUS_UNIFIED.md

> 双仓统一状态文档  
> 版本: v1.1.0  
> 最后更新: 2026-03-16

> **权威源**: 本文档已过时，请以 `PROGRAM_STATE_UNIFIED.yaml` 为准。

---

## 1. 边界账（长期固定）

| 仓库 | 角色 | 权威源职责 |
|------|------|------------|
| **EgoCore** | 宿主 / 运行时 / 治理 | 用户入口、任务执行、工具系统、恢复机制、审计追踪 |
| **OpenEmotion** | 主体内核 | identity、self-model、memory、appraisal、reflection |

### 硬边界

| EgoCore 允许 | EgoCore 禁止 |
|--------------|--------------|
| host-side mirror/cache | memory model semantics |
| loader/validator | salience semantics |
| compatibility guard | consolidation semantics |
| restore injector | relationship semantics |
| replay/audit/trace | appraisal state semantics |
| runtime orchestration | reflection/policy promotion |

**允许 mirror，禁止双主。**

---

## 2. 版本账（三套体系）

### 2.1 EgoCore Phase 体系

| 阶段 | 状态 |
|------|------|
| Phase 1: 核心功能 | ✅ 完成 |
| P2-A: 工具执行安全边界 | ✅ 完成 |
| P2-A.1: 主链接线收口 | ✅ 完成 |
| P2-A.2: 意图映射+后置条件 | ✅ 完成 |
| P2-B: 后台推进闭环 | ✅ 完成 |
| P2-C: Human-in-the-Loop | ✅ 完成 |
| P2-D: Operator Control | ✅ 完成 |
| P3-A: 模块化开发规约 | ✅ 完成 |
| P3-B: emotion_context_formatter | ✅ 完成 |
| P3-C: runtime_metrics dry-run | ✅ 完成 |
| P3-D: runtime_metrics 接主链 | ✅ 完成 |

**当前状态**: 宿主稳定期，进入 shadow observation

---

### 2.2 OpenEmotion MVP 体系

| 阶段 | 状态 | 备注 |
|------|------|------|
| MVP11.5 | ✅ 完成 | SRAP Stabilization |
| MVP12 | ⚠️ 声称完成，未验证 | Developmental Core |
| MVP13 | ⚠️ 声称完成，未验证 | Persistent Self-Model |
| MVP14 | ⚠️ 声称完成，未验证 | Endogenous Drives |
| MVP15 | ⚠️ 声称完成，未验证 | Reflective Self |
| MVP16 | 🔄 观测期 (Day 4/14) | Open Developmental Self |

**当前状态**: MVP16 blocked (mvp13_mvp15_wiring_not_proven)

---

### 2.3 MVS (Minimum Viable Self) 体系

> **警告**: 本节已过时，请以 `PROGRAM_STATE_UNIFIED.yaml` 为准。

| 阶段 | 状态 | 说明 |
|------|------|------|
| WS-A | verified_contract | 持续身份 |
| WS-B | verified_contract | Self-Model v1 |
| WS-C/C1 | code_exists | 三层记忆模型 v1 (未验证) |
| WS-C/C2 | planned | Salience |
| WS-D | planned | Appraisal |
| WS-E | planned | Reflection |

**当前状态**: disputed (WS-C/C1 code_exists not verified)

---

### 2.4 体系关系

```
MVS (主体演化主线)
├── WS-A: 持续身份 ✅
├── WS-B: Self-Model v1 ✅
├── WS-C: 记忆演化
│   ├── C1: 三层记忆模型 ✅
│   ├── C2: Salience 📋
│   └── C3: Consolidation 📋
├── WS-D: Appraisal 📋
└── WS-E: Reflection 📋

OpenEmotion MVP (产品版本线)
├── MVP11-15: 历史/声称完成
└── MVP16: 当前观测期 (依赖 MVS)

EgoCore Phase (宿主版本线)
├── Phase 1-3 ✅
└── Shadow Observation 🔄
```

---

## 3. 验证账

### 3.1 EgoCore 验证

| 项目 | 状态 |
|------|------|
| 测试通过 | 139 passed |
| Shadow Observation | Day 1/14 |
| Gate A/B/C | ✅ PASS |

### 3.2 OpenEmotion 验证

| 项目 | 状态 |
|------|------|
| MVP16 Daily Check | persistence-backed ✅ |
| MVP13-MVP15 Wiring | ⚠️ 未证明 |
| Gate A/B/C | ✅ PASS (边界整改) |

### 3.3 边界验证

| 项目 | 状态 |
|------|------|
| SHIM_REGISTER.md | ✅ 4 个 shim 已登记 |
| 边界宪章 | ✅ 存在 |
| EgoCore 主体本体残留 | ✅ 无新增 |

---

## 4. 当前真实差距

### 4.1 EgoCore

- **差距**: 无重大差距
- **状态**: 稳宿主、守边界
- **风险**: 低

### 4.2 OpenEmotion

- **差距**: MVP13-MVP15 wiring 未证明
- **状态**: MVP16 blocked
- **风险**: 声称完成但未验证的模块可能存在问题

### 4.3 MVS

- **差距**: C2/C3/D/E 未开发
- **状态**: C1 已完成，主线清晰
- **风险**: 低（按路线图推进）

---

## 5. 当前唯一主线

### 主线: OpenEmotion MVS 演进

| 优先级 | 任务 | 仓库 |
|--------|------|------|
| P1 | WS-C/C2: Salience | OpenEmotion |
| P2 | 记忆系统与 EgoCore adapter 集成 | OpenEmotion + EgoCore |
| P3 | WS-D: Appraisal | OpenEmotion |

### 非主线

| 优先级 | 任务 | 原因 |
|--------|------|------|
| - | EgoCore 新增主体本体 | 边界禁止 |
| - | MVP17 新功能 | MVP16 blocked |
| - | 多 Agent 编排 | 超出当前范围 |

---

## 6. 禁止事项

### 6.1 EgoCore 禁止

- ❌ 新增 memory model semantics
- ❌ 新增 salience/consolidation 逻辑
- ❌ 新增 appraisal/reflection 本体
- ❌ 把 mirror 变成真源

### 6.2 OpenEmotion 禁止

- ❌ 直接执行工具
- ❌ 直接接入渠道
- ❌ 越过 EgoCore 做高风险操作

### 6.3 口径禁止

- ❌ 把 WS-C/C1 写成"OpenEmotion 整体进度上限"
- ❌ 把 Phase/MVP/MVS 混用
- ❌ 声称完成但无验证证据

---

## 7. 后续进入条件

### 进入 WS-C/C2 (Salience)

| 条件 | 状态 |
|------|------|
| C1 三层记忆模型 | ✅ 完成 |
| 边界宪章遵守 | ✅ 验证 |
| 六问门禁 | 📋 待写 |

### 进入 MVP16 解除阻塞

| 条件 | 状态 |
|------|------|
| MVP13-MVP15 wiring 证明 | ⚠️ 未完成 |
| 主链接入验证 | ⚠️ 未完成 |

---

## 8. 统一表述规范

### 正确表述

| 场景 | 正确说法 |
|------|----------|
| OpenEmotion 整体状态 | "OpenEmotion 正处于 MVP16 观测期，MVS 已完成 WS-C/C1" |
| WS-C/C1 定位 | "WS-C/C1 是 MVS v1 的当前主线缺口，已完成" |
| 下一步 | "推进 WS-C/C2 Salience，在 OpenEmotion" |

### 错误表述

| 场景 | 错误说法 |
|------|----------|
| 整体进度 | "OpenEmotion 只到 C1" ❌ |
| C1 定位 | "C1 是整体版本上限" ❌ |
| EgoCore 职责 | "EgoCore 实现记忆系统" ❌ |

---

## 9. 状态文件索引

| 文件 | 仓库 | 用途 |
|------|------|------|
| README.md | EgoCore | 宿主公开状态 |
| README.md | OpenEmotion | 主体公开状态 |
| docs/CURRENT_STATE.md | EgoCore | 宿主详细状态 |
| roadmap/ROADMAP_STATE.json | OpenEmotion | MVP 版本状态 |
| docs/DUAL_REPO_STATUS_UNIFIED.md | 本文档 | 统一口径 |

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-03-15 | 创建统一状态文档，明确三套版本体系关系 |

---

**一句话总结**: EgoCore 稳宿主，OpenEmotion 承接主体本体，MVS 是当前主线，WS-C/C1 已完成而非上限。
