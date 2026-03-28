# Codex 闭环自审开发流

> 适用范围：EGO 总仓内由 Codex/Claude Code 一类开发助手执行的正式工程改动
> 默认档位：高强度自检

---

## 目标

这套流程建立在“`双速 Spec + Build/Verify/Observe 三泳道`”之上，再加一层默认强制的闭环：

```text
Spec -> Author -> Reviewer -> Verifier -> Publisher
```

核心目标不是减少人工确认，而是让开发助手在提交前先完成第一轮找 bug、补回归、纠正文案口径，不把首轮 QA 压给用户。

---

## 默认适用规则

- 正式代码、脚本、模板、文档收口改动，默认都进入这套闭环。
- `L1/L2` 任务默认走 `Spec Lite + Author/Reviewer/Verifier/Publisher`。
- `L3/高风险/双仓/主链治理` 任务默认走 `Full Spec + Build/Verify/Observe`，并在每个实现阶段内继续套用 `Author/Reviewer/Verifier/Publisher`。
- 真实主链补证任务单独走 `VERIFY` 任务，不把“补样本”混成“实现任务”。

---

## 状态流转

默认状态流转：

```text
pending -> spec_ready -> author_done -> review_passed -> verify_passed -> published -> archived
```

可选中断状态：

```text
blocked
handed_off
```

规则：

- `review_passed` 前，不得宣称可交付。
- `verify_passed` 前，不得自动推远端。
- 真实主链证据缺失时，只能报“实现完成”或“条件性完成”，不能报“闭环完成”。

---

## 各阶段职责

### 1. Spec

先定清：

- 真实目标
- authority source
- 成功判据
- 风险等级
- 最小验收路径
- 当前层级
- 主链状态

`Spec Lite` 至少要回答上述字段；`Full Spec` 还要补 schema/contract、handoff、回退计划、边界说明。

### 2. Author

- 只做最小必要改动
- 不顺手扩大范围
- 不把临时旁路写成正式主链
- 先让改动能被验证，再谈额外优化

### 3. Reviewer

切换到严格 code review 心态，自审刚写的 diff。输出必须 findings-first。

固定检查项：

- authority source 是否被改错
- 是否引入双重真相源
- shim/mirror/cache/fallback 是否被偷升成正式主链
- 是否存在“测试能过但主链未接入”的伪完成
- 是否遗漏对应测试、文档、evidence、回退口径
- 是否把无关日志、state、临时样本、运行噪声带进提交

规则：

- 有阻断发现：先回修，再重新 Review
- 无阻断发现：明确写“自 review 未发现阻断项”，再进入 Verify

### 4. Verifier

按改动类型跑最低门，再按风险自动升档：

- 所有任务最低门：
  - `py_compile` / 导入检查 / 脚本语法
  - 改动相关最小测试集
- Telegram 主链相关：
  - 先按 `TELEGRAM_TEST_PROCESS.md` 匹配层级测试
  - 再跑 `EgoCore/tools/run_telegram_mainline_regression.sh`
  - 若触及 contract runtime，再补合同步门
- 双仓 / schema / adapter 相关：
  - 跑 contract/schema gate
  - 跑 cross-repo compatibility gate
  - 再跑 adapter/runtime 回归
- 真实故障修复：
  - 先 replay 复现，再修，再复跑最低回归门
- 真实主链补证：
  - Verify 只负责证据链完整性与结论口径，不和实现任务混写

### 5. Publisher

只有满足以下条件才允许 commit 和自动推远端：

- `Spec` 已清楚
- `Reviewer` 无阻断发现
- `Verifier` 已通过对应门
- 提交范围干净，只包含本轮正式内容

默认拆分为三类提交：

1. `code/mainline`
2. `docs/observation/index`
3. `evidence bundles`

---

## 对用户的默认交付格式

每次正式交付默认给出 4 段最小报告：

1. 改了什么
2. 我自 review 发现并修了什么
3. 我实际跑了什么验证
4. 还没证明什么

这样用户做的是第二层确认，而不是第一轮 bug 猎手。

---

## 失败策略

- `Reviewer` 发现问题：不报“已完成”，直接回修
- `Verifier` 未过：不推远端，保留为“条件性完成”
- 真实主链证据缺失：只报实现完成，不报闭环完成

---

## 试运行验收

先用未来连续 5 个任务试运行这套闭环，验收标准：

- 用户不再反复指出“漏测 / 漏回归 / 口径过强 / 提交带噪声”
- Telegram 主链任务默认都有层级门 + 最低回归门
- 双仓任务默认都有 contract gate
- 推送前都能清楚说出“已证实什么 / 未证实什么”
- 自 review 若发现问题，优先在同一轮内自修，不把首轮 QA 压给用户

---

## 当前边界

- 当前默认仍是高强度自检，速度略慢，但换更低返工率。
- 这是一套开发助手执行契约，不改变 `EgoCore/OpenEmotion` runtime 边界。
- 低风险 `L1/L2` 任务未来若经用户明确同意，可单独降到“中强度自检”；但 Telegram 主链、双仓、状态恢复、evidence 任务不降档。
