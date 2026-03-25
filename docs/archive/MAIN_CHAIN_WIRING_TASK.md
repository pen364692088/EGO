# 主链 Wiring 任务单 - MVP13/15 接入验证

> 任务类型: 验证修复  
> 优先级: P0  
> 创建时间: 2026-03-16

---

## A. Capability Ownership

| 问题 | 答案 |
|------|------|
| 归属仓库 | OpenEmotion |
| 归属模块 | emotiond/core.py, openemotion/self_model, openemotion/identity |
| 能力类型 | 主体本体接入主链 |

---

## B. Authority Source

| 问题 | 答案 |
|------|------|
| 权威数据在哪 | openemotion/self_model/model.py |
| 谁定义字段语义 | OpenEmotion |
| Schema 位置 | schemas/self_model.schema.json |

---

## C. Mirror Need

| 问题 | 答案 |
|------|------|
| 是否需要 mirror | 是（过渡期） |
| 为什么需要 | emotiond/core.py 当前依赖 legacy self_model，需要双轨运行验证 |
| Mirror 位置 | emotiond/self_model_mirror.py (已存在) |
| 真相源位置 | openemotion/self_model/ |

---

## D. Boundary Risk

| 风险类型 | 是否存在 | 说明 |
|----------|----------|------|
| 双主风险 | 否 | 只有一个真相源 (openemotion) |
| Shim 永久化风险 | 否 | legacy self_model 将被废弃 |
| 边界回退风险 | 否 | 正确方向 |

---

## E. Failure Owner

| 问题 | 答案 |
|------|------|
| 失败由谁兜底 | OpenEmotion |
| 失败影响范围 | emotiond/core.py 主链 |
| 恢复策略 | 回退到 legacy self_model |

---

## F. Exit Plan

| 问题 | 答案 |
|------|------|
| 是否有临时实现 | 是 |
| 临时实现位置 | emotiond/self_model_mirror.py |
| 删除/迁移时间 | MVP13 verified 后 |
| 删除动作 | 移除 emotiond/self_model*.py |

---

## 任务范围

### 必须完成

- [ ] 1. 在 emotiond/core.py 中导入 openemotion.self_model
- [ ] 2. 创建 adapter 或 bridge 连接新旧接口
- [ ] 3. 添加 feature flag 控制 legacy/new 切换
- [ ] 4. 在 shadow mode 下运行并收集数据
- [ ] 5. 验证新 self_model 的输出与 legacy 一致或有改进

### 明确不做

- [ ] 完全删除 legacy self_model
- [ ] 修改 openemotion/self_model 的语义
- [ ] 跳过 shadow 验证直接切换

---

## 当前状态

### 已有组件

| 组件 | 路径 | 状态 |
|------|------|------|
| legacy self_model | emotiond/self_model.py | ✅ 主链使用 |
| new self_model | openemotion/self_model/model.py | ⚠️ 未接入主链 |
| mirror | emotiond/self_model_mirror.py | ✅ 存在 |
| schema | schemas/self_model.schema.json | ✅ 存在 |

### 需要创建

| 组件 | 用途 |
|------|------|
| self_model_adapter.py | 连接 openemotion.self_model 到 emotiond/core.py |
| feature flag | 控制 legacy/new 切换 |
| shadow mode | 双轨运行收集数据 |

---

## Gate 验收

### Gate A: Contract

- [ ] adapter 边界清晰
- [ ] 不修改 openemotion.self_model 语义
- [ ] feature flag 存在

### Gate B: E2E

- [ ] shadow mode 运行成功
- [ ] 新 self_model 输出有效
- [ ] 无主链崩溃

### Gate C: Integrity

- [ ] 无双主
- [ ] legacy/new 可切换
- [ ] 可回滚

---

## 完成标准

| 标准 | 状态 |
|------|------|
| 新 self_model 接入主链（shadow mode） | [ ] |
| feature flag 控制 | [ ] |
| shadow 数据收集 | [ ] |
| PROGRAM_STATE_UNIFIED.yaml 更新 | [ ] |

---

## 禁止事项

- ❌ 跳过 shadow 直接切换
- ❌ 修改新 self_model 语义
- ❌ 删除 legacy self_model（过渡期保留）
