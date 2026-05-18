# Boundary Migration Policy

> 版本: 1.0.0
> 日期: 2026-03-16

---

## 1. 边界原则

### 1.1 双核架构

- **EgoCore**：宿主，负责与世界交互
- **OpenEmotion**：内核，负责主体本体

### 1.2 禁止双主

任何模块不能同时在 EgoCore 和 OpenEmotion 拥有本体定义。

### 1.3 权威源唯一

每个主体能力有且仅有一个权威源。

---

## 2. 归属判定规则

按以下顺序判定模块归属：

1. **权威数据归属**：数据定义在谁那里？
2. **字段语义解释权**：谁定义字段含义？
3. **失败兜底责任**：谁负责失败处理？
4. **现实动作裁决权**：谁决定最终行为？

---

## 3. 允许的边界行为

### 3.1 EgoCore 允许

- **mirror**：缓存 OpenEmotion 数据
- **loader**：加载 OpenEmotion 产物
- **validator**：验证 OpenEmotion 输出
- **injector**：注入到 runtime
- **adapter**：适配 OpenEmotion 接口
- **audit**：记录操作轨迹

### 3.2 禁止

- 定义主体本体字段语义
- 实现主体本体生成逻辑
- 维护独立的主体状态

---

## 4. Shim 管理规则

### 4.1 定义

**shim**：临时性的边界桥接实现，用于过渡期。

### 4.2 要求

所有 shim 必须：

1. 在 `SHIM_REGISTER.md` 登记
2. 说明为什么需要 shim
3. 标明正式归属模块
4. 设定到期版本
5. 制定删除计划

### 4.3 禁止

- 未登记 shim 长期存在
- shim 变成永久实现
- shim 成为第二真相源

---

## 5. 新功能开发规则

### 5.1 六问门禁

每个新功能开发前必须回答：

1. **Capability Ownership**: 归 EgoCore 还是 OpenEmotion？
2. **Authority Source**: 权威数据在哪里？
3. **Mirror Need**: 是否需要 cache/mirror/shim？为什么？
4. **Boundary Risk**: 是否有双主风险？
5. **Failure Owner**: 失败由谁兜底？
6. **Exit Plan**: 如果有临时实现，何时删除？

缺一不可，禁止开写。

### 5.2 WS-C 及后续限制

从 WS-C/C1 开始，以下内容禁止写入 EgoCore：

- memory model 本体
- salience/consolidation 本体
- relationship semantics 本体
- appraisal/emotion 本体
- reflection/policy promotion 本体

---

## 6. 迁移流程

### 6.1 标准迁移流程

```
1. 审计归属
   ↓
2. 在目标仓库创建正式模块
   ↓
3. EgoCore 改为读取目标产物
   ↓
4. 登记 shim
   ↓
5. 删除或降级旧实现
   ↓
6. 验证主链完整性
```

### 6.2 回滚策略

如果迁移导致主链不稳定：

1. 恢复 shim
2. 回退到上一版本
3. 分析失败原因
4. 修复后重新迁移

---

## 7. 审计要求

### 7.1 定期审计

- 每月检查 SHIM_REGISTER.md
- 确认所有 shim 都有删除计划
- 确认没有未登记的越界实现

### 7.2 Gate 检查

每次迁移必须通过：

- **Gate A**: 边界合同正确
- **Gate B**: E2E 联动正常
- **Gate C**: 审计轨迹完整

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-16 | 初始版本 |
