# New Feature Boundary Gate

> 版本: 1.0.0
> 日期: 2026-03-16

---

## 1. 目的

确保每个新功能开发前都经过边界检查，防止边界漂移。

---

## 2. 六问门禁模板

每个新功能任务书必须包含以下六节：

### 2.1 A. Capability Ownership

**问题**: 归 EgoCore 还是 OpenEmotion？

**判定规则**:
- 主体本体能力 → OpenEmotion
- 宿主交互能力 → EgoCore
- 治理审计能力 → EgoCore

**答案**: [填写]

---

### 2.2 B. Authority Source

**问题**: 权威数据在哪里？

**判定规则**:
- 主体本体数据 → OpenEmotion
- 运行时状态数据 → EgoCore
- 用户交互数据 → EgoCore

**答案**: [填写]

---

### 2.3 C. Mirror Need

**问题**: 是否需要 cache/mirror/shim？为什么？

**判定规则**:
- 需要 → 说明原因和过期条件
- 不需要 → 确认所有数据直接读取权威源

**答案**: [填写]

---

### 2.4 D. Boundary Risk

**问题**: 是否有双主风险？是否可能让 shim 永久化？

**判定规则**:
- 如果两边都定义相同字段 → 双主风险
- 如果 shim 没有删除计划 → 永久化风险

**答案**: [填写]

---

### 2.5 E. Failure Owner

**问题**: 失败由谁兜底？

**判定规则**:
- 本体逻辑失败 → OpenEmotion 负责
- 加载/注入失败 → EgoCore 负责
- 接口适配失败 → adapter 负责

**答案**: [填写]

---

### 2.6 F. Exit Plan

**问题**: 如果有临时实现，何时删除？

**要求**:
- 所有临时实现必须有删除计划
- 标明到期版本
- 迁移完成后必须删除

**答案**: [填写]

---

## 3. 示例

### 示例: 添加 Event Memory

#### A. Capability Ownership
归 OpenEmotion。Memory 属于主体本体。

#### B. Authority Source
权威数据在 OpenEmotion/openemotion/memory/。

#### C. Mirror Need
EgoCore 需要 host-side mirror 用于 restore 时快速加载。mirror 值从 OpenEmotion 快照读取。

#### D. Boundary Risk
无双主风险。EgoCore 只缓存，不定义 memory 本体。

#### E. Failure Owner
memory 本体逻辑失败 → OpenEmotion 负责。加载失败 → EgoCore 的 memory_loader 负责。

#### F. Exit Plan
无临时实现。

---

## 4. 审批流程

1. 任务书包含六问门禁
2. 检查边界是否正确
3. 通过后才能开始开发
4. 不通过需要重新设计

---

## 5. 禁止行为

- 跳过六问门禁直接开发
- 六问门禁回答模糊
- 故意绕过边界检查
- 迁移时不更新六问门禁

---

## 6. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-16 | 初始版本 |
