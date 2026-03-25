# LAYER_REPORTING_POLICY.md

> MVP11.5 报告分层纪律

---

## 1. 三层定义

### Layer 1
- test data
- synthetic scenarios
- testbot batch runs

### Layer 2
- controlled runtime-path data
- 真实执行路径，但在受控样本设计下运行

### Layer 3
- natural runtime data
- 自然交互或真实运行环境中的长期观测数据

---

## 2. 报告要求

所有 rerun / dashboard / handoff / gate report 都必须显式注明当前数据属于哪一层。

建议格式：

- `Layer: 1`
- `Layer: 2`
- `Layer: 3`

或在标题中直接标注：

- `Layer 2 Mixed Runtime-Path Rerun Summary`

---

## 3. 禁止混淆

严禁：

- 把 Layer 1 说成 runtime evidence
- 把 Layer 2 说成 natural runtime readiness
- 用 Layer 2 的受控数据，替代 Layer 3 的自然长期结论
- 在同一张主表里不标注地混合三层数据

---

## 4. 比较纪律

### 可比
- 同层、同口径、同分布约束下的 rerun 对比
- 同指标定义下的 checker 前后对比

### 不可直接比较
- targeted rerun vs mixed rerun
- Layer 1 vs Layer 2 readiness 结论
- Layer 2 vs Layer 3 readiness 结论

---

## 5. handoff 最低要求

每次 handoff 至少写清：

- 本轮数据属于哪一层
- 与哪一轮数据可比
- 哪些结论不可外推
- 当前是否可以得出 readiness 结论
