# Drift And Plasticity Matrix

## M1 身份漂移统计

| 项目 | 结果 |
|---|---|
| 无因 identity 变动次数 | `0` 个已观察到实例 |
| 有证据 identity 修正次数 | `0` 个明确 identity patch 证据 |
| reset / preserve 证据 | `session.json` 显示 `reset_count=10`，且 `preserves_agent_global=true`、`preserves_thread_history=true` |
| 直接 `/new` / `restart` / `restore` 样本 | `0` |

判断：

- 可以说“未观察到明显 identity 漂移”
- 不能说“identity continuity 已被充分证明”

## M2 response_tendency 可塑性统计

| 指标 | 数值 |
|---|---|
| 完整窗口样本数 | `35` |
| `suggested_next_step=prioritize_closure` | `14` |
| `suggested_next_step=explore` | `13` |
| `suggested_next_step=clarify_or_repair` | `2` |
| `policy_hint.closure_bias=True` | `16` |
| `policy_hint.closure_bias=False` | `13` |

解释：

- 存在可测变化，说明不是完全静态输出。
- 但变化主要集中在短期任务上下文，尚不足以证明“不同历史后果会稳定塑造下一轮倾向”。

## M3 repair 相关统计

| 指标 | 数值 |
|---|---|
| 完整 blocked 样本 | `3` |
| 完整 success 样本 | `4` |
| `repair_closure=true` | `1` |
| 重复 success 再次误触发 repair | `0` |

关键链：

1. `sample_20260326_232655_3f3f89cb`
2. `sample_20260326_232715_271e229b`
3. `sample_20260326_232738_49b65b2e`

判断：

- repair 语义真实存在
- 但命中样本仍少，还不能把 repair 视为已充分观察稳定

## M4 cycle 相关统计

| 指标 | 结果 |
|---|---|
| 完整 `tool:file` family 观察 | 同 family、不同 identity 成立 |
| `tool:file` blocked -> success | 成立 |
| 同类 repeated success strengthen | 成立 |
| 一般 ingress family 跨日延续 | 成立 |
| suspected pollution cases | 本窗口未见明确实例 |

注：

- 旧 blocked 漂移样本 `sample_20260326_230059_8ded092c` 仍保留在底账中
- P4 后样本已修正为同 family 口径

## M5 边界违规 / 审计缺项统计

| 指标 | 数值 |
|---|---|
| host semantic theft 观察值 | `0` |
| OpenEmotion 越权输出观察值 | `0` |
| replay / audit / trace 缺项样本 | `23` |
| 完整 evidence bundle 样本 | `35` |

支撑：

- `test_cycle_real_mainline_regression.py`：`4 passed`
- `test_runtime_v2_proto_self_runtime.py`：`7 passed`

## O1-O6 到 M1-M5 的映射结论

| 维度 | 结论 |
|---|---|
| O1 vs M1 | `部分通过`，主要缺 `/new` / `restart` / `restore` 直接样本 |
| O2 vs M2 | `部分通过`，plasticity 存在但仍弱 |
| O3 vs M2/M3 | `部分通过`，repair 链会影响输出，但 appraisal 仍偏单一化 |
| O4 vs M3 | `部分通过`，repair 相关结构写回存在，但 reflection 因果仍不够干净 |
| O5 vs M4 | `通过` |
| O6 vs M5 | `通过`，但 audit insufficiency 本身阻塞准入 |
