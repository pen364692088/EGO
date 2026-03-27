# Failure Evidence Ledger

## 口径

本账本记录两类内容：

1. `真实样本 evidence 缺项 / 不完整`，这会直接降低 E5 观察结论强度。
2. `真实主链 blocked/failure 业务样本`，这类样本本身不是坏事，但必须正式入账。

## 摘要

| 类别 | 数量 |
|---|---|
| evidence 缺项 / 不完整 | `23` |
| 真实 blocked 工具样本（完整） | `3` |
| 观察窗口内已确认 host semantic theft | `0` |
| 观察窗口内已确认 OpenEmotion 越权输出 | `0` |

## A. evidence 缺项 / 不完整

统一状态：`已归因，待补齐或正式归档`

统一归因：

- 当前剩余样本的硬缺项集中在 `normalized_event.json`、`openemotion_result.json`
- 一轮安全回填已把可合法推断的 `response_plan.json` 补回兼容镜像
- 这些样本不能计入 E5 完整成功样本
- 这直接构成 `replay / audit insufficiency`

| sample_id | 状态 | 缺项 |
|---|---|---|
| `sample_20260326_122012_a1eb9987` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_130620_fa6a1303` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_134949_b14ecef8` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_135004_de5a2b74` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_140841_7fd57d3e` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_141603_c295f138` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_141641_68a5a243` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_142359_945ae501` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_143224_1406bcb4` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_143303_9df6b133` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_143624_eb57644d` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_143641_05b02d55` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_143708_8a6c95fe` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_154600_e34d5fbc` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_154804_12ed4c28` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_180956_097602f5` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_181045_4e639441` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_181325_7177ff8e` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_184809_ab5a513f` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_204952_a1ad48c9` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_222703_9e2bb07b` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_223755_238449d4` | 已归因 | `normalized_event.json`, `openemotion_result.json` |
| `sample_20260326_223842_b8d9e1f2` | 已归因 | `normalized_event.json`, `openemotion_result.json` |

## B. 真实 blocked / failure 业务样本

统一状态：`已关闭（样本完整，纳入观察，不构成审计缺项）`

| sample_id | 结果 | 说明 |
|---|---|---|
| `sample_20260326_230059_8ded092c` | `tool:file blocked` | P3 前的 blocked 半边，family 仍是旧漂移口径；保留为对照证据。 |
| `sample_20260326_232655_3f3f89cb` | `tool:file blocked` | P4 后 blocked 半边，`mode=repair`，进入同 family。 |
| `sample_20260326_234618_b4b7792b` | `tool:shell blocked` | 真实 blocked 样本，证明失败样本并未被过滤出观察窗口。 |

## 当前阻塞含义

这份账本说明：

- 本轮不是“只有成功样本”的观察
- 但 `23/58` 的缺项比例仍过高，足以构成正式准入阻塞
- 在这些 gap 被压低前，不应把结论升级成 `E5 稳定成立`
