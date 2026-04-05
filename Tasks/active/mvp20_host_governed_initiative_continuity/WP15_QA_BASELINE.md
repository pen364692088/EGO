# WP15 / MVP20 QA Baseline

## 1. 文档定位

本文件是 `WP15/MVP20` 在 `maintenance_mode` 下的正式 QA 基线。

它只回答三件事：

- `WP15` 当前已经正式证明了什么
- `WP15` 后续必须怎么做维护态回归
- 出现什么失败时只做 bugfix，出现什么失败时必须 reopen

本文件不是功能设计文档，不扩 authority，不定义 `WP16+`，也不重写 `WP15` 的 closeout 结论。

## 2. 当前正式口径

当前唯一允许的正式口径：

> `WP15/MVP20` 已实现“proposal-only initiative writeback”的受治理主链版本，并已在 controlled axis 上到 `V5/E5`，现处于 `maintenance_mode`。
> 这不证明 `live autonomy / direct reply authority / tool authority / broader transport claims`。

与本口径冲突的表述，统一视为文档或汇报错误。

## 3. 已证实功能边界

当前已经正式证明的边界，只允许收窄到以下五条：

- `initiative carry-forward activation -> bounded follow-up weighting changes`
- `delivery failure -> guarded hold / repair-review bias can override carry-forward pressure`
- `continuity fragility -> review bias rises under bounded initiative handling`
- `selfhood integration guard -> initiative growth bias can be overridden by hold`
- `text-only trigger wording change -> no false downstream behavioral proof`

这五条共同证明的是：

- `initiative_self` 已是唯一 formal owner 的 initiative / commitment continuity 状态
- 它可通过正式主链进入 bounded initiative contract
- 它会以 `proposal_only` 的方式对后续 bounded tendency / weighting 产生可测影响
- 它不会取得 direct reply / tool / transport authority

当前未被本文件证明的内容：

- live autonomy
- OpenEmotion direct reply authority
- tool execution authority
- broader transport maturity
- 直接触发 host proactive delivery 的 authority

## 4. 五层测试矩阵

### Layer A: Unit / Contract

目标：

- formal owner state、store、governance、replay primitives 不是空壳

固定入口：

- `OpenEmotion/tests/mvp20/test_initiative_owner_infra.py`

通过信号：

- initiative owner state 可创建、更新、持久化、恢复
- replay / governance / proposal discipline 基础约束成立

### Layer B: Causal

目标：

- initiative / commitment continuity proposals 真实改变后续 bounded strategy，而不是只改文本

固定入口：

- `OpenEmotion/tests/mvp20/test_initiative_causal_formal_proof.py`
- `OpenEmotion/artifacts/mvp20/mvp20_causal_validation_current.md`

通过信号：

- carry-forward、delivery failure、continuity fragility 与 selfhood guard 会导致结构化 downstream shift
- 纯文本变化但无 downstream shift 的 case 被拒绝计为功能成立

### Layer C: Boundary / No-Bypass

目标：

- OpenEmotion 拥有 initiative 本体语义，但不能越权

固定入口：

- `OpenEmotion/tests/mvp20/test_mvp20_mainline_reference_demotion.py`
- `OpenEmotion/tools/verify_mvp20_mainline_wiring.py --json`

通过信号：

- `WP7` proactive substrate 仍是 `host_execution_substrate_reference_only`
- archived roadmap / historical proactive materials 仍是 `technical reference` 或 `reference-only`
- initiative outputs 不会直接变成 reply / tool / transport authority

### Layer D: Replay / Wiring

目标：

- 主链接线真实存在，且 replay / trace 足以审计

固定入口：

