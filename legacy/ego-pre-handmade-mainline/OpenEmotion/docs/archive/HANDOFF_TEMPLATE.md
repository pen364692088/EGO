# HANDOFF_TEMPLATE.md

> 新会话接管模板  
> 版本: v1.0.0

---

## 1. 读取顺序

1. `docs/DUAL_REPO_STATUS_UNIFIED.md` - 统一状态
2. `roadmap/ROADMAP_STATE.json` - MVP 状态
3. `README.md` - 公开状态
4. `POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md` - 边界宪章

---

## 2. 当前状态口径

### 正确表述

```
EgoCore: 宿主稳定期，Phase 3 完成，shadow observation
OpenEmotion: MVP16 观测期 (Day 4/14)，MVS 已完成 WS-C/C1
MVS 主线: 下一步是 WS-C/C2 Salience
```

### 错误表述

```
❌ "OpenEmotion 只到 C1"
❌ "C1 是整体版本上限"
❌ "EgoCore 实现记忆系统"
```

---

## 3. 边界约束

| 仓库 | 允许 | 禁止 |
|------|------|------|
| EgoCore | mirror/cache/loader | 主体本体逻辑 |
| OpenEmotion | identity/memory/appraisal | 工具执行/渠道接入 |

---

## 4. 下一步主线

| 优先级 | 任务 | 仓库 |
|--------|------|------|
| P1 | WS-C/C2: Salience | OpenEmotion |
| P2 | 记忆系统与 adapter 集成 | 双仓 |
| P3 | WS-D: Appraisal | OpenEmotion |

---

## 5. 禁止事项

- ❌ 新增主体本体到 EgoCore
- ❌ 把 mirror 变成真源
- ❌ 混用 Phase/MVP/MVS 体系
- ❌ 声称完成但无验证

---

**接管时先读取 DUAL_REPO_STATUS_UNIFIED.md，再开始工作。**
