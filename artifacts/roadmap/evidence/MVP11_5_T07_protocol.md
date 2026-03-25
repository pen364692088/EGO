# T07 Execution Plan - Data Layering

**Generated**: 2026-03-08T18:18:00-05:00
**Type**: Execution Protocol

---

## 数据分层定义

### Layer 1: Test Data
- 来源: testbot / 集成测试 / 批跑数据
- 用途: 回归与场景覆盖证据
- 标识: session_id 为空或以 `test_` 开头

### Layer 2: Controlled Runtime-Path Data
- 来源: daemon 已启动，通过真实 API/事件入口
- 要求: session_id 非空且非 test_*
- 用途: 证明 runtime wiring 生效

### Layer 3: Natural Runtime Data
- 来源: 真实自然使用过程
- 若本轮没有，必须明确写"暂无"

---

## T07-A 目标

1. 启动 emotiond daemon
2. 通过真实 /plan 或 /event API 注入事件
3. 生成 fresh shadow log 数据
4. 验证 contract/checker/shadow logging 生效

---

## 样本要求

- 至少覆盖 interpreted 默认链路
- 至少覆盖单轮与多轮
- 至少覆盖：
  - epistemic upgrade risk
  - numeric leak risk
  - commitment boundary risk
  - multi-turn intent drift risk

---

## 口径边界

- ❌ 不进入 MVP12
- ❌ 不调整 promotion criteria
- ❌ 不直接切 Enforced
- ❌ 不把 controlled runtime-path data 说成 natural runtime
- ❌ 不把 test data 说成 runtime evidence

---

**Generated**: 2026-03-08T18:18:00-05:00