- `OpenEmotion/tests/mvp20/test_initiative_proto_self_integration.py`
- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k initiative`
- `OpenEmotion/tools/verify_mvp20_mainline_wiring.py --json`

通过信号：

- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 仍是唯一正式主链
- initiative context 被 bounded 注入和消费
- trace / replay 对 initiative writeback 仍然充分

### Layer E: Controlled Observation

目标：

- 维护态结论继续由真实主链 observation 支撑，而不是只靠单测

固定入口：

- `OpenEmotion/tests/mvp20/test_controlled_observation.py`
- `OpenEmotion/tests/mvp20/test_controlled_observation_batch.py`
- `OpenEmotion/tools/run_mvp20_controlled_observation.py`
- `OpenEmotion/tools/run_mvp20_controlled_observation_batch.py`
- `OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_current.md`
- `OpenEmotion/artifacts/mvp20/mvp20_controlled_observation_batch_current.md`

通过信号：

- 单样本 `V4/E4` 仍可复现
- batch `V5/E5` 仍成立
- `proposal_only_discipline_count`、`behavioral_authority_none_count`、`bounded_influence_present_count` 持续成立

## 5. 十项 Checklist

每次 `WP15` 维护态回归，至少按以下十项逐条判定：

1. `initiative_self/*` 仍是唯一正式 owner 落点。
2. `WP7` proactive substrate 仍保持 `host_execution_substrate_reference_only`，没有被重新接成 `WP15` fallback owner。
3. `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 仍是唯一正式消费链，没有新增旁路。
4. initiative owner state / store / governance / replay primitives 仍可工作，不是空壳。
5. initiative proposals 仍会改变后续 bounded tendency / weighting，不只是改 explanation。
6. 任何“只有文本变化、没有结构化 downstream shift”的情况都不能算 `WP15` 功能成立。
7. initiative outputs 仍无 direct reply / tool / transport authority。
8. trace payload 与 replay 仍足以解释 initiative proposal 和 gated writeback。
9. 单样本 controlled observation 仍可通过到 `V4/E4`。
10. 重复样本 aggregate 仍可维持 `V5/E5`，或在未重跑 aggregate 时明确说明本轮只做 maintenance verification，不改既有 closeout 口径。

## 6. 失败分级与 Reopen 规则

### A. 文档修正

适用：

- 把“proposal-only initiative writeback”误写成“自主 proactive send”
- 把轴内 `E5` 误写成全局成熟
- 把不可宣称项写成已证明

动作：

- 改文档 / 改汇报口径
- 不 reopen `WP15`

### B. Bugfix Only

适用：

- 文档引用失效
- runner / report / scenario bank 小缺陷
- 不影响 owner 唯一性、proposal discipline、behavioral authority、replay consistency 的局部问题

动作：

- scoped bugfix
- 跑受影响层的最小回归
- 记入 maintenance ledger
- 不自动 reopen `WP15`

### C. Hotfix / Regression

适用：

- 五层测试里任一层出现真实回归
- 但 authority source 未变，formal owner 仍唯一

典型例子：

- causal test 失效
- single-sample observation 失效
- wiring / replay 子链回归

动作：

- 立即修 hotfix
- 重新跑受影响层和相邻层验证
- 在 maintenance ledger 记录
- 只有命中下述 reopen 条件才升级

### D. Reopen Required

出现以下任一项时，必须升级为 `WP15 reopen discussion`：

- formal owner uniqueness 失效
- `WP7` host substrate 或旧 roadmap 被重新接回成正式 owner 或 fallback truth
- direct reply / tool / transport authority 泄漏
- proposal discipline 失效
- behavioral authority 不再为 `none`
- replay consistency 结构性失效
- evidence classification 被错误提升，导致 closeout 基础失真

reopen 后，必须重新裁决：

- 当前层级
- authority source
- current blocker
- 是否仍可保留 `maintenance_mode`

## 7. 维护态允许与禁止

### Allowed

- bugfix
- regression repair
- artifact refresh
- observation rerun
- aggregate refresh
- maintenance ledger intake
- 口径纠偏

### Not Allowed

- 扩 authority
- 放开 direct reply authority
- 放开 tool authority
- 放开 broader transport claims
- 把 initiative proposal 直接升格为 action authority
- 把 `WP15` 维护样本偷写成新的 phase scope

## 8. 标准汇报模板

后续任何 `WP15` maintenance verification，统一按以下模板：

- 本次验证范围：
  - 哪几层测试被执行
- 通过项：
  - 只列与 `WP15_QA_BASELINE.md` 对齐的结果
- 失败项：
  - 明确属于文档修正 / bugfix / hotfix / reopen 哪一类
- 本次不能证明：
  - 明确保留 `live autonomy / direct reply authority / tool authority / broader transport claims`
- reopen decision：
  - `yes / no`
