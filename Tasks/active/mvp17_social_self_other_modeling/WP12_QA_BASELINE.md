# WP12 / MVP17 QA Baseline

## 1. 文档定位

本文件是 `WP12/MVP17` 在 `maintenance_mode` 下的正式 QA 基线。

它只回答三件事：

- `WP12` 当前已经正式证明了什么
- `WP12` 后续必须怎么做维护态回归
- 出现什么失败时只做 bugfix，出现什么失败时必须 reopen

本文件不是功能设计文档，不扩 authority，不定义 `WP13+`，也不重写 `WP12` 的 closeout 结论。

## 2. 当前正式口径

当前唯一允许的正式口径：

> `WP12/MVP17` 已实现“proposal-only social writeback”的受治理主链版本，并已在 controlled axis 上到 `V5/E5`，现处于 `maintenance_mode`。
> 这不证明 `live autonomy / direct reply authority / broader transport claims`。

与本口径冲突的表述，统一视为文档或汇报错误。

## 3. 已证实功能边界

当前已经正式证明的边界，只允许收窄到以下四条：

- `negative trust drift -> guarded social weighting + repair-sensitive proposal`
- `commitment breach -> stricter commitment guard + elevated repair bias`
- `boundary caution -> cautious boundary weighting`
- `text-only social event wording change -> no false downstream behavioral proof`

这四条共同证明的是：

- `social_self` 已是唯一 formal owner 的 social continuity state
- 它可通过正式主链进入 bounded social contract
- 它会以 `proposal_only` 的方式对后续 bounded tendency / weighting 产生可测影响
- 它不会取得 direct reply / tool / transport authority

当前未被本文件证明的内容：

- 完整社会人格或开放式 social autonomy
- 泛化 other-model mind-reading
- live autonomy
- OpenEmotion direct reply authority
- broader transport maturity

## 4. 五层测试矩阵

### Layer A: Unit / Contract

目标：

- formal owner state、store、governance、replay primitives 不是空壳

固定入口：

- `OpenEmotion/tests/mvp17/test_social_owner_infra.py`

通过信号：

- social owner state 可创建、更新、持久化、恢复
- replay / governance / proposal discipline 基础约束成立

### Layer B: Causal

目标：

- social proposals 真实改变后续 bounded strategy，而不是只改文本

固定入口：

- `OpenEmotion/tests/mvp17/test_social_causal_formal_proof.py`
- `OpenEmotion/artifacts/mvp17/mvp17_causal_validation_current.md`

通过信号：

- trust drift、commitment breach、boundary caution 会导致结构化 downstream shift
- 纯文本变化但无 downstream shift 的 case 被拒绝计为功能成立

### Layer C: Boundary / No-Bypass

目标：

- OpenEmotion 拥有 social self 本体语义，但不能越权

固定入口：

- `OpenEmotion/tests/mvp17/test_mainline_reference_demotion.py`
- `OpenEmotion/tools/verify_mvp17_mainline_wiring.py --json`

通过信号：

- 旧 social / relation surfaces 仍是 `reference-only` 或 `input-only`
- social outputs 不会直接变成 reply / tool / transport authority
- runtime bridge 只做承接和记录，不偷做 social owner semantics

### Layer D: Replay / Wiring

目标：

- 主链接线真实存在，且 replay / trace 足以审计

固定入口：

- `OpenEmotion/tests/mvp17/test_social_proto_self_integration.py`
- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k social`
- `OpenEmotion/tools/verify_mvp17_mainline_wiring.py --json`

通过信号：

- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 仍是唯一正式主链
- social context 被 bounded 注入和消费
- trace / replay 对 social writeback 仍然充分

### Layer E: Controlled Observation

目标：

- 维护态结论继续由真实主链 observation 支撑，而不是只靠单测

固定入口：

- `OpenEmotion/tests/mvp17/test_controlled_observation.py`
- `OpenEmotion/tests/mvp17/test_controlled_observation_batch.py`
- `OpenEmotion/tools/run_mvp17_controlled_observation.py`
- `OpenEmotion/tools/run_mvp17_controlled_observation_batch.py`
- `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_current.md`
- `OpenEmotion/artifacts/mvp17/mvp17_controlled_observation_batch_current.md`

通过信号：

- 单样本 `V4/E4` 仍可复现
- batch `V5/E5` 仍成立
- `proposal_only_discipline_count`、`behavioral_authority_none_count`、`bounded_influence_present_count` 持续成立

## 5. 十项 Checklist

每次 `WP12` 维护态回归，至少按以下十项逐条判定：

1. `social_self/*` 仍是唯一正式 owner 落点。
2. 旧 social / relation surfaces 仍保持 `reference-only` 或 `input-only`，没有重新进入主链消费。
3. `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 仍是唯一正式消费链，没有新增旁路。
4. social owner state / store / governance / replay primitives 仍可工作，不是空壳。
5. trust / commitment / repair proposals 仍会改变后续 bounded tendency / weighting，不只是改 explanation。
6. 任何“只有文本变化、没有结构化 downstream shift”的情况都不能算 `WP12` 功能成立。
7. social outputs 仍无 direct reply / tool / transport authority。
8. trace payload 与 replay 仍足以解释 social proposal 和 writeback。
9. 单样本 controlled observation 仍可通过到 `V4/E4`。
10. 重复样本 aggregate 仍可维持 `V5/E5`，或在未重跑 aggregate 时明确说明本轮只做 maintenance verification，不改既有 closeout 口径。

## 6. 失败分级与 Reopen 规则

### A. 文档修正

适用：

- 把“proposal-only social writeback”误写成“完整社会人格”
- 把轴内 `E5` 误写成全局成熟
- 把不可宣称项写成已证明

动作：

- 改文档 / 改汇报口径
- 不 reopen `WP12`

### B. Bugfix Only

适用：

- 文档引用失效
- runner / report / scenario bank 小缺陷
- 不影响 owner 唯一性、proposal discipline、behavioral authority、replay consistency 的局部问题

动作：

- scoped bugfix
- 跑受影响层的最小回归
- 记入 maintenance ledger
- 不自动 reopen `WP12`

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

出现以下任一项时，必须升级为 `WP12 reopen discussion`：

- formal owner uniqueness 失效
- legacy social path 被重新接回正式主链
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
- 把 social proposal 直接升格为 action authority
- 把 `WP12` 维护样本偷写成新的 phase scope
- 因为 `WP12` 已 pass 就回推“OpenEmotion 可以直接说话”

## 8. 标准汇报模板

每次 `WP12` maintenance verification，统一按以下结构汇报：

### Verification Scope

- 本次触发层：`Unit / Contract | Causal | Boundary | Replay/Wiring | Controlled Observation`
- 入口命令：
- 影响文件或 artifacts：

### Pass / Fail

- 通过项：
- 失败项：
- 是否命中十项 checklist：

### Current Claim

- 允许的当前口径：
- 本次不能证明什么：

### Reopen Decision

- 是否触发 reopen：
- 若否：归类为 `doc fix | bugfix | hotfix`
- 若是：列出命中的 reopen 条件
