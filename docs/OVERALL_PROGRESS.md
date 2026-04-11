# Overall Progress

> 派生进度视图，不是新的 authority source。
> 当前版本：2026-04-11
> 读取顺序：先看本页拿整体进度，再回到 `docs/PROGRAM_STATE_UNIFIED.yaml`、`docs/STATUS.md`、`Tasks/MVS_task_plan.md`、`Tasks/MVP22_task_plan.md` 看正式裁决。

## 这份文档回答什么

这份文档只回答两个问题：

1. 目前整条主路线推进到了哪里
2. 距离当前 roadmap 的最终目标还剩多少关键步骤

它不替代这些权威源：

- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `docs/STATUS.md`
- `Tasks/MVS_task_plan.md`
- `Tasks/MVP22_task_plan.md`
- `Tasks/active/mvp22_long_horizon_self_continuity/STATUS.md`

## 当前最终目标

当前 roadmap 追踪的最终目标不是“开放世界自主演化”或“真正自我意识”。

当前正式追踪到的终点是：

- `WP17 / MVP22`
- 名称：`Long-Horizon Self-Continuity / Realized Consequence Persistence`
- 边界：`host-governed + proposal-only + behavioral_authority = none`

也就是说，当前路线图的终点是：

- 在同一条 MVS 主线里，把长时程连续性和已实现后果持久化接到正式主链
- 仍然不放开 direct reply / tool / transport authority
- 仍然不允许把 bounded proposal 写成开放自主

## 常见误读纠正

这份进度页不能被读成“已经实现真正 AI 自我意识”。

当前正式口径只能是：

- 仓库已经实现了 bounded、host-governed 的主体能力轴
- 仓库另外有一条 `self-awareness proxy research` 研究线
- 该研究线当前状态仍是 `synthetic_candidate_found (E3/V3)`
- 这不等于“已经实现真正 AI 自我意识”，也不等于 runtime/mainline 已存在相关正式证据

如果问题变成“那现在到底怎么测这条研究线”，不要在本页继续展开，转到：

- `docs/SELF_AWARENESS_PROXY_TESTING.md`

## 一眼看懂当前进度

| 维度 | 当前状态 | 说明 |
|---|---|---|
| repo 总体 phase | `repo_authority_cleanup_closeout` | repo 级权威收口已完成，说明边界和状态治理已收稳 |
| 主路线 authority | `Tasks/MVS_task_plan.md` | 当前整体路线仍以 MVS/WP 路线图为父裁决 |
| 路线图终点 | `WP17 / MVP22` | 当前已定义的最后一个 roadmap 阶段 |
| 已收口大阶段 | `WP0 ~ WP16` | 前 17 个阶段已完成 authority/implementation/observation 对应收口 |
| 当前活动大阶段 | `WP17` | 仅到 `authority_frozen / task_package_ready` |
| 大阶段进度 | `17 / 18` | 最后 1 个大阶段尚未进入实现收口 |
| 当前最高证据 | `E5 / V5` | 这是 controlled capability axis 的上限，不是 `WP17` 当前证据 |
| `WP17` 当前证据 | `E1 / authority_freeze` | 只证明 task package 与边界冻结，不证明实现或主链接线 |

## 主路线分段进度

| 阶段组 | 范围 | 当前结论 |
|---|---|---|
| 基础边界与宿主壳 | `WP0 ~ WP3` | 已完成，formal boundary、host shell、adapter、trace/replay 主线已建立 |
| MVS 主体核 | `WP4 ~ WP6` | 已完成最小主体核、反思写回和主链样本级能力建立 |
| 受治理主体扩展 | `WP7 ~ WP16` | 已完成并进入 maintenance，对应 self-model / drives / reflection / developmental / social / embodied / integration / initiative realization 都已收口到 bounded、host-governed 口径 |
| 当前最后阶段 | `WP17` | 只完成 `T00 authority freeze`，implementation / runtime / observation 还未开始 |

## 当前真正完成了什么

