# Legacy OpenClaw Dependency Status

## 声明

**OpenClaw 不再是 EgoCore + OpenEmotion 双核系统的正式主链组成部分。**

所有涉及 OpenClaw 的集成、扩展、插件、配置，统一降级为：
- `legacy`
- `compat only`
- `not part of formal production chain`

## 受影响内容

### OpenEmotion 仓库

| 路径 | 状态 | 说明 |
|------|------|------|
| `integrations/openclaw/` | legacy | 历史兼容，不作为正式依赖 |
| `openclaw_skill/` | legacy | 历史兼容，不作为正式依赖 |
| `~/.openclaw/extensions/emotiond/` | legacy | OpenClaw 扩展，不计入正式主链验收 |

### 验收证据排除

以下内容**不再计入正式主链验收证据**：
- OpenClaw emotiond 扩展已配置
- 通过 OpenClaw 触发的 emotiond 调用
- OpenClaw 服务状态

## 正式主链

**唯一正式主链**：
```
真实入口 → EgoCore → emotiond(OpenEmotion) → EgoCore → 外部回复/任务/工具 → 结果回流
```

**正式宿主**：EgoCore
**被宿主组件**：OpenEmotion (emotiond)

## 迁移状态

| 项目 | 状态 |
|------|------|
| EgoCore 直连 emotiond | 进行中 |
| 正式入口切换 | 待完成 |
| legacy 目录清理 | 待决策 |

## 参考

- `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md` - 正式主链定义
- `docs/EGOCORE_HOSTING_PROGRESS.md` - 宿主化进展

---

**创建日期**: 2026-03-17
**生效日期**: 即日起
