# Legacy Structures

> 本文档标注 OpenEmotion 中已废弃或兼容性质的旧结构

---

## 重要声明

**OpenClaw 已不再是正式主链的一部分。**

从 2026-03-17 起，系统正式主链是：

```
真实入口 → EgoCore → emotiond(OpenEmotion) → EgoCore → 外部回复/任务/工具
```

**EgoCore 是 OpenEmotion 的唯一正式宿主。**

---

## integrations/openclaw/

**状态**: LEGACY / COMPATIBILITY / NOT PART OF FORMAL PRODUCTION CHAIN

| 字段 | 值 |
|------|-----|
| 类型 | 旧集成层 |
| 为什么存在 | P1 之前与 OpenClaw 的直接集成 |
| 当前角色 | 兼容层，**非正式主线** |
| 正式替代 | EgoCore `egocore/adapters/openemotion_adapter.py` |
| 风险 | 可能误导新参与者认为 OpenClaw Skill 是核心定位 |

**决策**:
- 不计入正式主链验收证据
- 不作为运行前提
- 新功能开发不考虑此集成

---

## openclaw_skill/emotion_core/

**状态**: LEGACY / COMPATIBILITY / NOT PART OF FORMAL PRODUCTION CHAIN

| 字段 | 值 |
|------|-----|
| 类型 | 旧 OpenClaw Skill 实现 |
| 为什么存在 | P1 之前作为 OpenClaw 技能包的集成 |
| 当前角色 | 兼容层，**非正式主线** |
| 正式替代 | EgoCore `egocore/adapters/openemotion_adapter.py` |
| 风险 | 与 README 新架构描述冲突 |

**决策**:
- 不计入正式主链验收证据
- 不作为运行前提
- 新功能开发不考虑此集成

---

## 非正式主线定义

以下路径是旧时代产物，**不作为当前架构的正式组成部分，不计入验收证据**：

- `integrations/openclaw/`
- `openclaw_skill/`

**正式主线**:

- `emotiond/` - 情感核心守护进程
- `schemas/` - Schema 定义
- `docs/` - 架构文档

**正式宿主**: EgoCore (https://github.com/pen364692088/EgoCore)

---

## 口径对照

| 旧口径 | 新口径 |
|--------|--------|
| "OpenClaw 已有 emotiond 扩展，因此主链基本通了" | "emotiond 服务可独立运行，EgoCore 直连 emotiond 已接通" |
| "通过 OpenClaw 触发的链路验证" | "legacy 验证，不计入正式主链证据" |
| "OpenClaw 是正式主链一部分" | "OpenClaw 仅作为 legacy/compat 残留，不再作为正式依赖" |

---

## 相关文档

- EgoCore 正式主链定义: https://github.com/pen364692088/EgoCore/blob/main/docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md
- OpenClaw Legacy 状态: https://github.com/pen364692088/EgoCore/blob/main/docs/LEGACY_OPENCLAW_DEPENDENCY_STATUS.md
- v6k 观察口径: https://github.com/pen364692088/EgoCore/blob/main/docs/MVP16_V6K_OBSERVATION_PROTOCOL.md

---

## 统计

| 类型 | 数量 |
|------|------|
| Legacy 目录 | 2 |
| 正式主线模块 | 3 (emotiond, schemas, docs) |
| 正式宿主 | 1 (EgoCore) |

---

最后更新: 2026-03-17