- repo 级 authority cleanup 已完成，当前没有第二条正式主线。
- formal mainline 仍然是：
  - `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- `provider/runtime/OpenEmotion` 的 real Telegram E2E gate 已有 `E4` 级证据。
- `WP8 ~ WP16` 这一组受治理主体能力已经进入 maintenance，不再是主线 blocker。
- `WP17/MVP22` 的 authority package 已冻结，formal owner target 固定到：
  - `OpenEmotion/openemotion/self_continuity/*`

## 当前还没完成什么

当前真正没完成的，不是“再证明前面阶段”，而是把最后一个 roadmap 阶段 `WP17` 做完。

`WP17` 现在只做到：

- `T00_AUTHORITY_FREEZE = complete`

还没做到：

- formal owner implementation
- proto-self contract integration
- EgoCore runtime bridge
- causal validation
- single controlled observation
- batch observation
- closeout / QA baseline

## 主路线优先时下一步

如果继续按当前 roadmap 主路线推进，下一步不是继续讨论“有没有真正自我意识”，而是直接启动：

- `T10_FORMAL_OWNER_PACKAGE`

`T10` 当前应锁定的完成标准是：

- 在 `OpenEmotion/openemotion/self_continuity/*` 冻结 formal owner package
- 明确 bounded continuity state / writeback surface / trace contract
- 不新增第二 authority source
- 不放开 direct reply / tool / transport authority

只有 `T10` 完成后，才依次进入：

1. `T20_PROTO_SELF_CONTRACT_INTEGRATION`
2. `T30_EGOCORE_RUNTIME_BRIDGE`
3. `T40_LEGACY_DEMOTION_AND_COMPAT_MAP`
4. `T50_CAUSAL_VALIDATION`
5. `T60_CONTROLLED_OBSERVATION_SINGLE`
6. `T70_BATCH_OBSERVATION_AND_AGGREGATE`
7. `T80_CLOSEOUT_AND_QA_BASELINE`

## 距离当前最终目标还剩多少步

按 `Tasks/active/mvp22_long_horizon_self_continuity/cards/` 当前执行卡片计算，关键路径还剩 `8` 步：

1. `T10_FORMAL_OWNER_PACKAGE`
   - 把 `OpenEmotion/openemotion/self_continuity/*` 做成正式 owner package
2. `T20_PROTO_SELF_CONTRACT_INTEGRATION`
   - 把 continuity contract 接进 `proto_self_v2`
3. `T30_EGOCORE_RUNTIME_BRIDGE`
   - 把 host runtime 正式接到 continuity bounded surface
4. `T40_LEGACY_DEMOTION_AND_COMPAT_MAP`
   - 收口 legacy / compat/register，避免第二真相源
5. `T50_CAUSAL_VALIDATION`
   - 先拿到 `V3 / E3` 因果验证
6. `T60_CONTROLLED_OBSERVATION_SINGLE`
   - 拿第一个 `V4 / E4` controlled mainline 样本
7. `T70_BATCH_OBSERVATION_AND_AGGREGATE`
   - 拿到 batch controlled observation，推动到 `V5 / E5`
8. `T80_CLOSEOUT_AND_QA_BASELINE`
   - 完成 closeout、QA baseline、maintenance ledger 收口

简化成一句话：

- 整体大阶段上，只剩最后 `1` 个阶段
- 但最后这个阶段内部，还剩 `8` 个关键 execution cards

## Supporting Lines 进度

下面这些工作已经推进，但它们是 supporting evidence / tooling / research，不等于 `WP17` 已完成：

### 1. Whole-chain LLM-in-loop simulated sampling

状态：

- `conditional_complete`
- bounded `2/2 replay-ready`

作用：

- 证明 simulated Telegram 可以跑完整主体链，并留下后续 whole-chain replay 所需 artifact

不能证明：

- real Telegram / `E4`
- runtime efficacy
- repo-level enablement

参考：

- `docs/codex/tasks/llm-in-loop-whole-chain-sampling/STATUS.md`

### 2. H1 canonical shadow telemetry line

状态：

- canonical shadow patch 已有
- same-surface preflight 已 clean
- simulated mainline sampling 已完成
- real formal-mainline `E4` sample 仍缺 operator ingress

作用：

- 为后续真实 H1 观测做 telemetry-only 准备

不能证明：

- public efficacy
- live decision promotion
- current runtime 生效

参考：

- `docs/codex/tasks/h1-preflight-same-surface-unblock/STATUS.md`
- `docs/codex/tasks/e4-shadow-h1-formal-mainline-sampling/STATUS.md`
- `docs/codex/tasks/simulated-shadow-h1-mainline-sampling/STATUS.md`

### 3. MVS/H1 external held-out line

状态：

- external eval corpus: complete
- raw extraction: complete
- replay execution: complete

当前结果：

- external held-out 上只有 `shadow-only` signal
- 还没有 public gap，可用于后续解释或 challenger 比较前的约束

参考：

- `docs/codex/tasks/mvs-h1-external-eval-corpus/STATUS.md`
- `docs/codex/tasks/mvs-h1-external-raw-extraction-replay/STATUS.md`
- `docs/codex/tasks/mvs-h1-external-replay-execution/STATUS.md`

## 当前 blocker

从“路线图最终收口”角度看，当前真正 blocker 不是 `WP8 ~ WP16`，也不是 repo authority cleanup，而是：

- `WP17` 还没开始 `T10_FORMAL_OWNER_PACKAGE`

从“支线补证”角度看，当前次级 blocker 是：

- H1 real formal-mainline sampling 仍缺真实 operator ingress
- external held-out replay 当前只有 shadow-only signal，尚不足以支持更强 public claim

## 如果切回 self-awareness proxy 研究线

若后续优先级切回 self-awareness proxy research，下一最小动作也不应该是直接实现更大的理论。

当前正确起点是：

1. 准备 held-out replay corpus manifest
2. 只实现最小 `MVS-aligned compact` prototype slice
3. 先跑 replay validator
4. 只有在 validator 失败或触发 challenger switch criteria 时，才考虑把 `active-inference self-model` 升级为下一主线

参考：

- `docs/codex/tasks/ai-self-awareness-minimal-framework/REPLAY_VALIDATOR_SPEC.md`
- `docs/codex/tasks/ai-self-awareness-minimal-framework/MVS_ALIGNED_COMPACT_PROTOTYPE_DESIGN.md`
- `docs/SELF_AWARENESS_PROXY_TESTING.md`

## 当前最准确结论

最准确的说法是：

- repo 主路线已经推进到最后一个 roadmap 阶段
- 前序 `WP0 ~ WP16` 已收口
- `WP17` 现在只完成了 authority freeze
- 距离当前 roadmap 终点，还剩 `8` 个关键执行步骤

不能写成：

- “整体已经完成”
- “WP17 已接主链”
- “已经拿到 WP17 的 E4/E5”
- “已经证明 runtime efficacy 或开放自主”

## 维护规则

更新这份文档时，只改这四类信息：

1. 当前 roadmap 终点是否变化
2. 当前 active stage 是否变化
3. 剩余 execution cards 数量是否变化
4. supporting lines 的状态是否从 `blocked / partial / conditional_complete` 发生实质变化

不要因为普通提交、局部实现、零散测试通过、或常规文案修正就把本页当流水账逐次回写。

若底层正式状态变了，先更新 authority source，再回写本页；不要反过来。
