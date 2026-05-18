# EgoCore 模块开发标准 v1.0

## 目标

后续新功能默认采用：

**先定义契约 → 再独立开发模块 → 再做隔离验证 → 观察期通过后再接入主链**

目的：
- 保护当前稳定主链
- 允许后续功能并行开发
- 降低后期接主链返工风险
- 保证每个模块可独立验证、可回滚、可观测

---

## 强制原则

### 1. 当前稳定主链默认冻结

观察期内只允许：
- 阻塞性 bug 修复
- 安全修复
- 兼容性修复

禁止：
- 顺手往主链塞新功能
- 为新模块提前大改主链
- 边观察边重构主流程

### 2. 契约先于实现

任何新模块编码前，必须先定义清楚：
1. 解决什么真实问题
2. 谁调用它
3. 输入是什么
4. 输出是什么
5. 失败时怎么返回
6. 未接主链时怎么独立验证

**没有 contract，不允许开写。**

### 3. 模块必须可独立运行

每个模块在未接主链前，必须能通过以下方式独立验证：
- mock input
- stub dependency
- local integration
- fallback simulation

目标：**模块先能单独跑通，后面只补 integration point。**

### 4. 强制分层

每个模块默认拆成：
- `core`：业务逻辑
- `contract`：输入输出/错误/fallback 定义
- `adapter`：外部上下文转换
- `integration`：决定什么时候接主链
- `observability`：日志、metrics、trace

禁止模块 core 直接绑死 Telegram、reply pipeline、任务状态机等主链细节。

### 5. 失败不能拖垮主链

每个模块都必须明确：
- timeout 语义
- dependency down 语义
- invalid response 语义
- fallback 行为
- 用户可见行为

原则：**模块失败只能降级，不能拖垮主链。**

---

## 标准开发流程

### Phase 1：问题定义

先写清楚：
- 用户真实抱怨
- 当前系统行为
- 最小决策点
- 主解决链
- 保险链
- 一周后若问题还在，说明没打中哪里

### Phase 2：契约定义

至少定义：
- module name
- responsibility
- caller
- trigger condition
- input schema
- output schema
- error schema
- fallback behavior
- timeout policy
- non-goals

### Phase 3：独立实现

固定顺序：
1. 写 contract
2. 写 core
3. 写 adapter
4. 写 mock/stub
5. 写 tests
6. 写 minimal metrics/logs

禁止先接主链再回头补契约。

### Phase 4：隔离验证

未接主链前必须验证：
- 正常输入输出正确
- 边界输入安全
- 空结果可处理
- 依赖异常可 fallback
- 日志与 metrics 可用

### Phase 5：接主链前必须过 3 道门

#### Gate A｜Contract

必须明确：
- [ ] input/output schema
- [ ] error schema
- [ ] fallback schema
- [ ] timeout schema

#### Gate B｜E2E

即使是 mock E2E，也必须覆盖：
- [ ] success
- [ ] skip
- [ ] fallback
- [ ] error

#### Gate C｜Preflight

必须确认：
- [ ] 不会破坏当前稳定主链
- [ ] integration point 唯一且可控
- [ ] 支持 feature flag / fast disable / rollback
- [ ] metrics/logging 已埋好

### Phase 6：观察后接主链

只有当前系统观察窗口通过后，才允许正式挂主链。

接入要求：
- 小步接入
- 单点接入
- 可关闭
- 可回滚
- 可观测
- 不顺手重构无关主链

---

## 优先适合先独立孵化的模块

优先做这类：
- memory adapter
- reply enhancer
- emotion context formatter
- runtime metrics aggregator
- event adapter
- safety decision helper
- planning helper

---

## 观察期内不要优先动的东西

原则上不动：
- Telegram 主入口重构
- intent 主分类器大改
- task 生命周期主逻辑重构
- session 主行为切换逻辑大改
- reply pipeline 全量重写

---

## 明确禁止事项

禁止：
1. 没有 contract 就开写
2. 模块 core 直接读主链内部状态
3. 为以后接入方便先改一堆主链
4. 没有 fallback 就准备上线
5. 没有 metrics/logs 就说模块可接入
6. 观察期边收数据边改主链
7. 把"模块可运行"等同于"主链可上线"

---

## 最低交付要求

每个模块至少交付：

### 代码
- core
- adapter
- integration stub
- metrics/logging

### 文档
- module contract
- design note
- fallback note
- integration plan

### 测试
- unit
- contract test
- integration test
- fallback test

### 验收
- Gate A 通过记录
- Gate B 通过记录
- Gate C 通过记录
- 接主链前风险说明

---

## 完成标准

一个模块只有同时满足以下条件，才允许进入"待接主链"状态：

1. [ ] 真实问题定义清楚
2. [ ] contract 已冻结
3. [ ] core 已完成
4. [ ] adapter 已完成
5. [ ] mock/integration 验证通过
6. [ ] fallback 成立
7. [ ] logs/metrics 可用
8. [ ] Gate A/B/C 全部通过
9. [ ] 已有明确 integration point
10. [ ] 已定义回滚方案

---

## 一句话执行指令

**EgoCore 后续功能一律按"契约先行、模块独立、隔离验证、观察后接主链"执行；未通过 Gate A / Gate B / Gate C 的模块，禁止接入当前稳定主链。**
